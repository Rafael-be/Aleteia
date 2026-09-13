"""
Módulo de Histórico de Chat.

Gerencia o armazenamento e a recuperação de mensagens trocadas entre o
usuário e a IA (prompt + resposta), agrupadas por conversa, usando uma
coleção dedicada no MongoDB.
"""

from datetime import datetime
import re


class ChatModel:
    """
    Modelo para gerenciamento de mensagens e conversas de chat no MongoDB.
    """

    COLLECTION_NAME = "chats"

    def __init__(self, db):
        self.db = db
        self.collection = None
        self.db_available = False
        self.db_error = None

        # Uma instância de Database direta continua suportada; com o provider
        # da aplicação, a primeira tentativa acontece apenas quando necessária.
        if not hasattr(db, "get_database"):
            self._conectar()

    def _conectar(self):
        """Obtém a coleção e atualiza o estado a cada nova tentativa."""
        db = self.db.get_database() if hasattr(self.db, "get_database") else self.db
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
        if not self.db_available or self.collection is None:
            self._conectar()
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")
        return self.collection

    def save_mensagem(self, firebase_uid: str, conversa_id: str, prompt: str, resposta: str) -> dict:
        """
        Salva uma troca completa (prompt do usuário + resposta da IA) no banco.

        :param user_id: ID do usuário autenticado.
        :param conversa_id: ID que agrupa todas as mensagens de uma mesma conversa.
        :param prompt: Texto enviado pelo usuário.
        :param resposta: Texto retornado pela IA.
        :return: Documento salvo, com _id em string e created_at em ISO.
        """
        collection = self._obter_colecao()

        doc = {
            "firebase_uid": firebase_uid,
            "conversa_id": conversa_id,
            "prompt": prompt,
            "resposta": resposta,
            "created_at": datetime.utcnow(),
        }
        result = collection.insert_one(doc)

        doc["_id"] = str(result.inserted_id)
        doc["created_at"] = doc["created_at"].isoformat()
        return doc

    def get_mensagens_por_conversa(self, firebase_uid: str, conversa_id: str) -> list:
        """
        Retorna todas as mensagens de uma conversa específica, em ordem cronológica.

        :param conversa_id: ID da conversa a ser buscada.
        :return: Lista de documentos (prompt + resposta) daquela conversa.
        """
        collection = self._obter_colecao()

        cursor = collection.find(
            {"firebase_uid": firebase_uid, "conversa_id": conversa_id},
            {"_id": 1, "prompt": 1, "resposta": 1, "created_at": 1}
        ).sort("created_at", 1)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["created_at"] = doc["created_at"].isoformat()
            results.append(doc)

        return results

    def apagar_conversa(self, firebase_uid: str, conversa_id: str) -> int:
        """Apaga todas as mensagens de uma conversa pertencente ao usuário."""
        collection = self._obter_colecao()
        resultado = collection.delete_many({
            "firebase_uid": firebase_uid,
            "conversa_id": conversa_id,
        })
        return resultado.deleted_count

    def pesquisar_conversas(self, firebase_uid: str, termo: str) -> list:
        """Busca conversas do usuário pelo conteúdo de prompts e respostas."""
        collection = self._obter_colecao()
        termo_escapado = re.escape(termo)
        pipeline = [
            {"$match": {
                "firebase_uid": firebase_uid,
                "$or": [
                    {"prompt": {"$regex": termo_escapado, "$options": "i"}},
                    {"resposta": {"$regex": termo_escapado, "$options": "i"}},
                ],
            }},
            {"$sort": {"created_at": 1}},
            {"$group": {
                "_id": "$conversa_id",
                "prompt": {"$first": "$prompt"},
                "resposta": {"$first": "$resposta"},
                "created_at": {"$first": "$created_at"},
            }},
            {"$sort": {"created_at": -1}},
        ]
        return [
            {
                "_id": doc["_id"],
                "prompt": doc["prompt"],
                "created_at": doc["created_at"].isoformat(),
            }
            for doc in collection.aggregate(pipeline)
        ]

    def get_conversas_por_usuario(self, firebase_uid: str) -> list:
        """
        Retorna uma linha por conversa do usuário (para popular a sidebar),
        usando a primeira mensagem de cada conversa como prévia/título.

        :param user_id: ID do usuário autenticado.
        :return: Lista de dicionários {"_id": conversa_id, "prompt": primeiro_prompt,
                 "created_at": ...}, ordenada da conversa mais recente para a mais antiga.
        """
        collection = self._obter_colecao()

        pipeline = [
            {"$match": {"firebase_uid": firebase_uid}},
            {"$sort": {"created_at": 1}},
            {"$group": {
                "_id": "$conversa_id",
                "prompt": {"$first": "$prompt"},
                "created_at": {"$first": "$created_at"}
            }},
            {"$sort": {"created_at": -1}}
        ]

        results = []
        for doc in collection.aggregate(pipeline):
            results.append({
                "_id": doc["_id"],
                "prompt": doc["prompt"],
                "created_at": doc["created_at"].isoformat()
            })

        return results
