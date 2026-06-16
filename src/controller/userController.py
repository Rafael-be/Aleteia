from flask import request, jsonify, session
from src.models.userModel import UserModel
from datetime import datetime, timezone
import jwt
import os


class UserController:
    """
    Controller de usuário.
    Responsável por lidar com as requisições de cadastro e login.
    """

    def __init__(self, db):
        self.user_model = UserModel(db)

    # ------------------------------------------------------------------
    # Cadastro
    # ------------------------------------------------------------------

    def register(self):
        print("REGISTER CHAMADO")

        """
        Endpoint de cadastro de usuário.

        Body JSON esperado:
        {
            "email": "usuario@email.com",
            "password": "Senha123",
            "confirm_password": "Senha123"
        }
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "Corpo da requisição inválido ou ausente."}), 400

            email = data.get("email", "").strip()
            password = data.get("password", "")
            confirm_password = data.get("confirm_password", "")

            # Verifica campos obrigatórios
            if not email or not password or not confirm_password:
                return jsonify({"error": "Todos os campos são obrigatórios: email, password, confirm_password."}), 400

            # Delega criação ao modelo (validações + hash + insert)
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
        Endpoint de login de usuário.

        Body JSON esperado:
        {
            "email": "usuario@email.com",
            "password": "Senha123"
        }

        Retorna um JWT token em caso de sucesso.
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "Corpo da requisição inválido ou ausente."}), 400

            email = data.get("email", "").strip()
            password = data.get("password", "")

            if not email or not password:
                return jsonify({"error": "E-mail e senha são obrigatórios."}), 400

            # Busca usuário no banco
            user = self.user_model.find_by_email(email)

            if not user:
                return jsonify({"error": "Credenciais inválidas."}), 401

            # Verifica se a conta está ativa
            if not user.get("is_active", True):
                return jsonify({"error": "Conta desativada. Entre em contato com o suporte."}), 403

            # Valida a senha
            if not self.user_model.check_password(password, user["password"]):
                return jsonify({"error": "Credenciais inválidas."}), 401

            # Gera o JWT token
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
        Gera um JWT token com os dados do usuário.

        :param user_id: ID do usuário no MongoDB.
        :param email: E-mail do usuário.
        :return: Token JWT assinado.
        """
        secret_key = os.getenv("JWT_SECRET_KEY", "criptografia123")

        payload = {
            "sub": user_id,
            "email": email,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, secret_key, algorithm="HS256")
        return token