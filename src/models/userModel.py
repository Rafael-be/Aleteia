"""Persistência dos dados de negócio vinculados a usuários do Firebase."""

from datetime import date, datetime, timezone

from pymongo import ReturnDocument


class UserModel:
    """Modelo dos dados da aplicação; senhas e verificação ficam no Firebase."""

    COLLECTION_NAME = "users"

    def __init__(self, db):
        self.collection = None
        self.db_available = False
        self.db_error = None
        if db is None:
            self.db_error = "Banco de dados indisponível"
            return
        try:
            self.collection = db[self.COLLECTION_NAME]
            self.collection.create_index("firebase_uid", unique=True)
            self.collection.create_index("email", unique=True, sparse=True)
            self.db_available = True
        except Exception as exc:
            self.db_error = str(exc)

    def sincronizar_usuario_firebase(self, firebase_uid: str, email: str | None) -> dict:
        """Cria, no primeiro login, o perfil de negócio do usuário Firebase."""
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")

        documento = {
            "firebase_uid": firebase_uid,
            "plano": "gratuito",
            "limite_diario_perguntas": 10,
            "uso_diario": {"data": "", "perguntas_feitas": 0, "tokens_usados": 0},
            "criado_em": datetime.now(timezone.utc),
        }
        if email:
            documento["email"] = email.strip().lower()
        return self.collection.find_one_and_update(
            {"firebase_uid": firebase_uid},
            {"$setOnInsert": documento},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def verificar_e_incrementar_uso(self, firebase_uid: str) -> tuple[bool, dict | None]:
        """Aplica o limite diário de perguntas e incrementa o uso de modo atômico."""
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")

        hoje = date.today().isoformat()
        usuario = self.collection.find_one({"firebase_uid": firebase_uid})
        if not usuario:
            return False, None

        if usuario.get("uso_diario", {}).get("data") != hoje:
            self.collection.update_one(
                {"firebase_uid": firebase_uid},
                {"$set": {"uso_diario": {"data": hoje, "perguntas_feitas": 0, "tokens_usados": 0}}},
            )

        usuario = self.collection.find_one_and_update(
            {
                "firebase_uid": firebase_uid,
                "uso_diario.data": hoje,
                "$expr": {"$lt": ["$uso_diario.perguntas_feitas", "$limite_diario_perguntas"]},
            },
            {"$inc": {"uso_diario.perguntas_feitas": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return usuario is not None, usuario

    def registrar_tokens_usados(self, firebase_uid: str, tokens_gastos: int) -> None:
        """Soma os tokens da resposta ao uso diário já aberto para o usuário."""
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")
        self.collection.update_one(
            {"firebase_uid": firebase_uid},
            {"$inc": {"uso_diario.tokens_usados": max(0, int(tokens_gastos))}},
        )
