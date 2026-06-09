from flask import Blueprint
from src.controller.chatController import ChatController

def chat_routes(db):
    chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")
    controller = ChatController(db)

    chat_bp.add_url_rule("/prompt",  view_func=controller.save_prompt,  methods=["POST"])
    chat_bp.add_url_rule("/prompts", view_func=controller.get_prompts,   methods=["GET"])

    return chat_bp