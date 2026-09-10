"""Sincronização do perfil de negócio após a autenticação pelo Firebase."""

from firebase_admin import auth as firebase_auth
from flask import jsonify, request

from src.models.userModel import UserModel
from src.utils.auth import obter_uid_do_token_firebase


class AuthController:
    def __init__(self, db):
        self.user_model = UserModel(db)

    def sincronizar_usuario(self):
        """Encontra ou cria o documento Mongo associado ao UID do Firebase."""
        uid, _ = obter_uid_do_token_firebase(request)
        if not uid:
            return jsonify({"error": "Token inválido."}), 401
        try:
            email = firebase_auth.get_user(uid).email
            self.user_model.sincronizar_usuario_firebase(uid, email)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception:
            return jsonify({"error": "Não foi possível sincronizar o usuário."}), 503
        return jsonify({"ok": True}), 200
