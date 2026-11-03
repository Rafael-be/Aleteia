"""Persistência dos dados de negócio vinculados a usuários do Firebase."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.utils.timing import timed
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.database import Database


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

    @timed("sincronizar_usuario_firebase")
    def sincronizar_usuario_firebase(self, firebase_uid: str, email: str | None) -> dict:
        """Cria, no primeiro login, o perfil de negócio do usuário Firebase."""
        collection = self._obter_colecao()

        documento = {
            "firebase_uid": firebase_uid,
            "plano": "gratuito",
            "limite_diario_perguntas": 10,
            "uso_diario": {"data": "", "perguntas_feitas": 0, "tokens_usados": 0},
            "criado_em": datetime.now(timezone.utc),
        }
        update = {"$setOnInsert": documento}
        if email:
            update['$set'] = {'email': email.strip().lower()}
        try:
            return collection.find_one_and_update(
                {"firebase_uid": firebase_uid}, update,
                upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            # Concurrent first requests may race on the unique UID index.
            usuario = collection.find_one({'firebase_uid': firebase_uid})
            if usuario is None:
                raise
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
