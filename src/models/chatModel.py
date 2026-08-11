"""
Módulo de Histórico de Chat.

Gerencia o armazenamento e a recuperação de mensagens trocadas entre o
usuário e a IA (prompt + resposta), agrupadas por conversa, usando uma
coleção dedicada no MongoDB.
"""

from datetime import datetime


class ChatModel:
    """
    Modelo para gerenciamento de mensagens e conversas de chat no MongoDB.
    """

    COLLECTION_NAME = "chats"

    def __init__(self, db):
        self.collection = None
        self.db_available = False
        self.db_error = None

        if db is None:
            self.db_error = "Banco de dados indisponível"
            return

        try:
            self.collection = db[self.COLLECTION_NAME]
            self.db_available = True
        except Exception as exc:
            self.db_error = str(exc)

    def save_mensagem(self, user_id: str, conversa_id: str, prompt: str, resposta: str) -> dict:
        """
        Salva uma troca completa (prompt do usuário + resposta da IA) no banco.

        :param user_id: ID do usuário autenticado.
        :param conversa_id: ID que agrupa todas as mensagens de uma mesma conversa.
        :param prompt: Texto enviado pelo usuário.
        :param resposta: Texto retornado pela IA.
        :return: Documento salvo, com _id em string e created_at em ISO.
        """
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")

        doc = {
            "user_id": user_id,
            "conversa_id": conversa_id,
            "prompt": prompt,
            "resposta": resposta,
            "created_at": datetime.utcnow(),
        }
        result = self.collection.insert_one(doc)

        doc["_id"] = str(result.inserted_id)
        doc["created_at"] = doc["created_at"].isoformat()
        return doc

    def get_mensagens_por_conversa(self, conversa_id: str) -> list:
        """
        Retorna todas as mensagens de uma conversa específica, em ordem cronológica.

        :param conversa_id: ID da conversa a ser buscada.
        :return: Lista de documentos (prompt + resposta) daquela conversa.
        """
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")

        cursor = self.collection.find(
            {"conversa_id": conversa_id},
            {"_id": 1, "prompt": 1, "resposta": 1, "created_at": 1}
        ).sort("created_at", 1)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["created_at"] = doc["created_at"].isoformat()
            results.append(doc)

        return results

    def get_conversas_por_usuario(self, user_id: str) -> list:
        """
        Retorna uma linha por conversa do usuário (para popular a sidebar),
        usando a primeira mensagem de cada conversa como prévia/título.

        :param user_id: ID do usuário autenticado.
        :return: Lista de dicionários {"_id": conversa_id, "prompt": primeiro_prompt,
                 "created_at": ...}, ordenada da conversa mais recente para a mais antiga.
        """
        if not self.db_available or self.collection is None:
            raise RuntimeError(self.db_error or "Banco de dados indisponível")

        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$sort": {"created_at": 1}},
            {"$group": {
                "_id": "$conversa_id",
                "prompt": {"$first": "$prompt"},
                "created_at": {"$first": "$created_at"}
            }},
            {"$sort": {"created_at": -1}}
        ]

        results = []
        for doc in self.collection.aggregate(pipeline):
            results.append({
                "_id": doc["_id"],
                "prompt": doc["prompt"],
                "created_at": doc["created_at"].isoformat()
            })

        return results