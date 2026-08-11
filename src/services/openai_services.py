"""
Módulo de Serviço da OpenAI (ChatGPT).

Responsável por montar o histórico de mensagens no formato esperado pela
API da OpenAI e obter a resposta da Aleteia para um novo prompt.

Este serviço substitui o gemini_services.py no fluxo ativo do chat, mas não
o remove: o gemini_services.py continua no projeto, apenas sem ser chamado
por nenhuma rota registrada (ver src/routes/chatRoutes.py e app.py).
"""

import os
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

BASE_DIR = Path(__file__).resolve().parents[2]
example_env = BASE_DIR / "Exemplo.env"
if example_env.exists():
    load_dotenv(example_env, override=False)

project_env = BASE_DIR / ".env"
if project_env.exists():
    load_dotenv(project_env, override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Você é a Aleteia, uma inteligência artificial brasileira especializada em
verificação de fatos (fact-checking) de notícias e informações.

Regras:
- Responda SEMPRE em português do Brasil
- Comece a resposta com o veredicto em negrito
- Cite as fontes que embasam sua resposta, quando existirem
- Se não encontrar informação suficiente, declare INCONCLUSIVO
- Jamais invente fatos
- Mantenha tom neutro e jornalístico, sem opiniões políticas
- Se a mensagem não for uma notícia verificável, peça educadamente que o
  usuário envie uma afirmação para checar

Formato obrigatório da resposta:
**Veredicto:** [VERDADEIRO / FALSO / PARCIALMENTE VERDADEIRO / INCONCLUSIVO]

**Análise:** [Explicação em 1 a 4 parágrafos]

**Fontes consultadas:** [Liste as fontes encontradas, se houver]"""


def obter_resposta(mensagem: str, historico: list[dict[str, str]] | None = None) -> tuple[str, int]:
    """
    Envia o prompt do usuário para a OpenAI, junto do histórico da conversa,
    e retorna o texto da resposta e a quantidade de tokens gastos na chamada.

    :param mensagem: Texto novo enviado pelo usuário.
    :param historico: Lista de mensagens anteriores no formato
                       [{"role": "user"|"assistant", "content": "..."}].
    :return: Tupla (texto_resposta, tokens_usados).
    :raises RuntimeError: Se a chamada à API falhar.
    """
    mensagens: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    mensagens.extend(cast(list[ChatCompletionMessageParam], historico or []))
    mensagens.append({"role": "user", "content": mensagem})

    try:
        resultado = client.chat.completions.create(
            model=MODEL_NAME,
            messages=mensagens,
        )
    except Exception as exc:
        print(f"[OpenAI] Erro ao gerar resposta: {exc}")
        raise RuntimeError("Não foi possível processar a resposta da IA.") from exc

    texto = resultado.choices[0].message.content or "Não foi possível gerar uma resposta."
    tokens_usados = resultado.usage.total_tokens if resultado.usage else 0
    return texto, tokens_usados
