"""Original single-generation path, without experimental extraction/scoring."""
import os
from threading import BoundedSemaphore
from time import monotonic
from src.services.standard_prompt import SYSTEM_PROMPT
from src.services.chat_events import FiltroVeredito, etapa, separar_veredito

_SLOTS = BoundedSemaphore(4)


def standard_answer(client, model, message, history, ledger):
    if not _SLOTS.acquire(blocking=False):
        raise RuntimeError('Generation capacity reached')
    try:
        context, size = [], 0
        pairs = [(history or [])[i:i+2] for i in range(0, len(history or []), 2)]
        for pair in reversed(pairs[-12:]):
            clean = [h for h in pair if h.get('role') in ('user', 'assistant')
                     and isinstance(h.get('content'), str)]
            cost = sum(len(h['content']) for h in clean)
            if size+cost > 24000:
                break
            context[0:0] = [{'role': h['role'], 'content': h['content']} for h in clean]
            size += cost
        inputs = [{'role': 'system', 'content': SYSTEM_PROMPT}, *context,
                  {'role': 'user', 'content': message}]
        extras = ({'reasoning': {'effort': os.getenv('OPENAI_REASONING_EFFORT', 'medium')}}
                  if model.startswith(('gpt-5', 'gpt-6', 'o1', 'o3', 'o4')) else
                  {'temperature': float(os.getenv('OPENAI_TEMPERATURE', '.1'))})
        filter_ = FiltroVeredito()
        started = monotonic()
        yield etapa('analyzing', 'Analisando a informação...')
        ledger.start('standard')
        with client.responses.create(model=model, input=inputs, tools=[{'type': 'web_search'}],
                tool_choice='auto', stream=True, max_output_tokens=5500, max_tool_calls=3,
                store=False, timeout=60, **extras) as stream:
            for event in stream:
                if monotonic()-started > 110:
                    raise RuntimeError('Generation deadline exceeded')
                if event.type in ('response.web_search_call.in_progress', 'response.web_search_call.searching'):
                    yield etapa('searching', 'Consultando informações na web...')
                elif event.type == 'response.output_text.delta':
                    chunk = filter_.adicionar(event.delta)
                    if chunk:
                        yield {'type': 'delta', 'text': chunk}
                elif event.type == 'response.completed':
                    response = event.response
                    ledger.record(response, 'standard')
                    if not response.output_text or response.status != 'completed':
                        raise RuntimeError('Incomplete generation')
                    chunk = filter_.finalizar()
                    if chunk:
                        yield {'type': 'delta', 'text': chunk}
                    _, verdict = separar_veredito(response.output_text)
                    verdict['mode'] = 'standard'
                    yield {'type': 'result', 'text': response.output_text,
                           'tokens': ledger.total, 'veredito': verdict, 'audit': None}
                    return
                elif event.type in ('response.failed', 'response.incomplete', 'error'):
                    if getattr(event, 'response', None) is not None:
                        ledger.record(event.response, 'standard')
                    raise RuntimeError('Generation interrupted')
        raise RuntimeError('Stream ended before completion')
    finally:
        _SLOTS.release()
