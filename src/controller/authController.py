"""Sincronização do perfil de negócio após a autenticação pelo Firebase."""

from flask import jsonify, request, g
import re

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
            email = g.firebase_claims.get('email')
            self.user_model.sincronizar_usuario_firebase(uid, email)
        except RuntimeError:
            return jsonify({"error": "Perfil temporariamente indisponivel."}), 503
        except Exception:
            return jsonify({"error": "Não foi possível sincronizar o usuário."}), 503
        return jsonify({"ok": True}), 200

    def validar_email(self):
        """Validação sintática local; Firebase confirma o controle da caixa."""
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or not isinstance(dados.get('email'), str):
            return jsonify(code='invalid_payload', message='Informe um e-mail válido.', error='Informe um e-mail válido.'), 400
        email = dados['email'].strip()
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            return jsonify({"error": "Informe um e-mail válido."}), 400

        return jsonify({
            "status": "aceito",
            # Preserva o contrato do cadastro sem consulta externa.
            "checagem_disponivel": False,
        }), 200
