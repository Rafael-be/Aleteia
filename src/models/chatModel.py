"""
Módulo de Histórico de Chat.

Este módulo gerencia o armazenamento e a recuperação de prompts de texto
enviados pelos usuários, utilizando uma coleção dedicada no MongoDB.
"""

from datetime import datetime


class ChatModel:
    """
    Modelo para gerenciamento de mensagens e prompts de chat no MongoDB.
    """

    COLLECTION_NAME = "chats"

    def __init__(self, db):
        """
        Inicializa o modelo com a instância do banco de dados.

        :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
        """
        self.collection = db[self.COLLECTION_NAME]

    def save_prompt(self, user_id: str, prompt: str) -> dict:
        """
        Salva um prompt no banco e retorna o documento inserido.

        :param user_id: ID único do usuário que enviou o prompt.
        :param prompt: O texto do prompt enviado pelo usuário.
        :return: Dicionário representando o documento salvo (com _id em string 
                 e data formatada em ISO).
        """
        doc = {
            "user_id": user_id,
            "prompt": prompt,
            "created_at": datetime.utcnow()
        }
        result = self.collection.insert_one(doc)
        
        # Formata os dados para o retorno do cliente
        doc["_id"] = str(result.inserted_id)
        doc["created_at"] = doc["created_at"].isoformat()
        return doc

    def get_prompts_by_user(self, user_id: str) -> list:
        """
        Retorna todos os prompts de um usuário, ordenados do mais recente ao mais antigo.

        :param user_id: ID único do usuário para busca.
        :return: Lista de dicionários contendo os prompts e metadados do usuário.
        """
        cursor = self.collection.find(
            {"user_id": user_id},
            {"_id": 1, "prompt": 1, "created_at": 1}
        ).sort("created_at", -1)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["created_at"] = doc["created_at"].isoformat()
            results.append(doc)
            
        return results