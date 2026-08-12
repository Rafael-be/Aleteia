"""
Módulo de Serviço da OpenAI (ChatGPT).

Usa a Responses API (não a Chat Completions) porque é ela que dá acesso à
ferramenta de busca na web — sem isso, o modelo responde só com o
conhecimento do treinamento, sem verificar nada em tempo real.
"""

import os
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for env_path in (PROJECT_ROOT / ".env", PROJECT_ROOT / "Exemplo.env"):
    if env_path.exists():
        load_dotenv(env_path, override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")

REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "high")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

_MODELOS_DE_RACIOCINIO = ("o1", "o3", "o4", "gpt-5")


def _e_modelo_de_raciocinio(nome_modelo: str) -> bool:
    return nome_modelo.startswith(_MODELOS_DE_RACIOCINIO)


SYSTEM_PROMPT = """Você é a Aleteia, uma inteligência artificial brasileira especializada em
verificação de fatos (fact-checking) de notícias e informações.

Seu trabalho:
1. Analisar a notícia ou afirmação enviada pelo usuário
2. Usar a ferramenta de busca na web para verificar a veracidade com informações atuais
3. Dar um veredicto claro e embasado em fontes reais

Regras:
- Responda SEMPRE em português do Brasil
- Comece a resposta com o veredicto em negrito
- Cite as fontes que embasam sua resposta
- Se não encontrar informação suficiente, declare INCONCLUSIVO
- Jamais invente fatos — use apenas o que encontrou na busca
- Mantenha tom neutro e jornalístico, sem opiniões políticas
- Se a mensagem não for uma notícia verificável, peça educadamente que o
  usuário envie uma afirmação para checar

Formato obrigatório da resposta:
**Veredicto:** [VERDADEIRO / FALSO / PARCIALMENTE VERDADEIRO / INCONCLUSIVO]

**Análise:** [Explicação em 1 a 4 parágrafos]

**Fontes consultadas:** [Liste as fontes encontradas]"""


def obter_resposta(mensagem: str, historico: list[dict[str, str]] | None = None) -> tuple[str, int]:
    """
    Envia o prompt do usuário à OpenAI (Responses API), com a ferramenta de
    busca na web habilitada, e retorna a resposta + tokens gastos.

    :param mensagem: Texto novo enviado pelo usuário.
    :param historico: Lista de mensagens anteriores no formato
                       [{"role": "user"|"assistant", "content": "..."}].
    :return: Tupla (texto_resposta, tokens_usados).
    :raises RuntimeError: Se a chamada à API falhar.
    """
    entrada = [{"role": "system", "content": SYSTEM_PROMPT}]
    entrada.extend(historico or [])
    entrada.append({"role": "user", "content": mensagem})

    parametros_extra = {}
    if _e_modelo_de_raciocinio(MODEL_NAME):
        parametros_extra["reasoning"] = {"effort": REASONING_EFFORT}
    else:
        parametros_extra["temperature"] = TEMPERATURE

    try:
        resultado = client.responses.create(
            model=MODEL_NAME,
            input=cast(list, entrada),
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            **parametros_extra,
        )
    except Exception as exc:
        print(f"[OpenAI] Erro ao gerar resposta: {exc}")
        raise RuntimeError("Não foi possível processar a resposta da IA.") from exc

    texto = resultado.output_text or "Não foi possível gerar uma resposta."
    tokens_usados = resultado.usage.total_tokens if resultado.usage else 0
    return texto, tokens_usados