from flask import Flask, request,jsonify, session,flash
from datetime import datetime
#from flask_pymongo import PyMongo
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"]= os.getenv("secretKey")
cluster = MongoClient("mongodb://localhost:27017/")
db = cluster[str(os.getenv("dbname"))]

user = db[str(os.getenv("user_table"))]
transaction = db[str(os.getenv("transaction_table"))]
ngo = db[str(os.getenv("ngo_table"))]

required = ["FOOD", "DONATION","MATERIALS"]


def login_required(f):
    def wraps(*args, **kwargs):
        if "LoggedAdmin" in session:
            return f(*args,**kwargs)
        else:
            return jsonify({"message":"login required"})
    return wraps


@app.route("/") # home page
def home():
    return "hello world"

@app.route("/user", methods =["POST"]) #for user to create )
def user():
    if request.method == "POST":
        db.user.insert_one({
            "_id":request.json["EmailID"], #primary key
            "FirstName":request.json["FirstName"],
            "LastName":request.json["LastName"],
            "Password":request.json["Password"],
            "DOB":request.json["DOB"],
            "PhoneNumber":request.json["PhoneNumber"],
            "PANNumber": request.json["PANNumber"],
            "Active":False,
            "LastLogin": datetime.now(),
            "IsAdmin": False
        })
        return jsonify({"message":"user created successfully"})


@app.route("/user/<id>", methods =["GET","DELETE"]) #for login
def login(id):
    CurrentUser = db.user.find_one({"_id":id})
    if request.method == "GET":
        if CurrentUser and request.json["Password"]== CurrentUser["Password"]:
            session["LoggedUser"] = CurrentUser # tocheck and use the user in diff places
            if CurrentUser["IsAdmin"] == True:
                session["LoggedAdmin"] = CurrentUser # to check before making a user into admin
            return jsonify({"message":"login succesfull"})
        else:
            return jsonify({"message":"invalid username and pwd"})
    
    elif request.method == "DELETE":
        if CurrentUser:
            ngo.remove({"_id":id})
            return jsonify({"message":"succesfully removed"})
        else:
            return jsonify({"message":"invalid usernamee"})


@app.route("/make_admin/<UserID>",methods=["GET","PUT"])
@login_required
def make_admin(UserID):
    CurrentUser = db.user.find_one({"_id":UserID})
    if CurrentUser and CurrentUser != session["LoggedAdmin"]:
        CurrentAdmin = session["LoggedAdmin"]
        db.user.update({"_id":UserID},{"$set":{"IsAdmin":True},"$push":{"AddedBy":CurrentAdmin}})
        return jsonify({"message":"you made user admin"})
    else:
        return jsonify({"message":"sorry! WRONG USEER  "})


@app.route("/transaction/<user_id>/<ngo_id>",methods = ["PUT"])
def transaction(user_id,ngo_id):
    pass

@app.route("/ngo", methods =["POST","GET"])
def ngo():
    if request.method == "POST":
        db.ngo.insert_one({
            "_id":request.json["EmailID"],  #primary key
            "Approved":False,
            "FullName":request.json["FullName"],
            "Password":request.json["Password"],
            "BankDetails":{
                "NameOncard":request.json["NameOnCard"],
                "AccountNumber":request.json["AccountNumber"],
                "IFSCCode":request.json["IFSCCode"],
                "PANNumber": request.json["PANNumber"]
            },
            "Address":request.json["Address"],
            "PhoneNumber":request.json["PhoneNumber"],                  #add location down
            "Description":[request.json["Type"],request.json["NoOfPeople"],"locationID",0,0],
                            #type of org       , no of people             ,loctionid, amt raised,likes
            "DateJoined": datetime.now(),
            "DonatedList":[],
            "Requirement": required[request.json["GetNumber"]], #1=food, 2=money, 3= materiaals  (refer line 15)
        })
        return jsonify({"message":"ngo created successfully"})



@app.route("/ngo/<id>", methods =["GET","DELETE"])
def login_ngo(id):
    if request.method == "GET":
        CurrentNGO = db.ngo.find_one({"_id":id})
        if CurrentNGO and request.json["Password"]== CurrentNGO["Password"]: #check for password 
            return jsonify({"message":"logged in succesfully"})
        else:
            return jsonify({"message":"invalid username and pwd"})
    
    elif request.method == "DELETE":
        CurrentNGO = db.ngo.find_one({"_id":id})
        if CurrentNGO:
            ngo.remove({"_id":id})
            return jsonify({"message":"succesfully removed"})
        else:
            return jsonify({"message":"invalid usernamee"})




if __name__ == "__main__":
    app.run(debug = True)