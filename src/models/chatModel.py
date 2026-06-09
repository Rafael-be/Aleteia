from datetime import datetime

class ChatModel:
    COLLECTION_NAME = "chats"

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]

    def save_prompt(self, user_id: str, prompt: str) -> dict:
        """Salva um prompt no banco e retorna o documento inserido."""
        doc = {
            "user_id": user_id,
            "prompt": prompt,
            "created_at": datetime.utcnow()
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        doc["created_at"] = doc["created_at"].isoformat()
        return doc

    def get_prompts_by_user(self, user_id: str) -> list:
        """Retorna todos os prompts de um usuário, do mais recente ao mais antigo."""
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