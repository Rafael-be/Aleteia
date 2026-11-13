"""Authentication profile synchronization and controlled legacy migration."""

import logging
import re

from firebase_admin import auth as firebase_auth
from firebase_admin._auth_utils import UserNotFoundError
from flask import g, jsonify, request
from pymongo.errors import PyMongoError

from src.models.userModel import IdentityConflictError, UserModel
from src.utils.auth import obter_uid_do_token_firebase
from src.utils.migration_rate_limit import legacy_migration_limiter


class AuthController:
    def __init__(self, db):
        self.user_model = UserModel(db)

    def sincronizar_usuario(self):
        """Create or refresh only the profile belonging to the token UID."""
        uid, email_verificado = obter_uid_do_token_firebase(request)
        if not uid:
            return jsonify({"error": "Token invalido."}), 401
        if not email_verificado:
            return jsonify(code="email_unverified", message="Email confirmation is required.", error="Email confirmation is required."), 403
        try:
            self.user_model.sincronizar_usuario_firebase(uid, g.firebase_claims.get("email"))
        except IdentityConflictError:
            return jsonify(code="identity_recovery_required", message="Identity recovery is required.", error="Identity recovery is required."), 409
        except (RuntimeError, PyMongoError) as exc:
            logging.getLogger(__name__).warning(
                "auth_sync_failed request_id=%s error_type=%s error_code=%s",
                getattr(g, "request_id", "unknown"), type(exc).__name__, getattr(exc, "code", None))
            return jsonify({"error": "Perfil temporariamente indisponivel."}), 503
        except Exception as exc:
            logging.getLogger(__name__).error(
                "auth_sync_unexpected request_id=%s error_type=%s",
                getattr(g, "request_id", "unknown"), type(exc).__name__)
            return jsonify(code="internal_error", message="Unexpected synchronization failure.", error="Unexpected synchronization failure."), 500
        return jsonify({"ok": True}), 200

    def migrar_usuario_legado(self):
        """Migrate only after legacy-password and Firebase-identity proof.

        A missing Firebase account is created from the password just supplied by
        its proven legacy owner. If Firebase already has the address, a valid
        token for that exact Firebase UID is required as a second proof.
        """
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or not isinstance(dados.get("email"), str) or not isinstance(dados.get("senha"), str):
            return jsonify(code="invalid_payload", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 400
        email = self.user_model.normalizar_email(dados["email"])
        senha = dados["senha"]
        if not email or len(email) > 254 or not senha or len(senha) > 1024:
            return jsonify(code="invalid_credentials", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 401
        if not legacy_migration_limiter.allow(request.remote_addr, email):
            return jsonify(code="migration_rate_limited", message="Please wait before trying again.", error="Please wait before trying again."), 429
        try:
            documento = self.user_model.validar_credenciais_legadas(email, senha)
            try:
                firebase_user = firebase_auth.get_user_by_email(email)
                firebase_exists = True
            except UserNotFoundError:
                if documento is None:
                    return jsonify(code="invalid_credentials", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 401
                firebase_user = firebase_auth.create_user(email=email, password=senha, email_verified=False)
                firebase_exists = False

            uid, _ = obter_uid_do_token_firebase(request)
            firebase_email = self.user_model.normalizar_email(getattr(g, "firebase_claims", {}).get("email"))
            if firebase_exists and (uid != firebase_user.uid or firebase_email != email):
                # Deliberately indistinguishable from an invalid legacy login:
                # callers cannot enumerate Firebase accounts by email.
                return jsonify(code="invalid_credentials", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 401

            if documento is None:
                # Google or an existing Firebase identity may prove control of
                # its current account, but must also prove the old bcrypt
                # password. A previous UID is replaced only once Firebase says
                # it no longer exists.
                documento = self.user_model.validar_prova_recuperacao(email, senha)
                if documento is None or not documento.get("firebase_uid"):
                    return jsonify(code="invalid_credentials", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 401
                try:
                    firebase_auth.get_user(documento["firebase_uid"])
                    return jsonify(code="identity_recovery_required", message="Identity recovery is required.", error="Identity recovery is required."), 409
                except UserNotFoundError:
                    vinculado = self.user_model.atualizar_uid_desatualizado(documento, firebase_user.uid, email)
            else:
                vinculado = self.user_model.vincular_usuario_legado(
                    documento, firebase_user.uid, email,
                    "legacy_password_and_firebase_proof" if firebase_exists else "legacy_password_and_firebase_creation")
            if vinculado is None:
                raise IdentityConflictError("legacy_document_changed")
        except IdentityConflictError as exc:
            logging.getLogger(__name__).warning(
                "legacy_migration_conflict request_id=%s error_type=%s",
                getattr(g, "request_id", "unknown"), type(exc).__name__)
            return jsonify(code="identity_recovery_required", message="Identity recovery is required.", error="Identity recovery is required."), 409
        except (PyMongoError, RuntimeError) as exc:
            logging.getLogger(__name__).warning(
                "legacy_migration_database_failed request_id=%s error_type=%s error_code=%s",
                getattr(g, "request_id", "unknown"), type(exc).__name__, getattr(exc, "code", None))
            return jsonify(code="database_unavailable", message="Database temporarily unavailable.", error="Database temporarily unavailable."), 503
        except Exception as exc:
            logging.getLogger(__name__).error(
                "legacy_migration_failed request_id=%s error_type=%s",
                getattr(g, "request_id", "unknown"), type(exc).__name__)
            return jsonify(code="migration_unavailable", message="Unable to complete sign-in.", error="Unable to complete sign-in."), 500
        return jsonify({"ok": True, "email_verification_required": not firebase_user.email_verified}), 200

    def validar_email(self):
        """Local syntax validation; Firebase confirms mailbox ownership."""
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or not isinstance(dados.get("email"), str):
            return jsonify(code="invalid_payload", message="Informe um e-mail valido.", error="Informe um e-mail valido."), 400
        email = dados["email"].strip()
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return jsonify({"error": "Informe um e-mail valido."}), 400
        return jsonify({"status": "aceito", "checagem_disponivel": False}), 200
