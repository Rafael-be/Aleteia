"""Persistência dos dados de negócio vinculados a usuários do Firebase."""

from datetime import datetime, timezone, timedelta
import re
from uuid import uuid4

import bcrypt
from src.utils.timing import timed
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.database import Database


class IdentityConflictError(Exception):
    """A Firebase identity cannot safely be associated with a Mongo profile."""


class UserModel:
    """Modelo dos dados da aplicação; senhas e verificação ficam no Firebase."""

    COLLECTION_NAME = "users"

    def __init__(self, db):
        self.db = db
        self.collection = None
        self.db_available = False
        self.db_error = None

        # Mantém compatibilidade com uma instância de Database direta, mas
        # não fixa o resultado quando recebe o provider usado pela aplicação.
        if isinstance(db, Database) or not hasattr(db, "get_database"):
            self._conectar()

    def _conectar(self):
        """Obtém a coleção, tentando reconectar se a tentativa anterior falhou."""
        db = self.db if isinstance(self.db, Database) else (self.db.get_database() if hasattr(self.db, "get_database") else self.db)
        if db is None:
            self.collection = None
            self.db_available = False
            self.db_error = getattr(self.db, "last_error", None) or "Banco de dados indisponível"
            return None
        try:
            self.collection = db[self.COLLECTION_NAME]
            self.db_available = True
            self.db_error = None
            return self.collection
        except Exception as exc:
            self.collection = None
            self.db_available = False
            self.db_error = str(exc)
            return None

    def _obter_colecao(self):
        # Quando o Mongo estava fora no boot, esta chamada é repetida em cada
        # operação, permitindo que o Atlas volte sem reiniciar o Flask.
        if not self.db_available or self.collection is None:
            self._conectar()
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")
        return self.collection

    @staticmethod
    def normalizar_email(email: str | None) -> str | None:
        if not isinstance(email, str):
            return None
        email = email.strip().lower()
        return email or None

    @staticmethod
    def _email_filter(email: str) -> dict:
        # Legacy records can have mixed-case email values. Escape input so it
        # never becomes an executable regular expression.
        return {"email": {"$regex": "^" + re.escape(email) + "$", "$options": "i"}}

    @staticmethod
    def _padronizar_uso(documento: dict) -> dict:
        uso = documento.get("uso_diario")
        if isinstance(uso, dict):
            return {
                "data": str(uso.get("data") or ""),
                "perguntas_feitas": max(0, int(uso.get("perguntas_feitas") or 0)),
                "tokens_usados": max(0, int(uso.get("tokens_usados") or 0)),
            }
        # Legacy counters remain in their original fields for audit. They must
        # never become the current daily quota after a migration.
        return {
            "data": "",
            "perguntas_feitas": 0,
            "tokens_usados": 0,
        }

    @staticmethod
    def _campos_padronizados(documento: dict, firebase_uid: str, email: str, metodo: str) -> dict:
        limite = documento.get("limite_diario_perguntas", 10)
        try:
            limite = max(1, int(limite))
        except (TypeError, ValueError):
            limite = 10
        return {
            "firebase_uid": firebase_uid,
            "email": email,
            "plano": documento.get("plano") if isinstance(documento.get("plano"), str) else "gratuito",
            "limite_diario_perguntas": limite,
            "uso_diario": UserModel._padronizar_uso(documento),
            "criado_em": documento.get("criado_em") or documento.get("created_at") or datetime.now(timezone.utc),
            "schema_version": 2,
            "migracao": {"status": "linked", "method": metodo, "linked_at": datetime.now(timezone.utc)},
        }

    def _encontrar_legado(self, email: str) -> dict | None:
        return self._obter_colecao().find_one({
            "$and": [
                self._email_filter(email),
                {"$or": [{"firebase_uid": {"$exists": False}}, {"firebase_uid": None}]},
            ]
        })

    def validar_credenciais_legadas(self, email: str, senha: str) -> dict | None:
        """Return a legacy document only after a bcrypt proof of possession."""
        email = self.normalizar_email(email)
        if not email or not isinstance(senha, str):
            return None
        documento = self._encontrar_legado(email)
        password_hash = documento.get("password") if documento else None
        if not isinstance(password_hash, str) or documento.get("is_active") is False:
            return None
        try:
            return documento if bcrypt.checkpw(senha.encode("utf-8"), password_hash.encode("utf-8")) else None
        except (ValueError, TypeError):
            return None

    def validar_prova_recuperacao(self, email: str, senha: str) -> dict | None:
        """Find exactly one legacy-password match, even if it has an old UID."""
        email = self.normalizar_email(email)
        if not email or not isinstance(senha, str):
            return None
        documentos = list(self._obter_colecao().find(self._email_filter(email)).limit(3))
        validos = []
        for documento in documentos:
            password_hash = documento.get("password")
            if documento.get("is_active") is False or not isinstance(password_hash, str):
                continue
            try:
                if bcrypt.checkpw(senha.encode("utf-8"), password_hash.encode("utf-8")):
                    validos.append(documento)
            except (ValueError, TypeError):
                continue
        return validos[0] if len(validos) == 1 else None

    def vincular_usuario_legado(self, documento: dict, firebase_uid: str, email: str, metodo: str) -> dict | None:
        """Atomically bind the exact legacy document after identity proofs."""
        collection = self._obter_colecao()
        password_hash = documento.get("password")
        if not documento.get("_id") or not isinstance(password_hash, str):
            return None
        return collection.find_one_and_update(
            {"_id": documento["_id"], "password": password_hash,
             "$or": [{"firebase_uid": {"$exists": False}}, {"firebase_uid": None}]},
            {"$set": self._campos_padronizados(documento, firebase_uid, email, metodo)},
            return_document=ReturnDocument.AFTER,
        )

    def atualizar_uid_desatualizado(self, documento: dict, firebase_uid: str, email: str) -> dict | None:
        """Replace a proven orphaned UID without touching histories or _id."""
        antigo_uid = documento.get("firebase_uid")
        password_hash = documento.get("password")
        if not antigo_uid or not documento.get("_id") or not isinstance(password_hash, str):
            return None
        campos = self._campos_padronizados(documento, firebase_uid, email, "legacy_password_and_orphaned_uid")
        campos["migracao"]["previous_firebase_uid"] = antigo_uid
        try:
            return self._obter_colecao().find_one_and_update(
                {"_id": documento["_id"], "firebase_uid": antigo_uid, "password": password_hash},
                {"$set": campos}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc:
            raise IdentityConflictError("identity_constraint") from exc

    @timed("sincronizar_usuario_firebase")
    def sincronizar_usuario_firebase(self, firebase_uid: str, email: str | None) -> dict:
        """Cria, no primeiro login, o perfil de negócio do usuário Firebase."""
        collection = self._obter_colecao()
        email = self.normalizar_email(email)
        existente = collection.find_one({"firebase_uid": firebase_uid})
        if existente is not None:
            if not email:
                return existente
            return collection.find_one_and_update(
                {"_id": existente["_id"]}, {"$set": {"email": email}},
                return_document=ReturnDocument.AFTER)

        # Email similarity deliberately starts a recovery flow; it never
        # transfers a legacy profile to an unproven Firebase identity.
        if email:
            conflito = collection.find_one({
                "$and": [self._email_filter(email), {"firebase_uid": {"$ne": firebase_uid}}]
            })
            if conflito is not None:
                raise IdentityConflictError("identity_recovery_required")

        documento = {
            "firebase_uid": firebase_uid,
            "plano": "gratuito",
            "limite_diario_perguntas": 10,
            "uso_diario": {"data": "", "perguntas_feitas": 0, "tokens_usados": 0},
            "criado_em": datetime.now(timezone.utc),
        }
        update = {"$setOnInsert": documento}
        if email:
            update['$set'] = {'email': email}
        try:
            return collection.find_one_and_update(
                {"firebase_uid": firebase_uid}, update,
                upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            # Concurrent first requests may race on the unique UID index.
            usuario = collection.find_one({'firebase_uid': firebase_uid})
            if usuario is None:
                raise IdentityConflictError("identity_constraint")
            return usuario

    @timed("verificar_e_incrementar_uso")
    def verificar_e_incrementar_uso(self, firebase_uid: str) -> tuple[bool, dict | None]:
        """Atomic day rollover, short rate limit, quota reservation and per-user lease.

        Requires MongoDB 4.2+. No expired lease refunds: an interrupted worker may
        already have spent API credits. Fail closed until the lease expires.
        """
        collection = self._obter_colecao()
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        minute = now.strftime('%Y-%m-%dT%H:%M')
        reservation = uuid4().hex
        same_day = {'$eq': ['$uso_diario.data', today]}
        count = {'$cond': [same_day, {'$ifNull': ['$uso_diario.perguntas_feitas', 0]}, 0]}
        same_minute = {'$eq': ['$rate_minute', minute]}
        rate = {'$cond': [same_minute, {'$ifNull': ['$rate_count', 0]}, 0]}
        user = collection.find_one_and_update(
            {'firebase_uid': firebase_uid,
             '$and': [{'$or': [{'lease_until': {'$exists': False}}, {'lease_until': {'$lte': now}}]},
                      {'$expr': {'$lt': [count, '$limite_diario_perguntas']}},
                      {'$expr': {'$lt': [rate, 3]}}]},
            [{'$set': {
                'uso_diario': {'data': today, 'perguntas_feitas': {'$add': [count, 1]},
                              'tokens_usados': {'$cond': [same_day, {'$ifNull': ['$uso_diario.tokens_usados', 0]}, 0]}},
                'rate_minute': minute, 'rate_count': {'$add': [rate, 1]},
                'reservation_id': reservation, 'reservation_day': today,
                'lease_until': now + timedelta(seconds=180),
            }}], return_document=ReturnDocument.AFTER)
        if user is not None:
            return True, user
        user = collection.find_one({'firebase_uid': firebase_uid})
        if user:
            exhausted = (user.get('uso_diario', {}).get('data') == today and
                         user['uso_diario'].get('perguntas_feitas', 0) >= user.get('limite_diario_perguntas', 10))
            user['quota_reason'] = 'daily_quota_exceeded' if exhausted else 'rate_limited'
        return False, user

    @timed("finalizar_reserva")
    def finalizar_reserva(self, firebase_uid, reserva, sucesso):
        """Idempotent release/refund; never refund a different request or day."""
        if not reserva:
            return
        query = {'firebase_uid': firebase_uid, 'reservation_id': reserva['reservation_id']}
        update = {'$unset': {'lease_until': '', 'reservation_id': '', 'reservation_day': ''}}
        if not sucesso:
            query['uso_diario.data'] = reserva['reservation_day']
            update['$inc'] = {'uso_diario.perguntas_feitas': -1}
        self._obter_colecao().update_one(query, update)

    @timed("registrar_tokens_usados")
    def registrar_tokens_usados(self, firebase_uid: str, tokens_gastos: int) -> None:
        self._obter_colecao().update_one(
            {'firebase_uid': firebase_uid, 'uso_diario.data': datetime.now(timezone.utc).date().isoformat()},
            {'$inc': {'uso_diario.tokens_usados': max(0, int(tokens_gastos))}})
