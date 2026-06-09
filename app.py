from flask import Flask, render_template
from pymongo import MongoClient
from src.routes.userRoutes import user_routes
from dotenv import load_dotenv
from src.routes.chatRoutes import chat_routes
import os

load_dotenv()

app = Flask(__name__, template_folder="public", static_folder='.', static_url_path='')

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]

app.register_blueprint(user_routes(db))

app.register_blueprint(chat_routes(db)) 

@app.route("/cadastro")
def cadastro():
    return render_template("cadastroTeste/cadastro.html")

@app.route("/")
def index():
    return render_template("main/main-desktop.html")

@app.route("/chat")
def logado():
    return render_template("chat/chatIndex.html")

@app.route("/login")
def login_page():
    return render_template("login/login.html")



if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)
