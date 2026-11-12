"""Funções compartilhadas de autenticação com Firebase."""

from src.utils.timing import timed
from flask import Request, request, g
from firebase_admin import auth as firebase_auth


@timed("obter_uid_do_token_firebase")
def obter_uid_do_token_firebase(req: Request = request) -> tuple[str | None, bool | None]:
    """Verifica o token Firebase e retorna ``(uid, email_verificado)``."""
    header = req.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, None
    token = header.removeprefix("Bearer ").strip()
    if not token:
        return None, None
    try:
        decoded = getattr(g, 'firebase_claims', None)
        if decoded is None:
            decoded = firebase_auth.verify_id_token(token)
            g.firebase_claims = decoded
        return decoded.get("uid"), decoded.get("email_verified", False)
    except Exception:
        return None, None
