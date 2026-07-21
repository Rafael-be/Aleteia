"""
Módulo de Controlador de Usuário.

Este módulo gerencia as rotas da API relacionadas à autenticação,
incluindo registro de novos usuários, validação de credenciais
e login com geração de tokens JWT.
"""

import os
from datetime import datetime, timezone

import jwt
from flask import jsonify, request, session

from src.models.userModel import UserModel


class UserController:
    """
    Controlador de usuário.

    Responsável por lidar com as requisições HTTP de cadastro e login,
    fazendo a ponte entre o cliente da API e as regras de negócio do UserModel.
    """

    def __init__(self, db):
        """
        Inicializa o controlador com a instância do banco de dados.

        :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
        """
        self.user_model = UserModel(db)

    # ------------------------------------------------------------------
    # Cadastro
    # ------------------------------------------------------------------

    def register(self):
        """
        Endpoint POST /api/users/register.

        Cadastra um usuário novo no MongoDB. O e-mail é validado e
        normalizado pelo modelo, e a senha é armazenada com hash bcrypt.

        Body JSON esperado:
        {
            "email": "usuario@email.com",
            "password": "Senha123",
            "confirm_password": "Senha123"
        }

        :return: Uma tupla contendo o objeto JSON do Flask e o status code HTTP:
                 - 201: Usuário cadastrado com sucesso.
                 - 400: Corpo da requisição inválido ou campos obrigatórios ausentes.
                 - 422: Regra de negócio violada, como e-mail inválido, senha fraca,
                        e-mail duplicado ou senhas diferentes.
                 - 500: Erro interno no servidor.
        """
        print("REGISTER CHAMADO")

        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "Corpo da requisição inválido ou ausente."}), 400

            email = data.get("email", "").strip()
            password = data.get("password", "")
            confirm_password = data.get("confirm_password", "")

            if not email or not password or not confirm_password:
                return jsonify({"error": "Todos os campos são obrigatórios: email, password, confirm_password."}), 400

            result = self.user_model.create_user(email, password, confirm_password)

            # Inicia sessão server-side após cadastro
            session["user_id"] = result["id"]
            session["email"]   = email

            return jsonify({
                "message": "Usuário cadastrado com sucesso.",
                "user_id": result["id"]
            }), 201

        except ValueError as e:
            return jsonify({"error": str(e)}), 422

        except Exception as e:
            return jsonify({"error": "Erro interno no servidor.", "details": str(e)}), 500

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self):
        """
        Endpoint POST /api/users/login.

        Autentica um usuário existente e retorna um token JWT. Esse token deve
        ser salvo pelo frontend e enviado nas rotas protegidas no formato:
        Authorization: Bearer <token>

        Body JSON esperado:
        {
            "email": "usuario@email.com",
            "password": "Senha123"
        }

        :return: Uma tupla contendo o objeto JSON do Flask e o status code HTTP:
                 - 200: Login bem-sucedido, retorna o token JWT.
                 - 400: Corpo da requisição inválido ou campos obrigatórios ausentes.
                 - 401: Credenciais inválidas (e-mail ou senha incorretos).
                 - 403: Conta desativada.
                 - 422: Falha nas validações de formato.
                 - 500: Erro interno no servidor.
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "Corpo da requisição inválido ou ausente."}), 400

            email = data.get("email", "").strip()
            password = data.get("password", "")

            if not email or not password:
                return jsonify({"error": "E-mail e senha são obrigatórios."}), 400

            user = self.user_model.find_by_email(email)

            if not user:
                return jsonify({"error": "Credenciais inválidas."}), 401

            if not user.get("is_active", True):
                return jsonify({"error": "Conta desativada. Entre em contato com o suporte."}), 403

            if not self.user_model.check_password(password, user["password"]):
                return jsonify({"error": "Credenciais inválidas."}), 401

            token = self._generate_token(str(user["_id"]), user["email"])

            # Inicia sessão server-side
            session["user_id"] = str(user["_id"])
            session["email"]   = user["email"]

            return jsonify({
                "message": "Login realizado com sucesso.",
                "token": token
            }), 200

        except ValueError as e:
            return jsonify({"error": str(e)}), 422

        except Exception as e:
            return jsonify({"error": "Erro interno no servidor.", "details": str(e)}), 500

    # ------------------------------------------------------------------
    # Geração de Token JWT
    # ------------------------------------------------------------------

    def _generate_token(self, user_id: str, email: str) -> str:
        """
        Gera um token JWT assinado contendo os dados do usuário.

        :param user_id: ID único do usuário no MongoDB, usado como claim 'sub'.
        :param email: E-mail do usuário logado.
        :return: String representando o token JWT assinado.
        """
        secret_key = os.getenv("JWT_SECRET_KEY", "criptografia123")

        payload = {
            "sub": user_id,
            "email": email,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, secret_key, algorithm="HS256")
        return token
