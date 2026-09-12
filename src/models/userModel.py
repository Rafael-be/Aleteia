"""Persistência dos dados de negócio vinculados a usuários do Firebase."""

from datetime import date, datetime, timezone

from pymongo import ReturnDocument


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
        if not hasattr(db, "get_database"):
            self._conectar()

    def _conectar(self):
        """Obtém a coleção, tentando reconectar se a tentativa anterior falhou."""
        db = self.db.get_database() if hasattr(self.db, "get_database") else self.db
        if db is None:
            self.collection = None
            self.db_available = False
            self.db_error = getattr(self.db, "last_error", None) or "Banco de dados indisponível"
            return None
        try:
            self.collection = db[self.COLLECTION_NAME]
            self.collection.create_index("firebase_uid", unique=True, sparse=True)
            self.collection.create_index("email", unique=True, sparse=True)
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
        if email:
            documento["email"] = email.strip().lower()
        return collection.find_one_and_update(
            {"firebase_uid": firebase_uid},
            {"$setOnInsert": documento},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def verificar_e_incrementar_uso(self, firebase_uid: str) -> tuple[bool, dict | None]:
        """Aplica o limite diário de perguntas e incrementa o uso de modo atômico."""
        collection = self._obter_colecao()

        hoje = date.today().isoformat()
        usuario = collection.find_one({"firebase_uid": firebase_uid})
        if not usuario:
            return False, None

        if usuario.get("uso_diario", {}).get("data") != hoje:
            collection.update_one(
                {"firebase_uid": firebase_uid},
                {"$set": {"uso_diario": {"data": hoje, "perguntas_feitas": 0, "tokens_usados": 0}}},
            )

        usuario = collection.find_one_and_update(
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
        collection = self._obter_colecao()
        collection.update_one(
            {"firebase_uid": firebase_uid},
            {"$inc": {"uso_diario.tokens_usados": max(0, int(tokens_gastos))}},
        )
