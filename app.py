from flask import Flask, render_template
from pymongo import MongoClient
from src.routes.userRoutes import user_routes

app = Flask(__name__, template_folder="public")

client = MongoClient("mongodb://localhost:27017/Aleteia")
db = client["Cadastro"]

app.register_blueprint(user_routes(db))

@app.route("/cadastro")
def cadastro():
    return render_template("cadastroTeste/cadstrotemplate.html")

@app.route("/")
def index():
    return render_template("main/main.html")

@app.route("/login")
def login():
    return render_template("login/login.html")

if __name__ == "__main__":
    app.run(debug=True)