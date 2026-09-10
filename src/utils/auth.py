"""Funções compartilhadas de autenticação com Firebase."""

from flask import Request, request
from firebase_admin import auth as firebase_auth


def obter_uid_do_token_firebase(req: Request = request) -> tuple[str | None, bool | None]:
    """Verifica o token Firebase e retorna ``(uid, email_verificado)``."""
    header = req.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, None
    token = header.removeprefix("Bearer ").strip()
    if not token:
        return None, None
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded.get("uid"), decoded.get("email_verified", False)
    except Exception:
        return None, None
