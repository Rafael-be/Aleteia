from flask import Flask, render_template, request, redirect
from pymongo import MongoClient

# Avisa que a pasta de templates agora se chama 'public'
app = Flask(__name__, template_folder='public')

# Configuração da Conexão (troque pela sua URL se usar o MongoDB Atlas)
client = MongoClient("mongodb://localhost:27017/")
db = client["Cadastro"]  # Nome do banco de dados
colecao = db["Usuario"]    # Nome da coleção (tabela)

@app.route('/')
def index():
    return render_template('cadastroTeste/cadastro.html')

@app.route('/enviar', methods=['POST'])
def enviar():
    # Coleta os dados do formulário HTML
    nome = request.form.get('nome')
    email = request.form.get('email')

    # Salva no MongoDB
    if nome and email:
        colecao.insert_one({"nome": nome, "email": email})
    
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)