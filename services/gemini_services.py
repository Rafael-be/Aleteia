# src/services/gemini_service.py
import os

import google.generativeai as genai

#esse depende do modelo.py:
from services.modelo import SYSTEM_PROMPT, PARAMETROS

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Histórico de conversa por sessão { sessao_id: [mensagens] }
_sessoes: dict = {}

def obter_resposta(mensagem: str, sessao_id: str) -> str:
    """
    Recebe a notícia do usuário e retorna a análise da Aleteia.
    O Gemini busca automaticamente na web via google_search_retrieval.
    """
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(**PARAMETROS),
        tools="google_search_retrieval"  # busca na web nativa do Gemini
    )

    # Inicia sessão com os exemplos como histórico base, descomentar quando implementar exemplos
    #if sessao_id not in _sessoes:
    #   _sessoes[sessao_id] = list(EXEMPLOS)

    chat = model.start_chat(history=_sessoes[sessao_id])
    resultado = chat.send_message(mensagem)
    resposta = resultado.text

    # Persiste no histórico para manter contexto da conversa
    _sessoes[sessao_id].append({"role": "user",  "parts": [{"text": mensagem}]})
    _sessoes[sessao_id].append({"role": "model", "parts": [{"text": resposta}]})

    return resposta