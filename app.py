from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from flask_cors import CORS
from flask_pymongo import PyMongo
import datetime
import jwt
import os
import openai
load_dotenv()

app = Flask(__name__)
app.config['MONGO_URI'] =os.getenv("mongo_url")
mongo = PyMongo(app)
CORS(app)
app.config['SECRET_KEY'] = 'secret!'
openai.api_key = os.getenv("OPENAI_API_KEY")
socketio = SocketIO(app,cors_allowed_origins='*')

app.config['CORS_HEADERS'] = 'Content-Type'
cors = CORS(app)


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "All details are required"}), 400
    
    user = mongo.db.users.find_one({"email": email})
    if user:
        return jsonify({"message": "User already registered"}), 200

    password_hash = generate_password_hash(password, method='scrypt', salt_length=3)
    data["password"]=password_hash

    users=mongo.db.users
    users.insert_one(data)
    return jsonify({"message": "User Registered"}), 200

getemail=None
@app.route("/login", methods=["POST"])
def login():
    global getemail
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    users = mongo.db.users
    user = users.find_one({"email": email})

    if not user:
        return jsonify({"message": "User not found"}), 200

    stored_password_hash = user["password"]

    if check_password_hash(stored_password_hash, password):
        token_payload = {"email": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=4)}
        jwt_token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
        if(jwt_token):
            getemail=email
        name=user['name']  
        # print(name)
        return jsonify({"token": jwt_token,"message":"Logged in Successfully","name":name}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 200


# //====================from here chat start=================

@app.route("/", methods=["GET"])
def index():
    return "API is working fine.."

def generate_response(prompt):

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Act as a parenting influencer. You provide solutions to all parenting problems, you have to answer in the language in which the user asks you the question. While answering to them, please reply as a human not as a machine. Try to replicate the tone of example and add some emoji according to question."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

@socketio.on('message')
def handle_message(prompt):
    global getemail
    chats=mongo.db.chats
    chats.insert_one({"mail":getemail,"chat":{ "content": prompt, "sent": True }})
    response = generate_response(prompt)
    emit('receive', response)  
    users = mongo.db.users
    user = users.find_one({"email": getemail})
    # print(user)
    if user:
        print(getemail)
    chats=mongo.db.chats
    chats.insert_one({"mail":getemail,"chat":{ "content": response, "sent": False }})

    return

@app.route("/getchat", methods=["GET"])
def getChat():
    global getemail
    chats = mongo.db.chats
    chat_documents = chats.find({"mail": getemail})
    chat_list = [chat_doc["chat"] for chat_doc in chat_documents]

    return jsonify(chat_list)

if __name__ == '__main__':
    socketio.run(app, debug=True) 
