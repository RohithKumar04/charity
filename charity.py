from flask import Flask,request,jsonify, session,flash
import datetime
from functools import wraps
#from flask_pymongo import PyMongo
import pymongo
from dotenv import load_dotenv
import os
import jwt,json


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"]= os.getenv("secretKey")
cluster = pymongo.MongoClient("mongodb://localhost:27017/")
db = cluster[str(os.getenv("dbname"))]

user = db[str(os.getenv("user_table"))]
transaction = db[str(os.getenv("transaction_table"))]
ngo = db[str(os.getenv("ngo_table"))]
location = db["Cities"]

required = ["FOOD", "DONATION","MATERIALS"]

print("commit 1");
print("commit 2");

with open("city.json","r") as city:
   db.location.insert_many(json.load(city))

count = 0 #to count no of users
approval = []

def login_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if "token" in request.headers:
            token = request.headers["token"]

            if not token:
                return jsonify({"message":"token is missing"})

            try:
                data = jwt.decode(token,app.config["SECRET_KEY"])
            except:
                return jsonify({"message":"invalid token"})
            return f(data,*args,**kwargs)
        else:
            return jsonify({"message":"login required"})
        
    return decorator

@app.route("/user/<ngoID>/approval")
@login_required
def approval(admin,ngoID):
    if not admin["IsAdmin"]:
        return jsonify({"message":"only accesalbe to admin"}) 
    
    if request.json["approval"]:
        db.ngo.update({"_id":ngoID},{"$set":{"Approved":True}})
        return jsonify({"message":"approval granted"})
    else: # disapproval
        db.ngo.update({"_id":ngoID},{"$set":{"Approved":False}})
        return jsonify({"message":"approval withdrawn"})

print("new commit")
@app.route("/search") 
def search():
    q =request.args.get("q")
    city =  request.args.get("city")
    if q: #to search near by ngo with coordinates and name
        result = db.ngo.find( {"$and":[{"FullName":{"$regex": q,"$options":'i'}},
                        {"Location" :{"$near":{ "$geometry" :{"type":"Point","coordinates" : [request.json["long"] , request.json["latitude"]] } ,"$maxDistance" : 5000} } },
                        {"City":city}]} )
    else:
        result = db.ngo.find( {"Location" :{"$near":{ "$geometry" :{"type":"Point", # search nearby ngos with coordinates
                              "coordinates" : [ request.json["long"] , request.json["latitude"]] } ,
                             "$maxDistance" : 500
                      } } } )
    #print(result)
    user_data = []
    for user in result:
        if user["Approved"]: #to make only approved ngo visible to the users
            user_data.append(user)
    return jsonify({"users":user_data})
    #return jsonify({"serach results": result}) 

@app.route("/user", methods =["POST"]) #create user )
def create_user():
    try: # catch duplicate error
        if request.method == "POST":
            db.user.insert_one({
                "_id":request.json["EmailID"], #primary key
                "FirstName":request.json["FirstName"],
                "LastName":request.json["LastName"],
                "CurrentPassword":request.json["CurrentPassword"],
                "DOB":request.json["DOB"],
                "PhoneNumber":request.json["PhoneNumber"],
                "PANNumber": request.json["PANNumber"],
                "Active":True if count ==0 else False, # the first user created will be admin
                "LastLogin":datetime.datetime.utcnow(),
                "IsAdmin":False
            })
            return jsonify({"message":"user created successfully"}
            )
        count +=1
    except:
        return jsonify({"message":"user already exist"})


@app.route("/user",methods=["GET"])
@login_required
def AllUsers(admin):
    if not admin["IsAdmin"]:
        return jsonify({"message":"only accesalbe to admin"})

    if request.method == "GET":
        users = db.user.find()
        user_data = []
        for user in users:
             user_data.append(user)
        return jsonify({"users":user_data})
    else:
        return jsonify({"message":"not a valid request"})

@app.route("/user/<id>", methods =["DELETE"]) #for deleting user
@login_required
def DeleteUser(admin,id):
    if not admin["IsAdmin"]:
        return jsonify({"message":"only accesalbe to admin"})

    if request.method == "DELETE":
        CurrentUser = db.user.find_one({"_id":id})
        if CurrentUser:
            db.user.remove({"_id":id})
            return jsonify({"message":"succesfully removed"})
        else:
            return jsonify({"message":"invalid usernamee"})

@app.route("/user/<userID>",methods = ["GET"]) #to obtain one user
def oneUser(userID):
    if request.method == "GET":
        CurrentUser = db.user.find({"_id":userID})
        display = []
        for user in CurrentUser:
            display.append(user)
        return jsonify({"user":display})
    return jsonify({"message":"not Valid User"})

@app.route("/user", methods= ["PUT"]) #current pwd is mandatory for updating
@login_required
def UpdateUser(loggeduser):
    if request.method == "PUT":
        CurrentPassword = loggeduser["CurrentPassword"] #password from the token
        if CurrentPassword == request.json["CurrentPassword"]:
            db.user.update({"_id":loggeduser["Username"]},{"$set":{
            "FirstName":request.json["FirstName"],
            "LastName":request.json["LastName"],
            "CurrentPassword":request.json["NewPassword"], #updating new password
            "PhoneNumber":request.json["PhoneNumber"]
            }})
            return jsonify({"message": "successfully updated"})
    return jsonify({"message":"not a valid request"})


@app.route("/login") #to login
def userlogin():
    CurrentUser = db.user.find_one({"_id":request.json["EmailID"]})
    if CurrentUser and CurrentUser["CurrentPassword"] == request.json["CurrentPassword"]:
        token = jwt.encode({"Username":CurrentUser["_id"],"CurrentPassword":CurrentUser["CurrentPassword"],"FirstName":CurrentUser["FirstName"],"PhoneNumber":CurrentUser["PhoneNumber"],"IsAdmin":CurrentUser["IsAdmin"],"exp":datetime.datetime.utcnow()+datetime.timedelta(minutes=40)},app.config["SECRET_KEY"])

        session["loggedin"]= CurrentUser

        db.user.update({"_id":CurrentUser["_id"]},{"$set":{"LastLogin":datetime.datetime.utcnow(),"Active":True}})
        return jsonify({"token": token.decode("UTF-8")})
    else:
        return jsonify({"message":"invalid user"})

@app.route("/make_admin/<UserID>",methods=["GET","PUT"])
@login_required
def make_admin(admin,UserID):
    if admin["IsAdmin"] and admin["Username"] != UserID: 
        CurrentUser = db.user.find_one({"_id":UserID})
        db.user.update({"_id":UserID},{"$set":{"IsAdmin":True},"$push":{"AddedBy":{"Name":admin["FirstName"],"EmailID":admin["Username"],"PhoneNumber":admin["PhoneNumber"]}}})
        return jsonify({"message":"you made user admin"})
    else:
        return jsonify({"message":"sorry! WRONG USEER  "})

@app.route("/logout") #can be used for both user and ngo
def logout():
    if "loggedin" in session:
        session.pop("loggedin",None)
        if "token" in request.headers:
            request.headers["token"] = None
        return jsonify({"message":"successfully logged out"})
    else:
        return jsonify({"message":"redirect to login page"})

@app.route("/ngo", methods =["POST"])
def create_ngo():
    if request.method == "POST":
        city = db.location.find_one({"name":{"$regex":request.json["city"],"$options":"i"}})
        db.ngo.insert_one({
            "_id":request.json["EmailID"],  #primary key
            "Approved":False,
            "FullName":request.json["FullName"],
            "CurrentPassword":request.json["CurrentPassword"],
            "BankDetails":{
                "NameOncard":request.json["NameOnCard"],
                "AccountNumber":request.json["AccountNumber"],
                "IFSCCode":request.json["IFSCCode"],
                "PANNumber": request.json["PANNumber"]
            },
            "Address":request.json["Address"],
            "PhoneNumber":request.json.get("PhoneNumber"),                  #add location down
            "Description":[request.json["Type"],request.json["NoOfPeople"],0,0],
                            #type of org       , no of people             ,loctionid, amt raised,likes
            "DateJoined": datetime.datetime.utcnow(),
            "DonatedList":[],
            "City":city["name"],
            "State":city["state"],
            "Location":{"type":"Point",
                 "coordinates":[request.json["Latitude"],request.json["Longitude"]]
                 },
            "Requirement": required[request.json["GetNumber"]] #1=food, 2=money, 3= materiaals  (refer line 15)
        })
        CurrentNGO = db.ngo.find_one({"_id":request.json["EmailID"]})
        approval.append(CurrentNGO)
        db.ngo.create_index([("Location", pymongo.GEOSPHERE)]) 
        return jsonify({"message":"ngo created successfully"})

@app.route("/ngo",methods=["GET"])
@login_required
def AllNGOs(admin):
    if not admin["IsAdmin"]:
        return jsonify({"message":"only accesalbe to admin"})

    if request.method == "GET":
        ngos = db.ngo.find()
        ngo_data = []
        for user in ngos:
            ngo_data.append(user)
        return jsonify(({"users":ngo_data}))
    else:
        return jsonify({"message":"not a valid request"})

@app.route("/ngo/<id>", methods =["DELETE"]) #for deleting ngo
@login_required
def Deletengo(admin,id):
    if not admin["IsAdmin"]:
        return jsonify({"message":"only accesalbe to admin"})

    if request.method == "DELETE":
        Currentngo = db.ngo.find_one({"_id":id})
        if Currentngo:
            ngo.remove({"_id":id})
            return jsonify({"message":"succesfully removed"})
        else:
            return jsonify({"message":"invalid usernamee"})

@app.route("/ngo/<ngoID>",methods = ["GET"]) #to obtain one ngo
def onengo(ngoID):
    if request.method == "GET":
        Currentngo = db.ngo.find_one({"_id":ngoID})
        return jsonify({"message":Currentngo})
    return jsonify({"message":"not Valid ngo"})

@app.route("/ngo", methods= ["PUT"]) #current pwd is mandatory for updating
@login_required
def Updatengo(loggedngo):
    if request.method == "PUT":
        CurrentPassword = loggedngo["CurrentPassword"] #password from the token
        if CurrentPassword == request.json["CurrentPassword"]:
            db.ngo.update({"_id":loggedngo["Username"]},{"$set":{
            "FullName":request.json["FullName"],
            "Address":request.json["Address"],
            "CurrentPassword":request.json["NewPassword"], #updating new password
            "PhoneNumber":request.json["PhoneNumber"],
            "Requirement": required[request.json["GetNumber"]],
            "Description.1": request.json["NoOfPeople"] #refer line 15
            }})
            return jsonify({"message": "successfully updated"})
    return jsonify({"message":"not a valid request"})

@app.route("/loginNGO")
def ngologin():
    Currentngo = db.ngo.find_one({"_id":request.json["EmailID"]})
    if Currentngo and Currentngo["CurrentPassword"] == request.json["CurrentPassword"]:
        token = jwt.encode({"Username":Currentngo["_id"],"CurrentPassword":Currentngo["CurrentPassword"],"Address":Currentngo["Address"],"FullName":Currentngo["FullName"],"PhoneNumber":Currentngo["PhoneNumber"],"Requirement":Currentngo["Requirement"],"exp":datetime.datetime.utcnow()+datetime.timedelta(minutes=40)},app.config["SECRET_KEY"])

        session["loggedin"]= Currentngo #for logging out

        return jsonify({"token": token.decode("UTF-8")})
    else:
        return jsonify({"message":"invalid user"})




if __name__ == "__main__":
    app.run(debug = True)