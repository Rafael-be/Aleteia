"""
Módulo de Serviço da OpenAI (ChatGPT).

Usa a Responses API (não a Chat Completions) porque é ela que dá acesso à
ferramenta de busca na web — sem isso, o modelo responde só com o
conhecimento do treinamento, sem verificar nada em tempo real.
"""

import os
from typing import cast
from time import perf_counter
import logging

from src.services.chat_events import FiltroVeredito, etapa

from openai import OpenAI
from flask import g, has_request_context

from src import config  # loads local configuration without overriding deployment

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY') or 'not-configured',
                timeout=60.0, max_retries=0)
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5-mini")

REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium")
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
- Termine a resposta com o veredicto em negrito, sempre na última linha
- Nunca antecipe o campo Veredicto antes da análise e das fontes
- Cite as fontes que embasam sua resposta
- Se não encontrar informação suficiente, declare INCONCLUSIVO
- Jamais invente fatos — use apenas o que encontrou na busca
- Mantenha tom neutro e jornalístico, sem opiniões políticas
- Se a mensagem não for uma notícia verificável, peça educadamente que o
  usuário envie uma afirmação para checar

Formato obrigatório da resposta:
**Análise:** [Explicação em 1 a 4 parágrafos]

**Fontes consultadas:** [Liste as fontes encontradas]

**Veredicto:** [VERDADEIRO / FALSO / PARCIALMENTE VERDADEIRO / INCONCLUSIVO]

Inclua sempre o Veredicto, inclusive para mensagens não verificáveis (INCONCLUSIVO)."""


def transmitir_resposta(mensagem: str, historico: list[dict[str, str]] | None = None):
    """Traduz eventos da OpenAI para o contrato público do chat, sem raciocínio interno."""
    entrada = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Bound context independently of caller. Keep complete user/assistant pairs.
    contexto, tamanho = [], 0
    pares = [historico[i:i+2] for i in range(0, len(historico or []), 2)]
    for par in reversed(pares[-12:]):
        custo = sum(len(item.get('content', '')) for item in par)
        if tamanho + custo > 24000:
            break
        contexto[0:0] = par
        tamanho += custo
    entrada.extend(contexto)
    entrada.append({"role": "user", "content": mensagem})
    extras = ({"reasoning": {"effort": REASONING_EFFORT}}
              if _e_modelo_de_raciocinio(MODEL_NAME) else {"temperature": TEMPERATURE})
    filtro = FiltroVeredito()
    inicio = perf_counter()
    escrevendo = False
    yield etapa("analyzing", "Analisando a afirmação e o contexto...")
    try:
        with client.responses.create(
            model=MODEL_NAME, input=cast(list, entrada), tools=[{"type": "web_search"}],
            tool_choice="auto", stream=True, max_output_tokens=4096, max_tool_calls=3, store=False, **extras,
        ) as stream:
            for evento in stream:
                if perf_counter() - inicio > 110:
                    raise RuntimeError('Tempo limite de geração excedido.')
                tipo = evento.type
                if tipo in {"response.web_search_call.in_progress", "response.web_search_call.searching"}:
                    yield etapa("searching", "Pesquisando informações e fontes na web...")
                elif tipo == "response.web_search_call.completed":
                    yield etapa("evaluating", "Analisando as informações encontradas...")
                elif tipo == "response.output_item.added" and getattr(evento.item, "type", "") == "reasoning":
                    yield etapa("analyzing", "Analisando a afirmação e as evidências disponíveis...")
                elif tipo == "response.output_text.delta":
                    if not escrevendo:
                        yield etapa("writing", "Redigindo a resposta...")
                        escrevendo = True
                    trecho = filtro.adicionar(evento.delta)
                    if trecho:
                        yield {"type": "delta", "text": trecho}
                elif tipo == "response.completed":
                    restante = filtro.finalizar()
                    if restante:
                        yield {"type": "delta", "text": restante}
                    resultado = evento.response
                    if not resultado.output_text:
                        raise RuntimeError("A IA não retornou uma resposta em texto.")
                    yield {"type": "result", "text": resultado.output_text,
                           "tokens": resultado.usage.total_tokens if resultado.usage else 0}
                    return
                elif tipo in {"response.failed", "response.incomplete", "error"}:
                    raise RuntimeError("A geração da resposta foi interrompida. Tente novamente.")
        raise RuntimeError("A conexão com a IA terminou antes de concluir a resposta.")
    except Exception as exc:
        raise RuntimeError("Não foi possível concluir a resposta da IA. Tente novamente.") from exc
    finally:
        request_id = getattr(g, 'request_id', 'unknown') if has_request_context() else 'offline'
        logging.getLogger(__name__).info('phase=openai request_id=%s duration_ms=%.1f', request_id, (perf_counter()-inicio)*1000)


def obter_resposta(mensagem: str, historico: list[dict[str, str]] | None = None) -> tuple[str, int]:
    """Compatibilidade para consumidores que ainda precisam da resposta completa."""
    for evento in transmitir_resposta(mensagem, historico):
        if evento["type"] == "result":
            return evento["text"], evento["tokens"]
    raise RuntimeError("A IA não concluiu a resposta.")
