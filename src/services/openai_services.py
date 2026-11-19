"""OpenAI transport for the deterministic Aleteia evidence pipeline."""
import os
import logging
from collections.abc import Generator
from time import perf_counter
from typing import cast
from openai import OpenAI
from flask import g, has_request_context
from src import config
from src.services.analysis_service import analyze, CompleteAnswer, UsageLedger
from src.services.analysis_errors import log_failure
from src.services.chat_events import AnalysisEvent
from src.services.standard_service import standard_answer

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY') or 'not-configured',
                timeout=30.0, max_retries=0)
MODEL_NAME = os.getenv('OPENAI_MODEL', 'gpt-6-luna')


def transmitir_resposta(mensagem, historico=None, ledger=None, *, mode='standard', images=()) -> Generator[AnalysisEvent, None, None]:
    inicio = perf_counter()
    ledger = ledger or UsageLedger()
    options = {'images': images} if images else {}
    try:
        if mode == 'standard':
            yield from standard_answer(client, MODEL_NAME, mensagem, historico, ledger, **options)
        elif mode == 'experimental':
            for event in analyze(client, MODEL_NAME, mensagem, historico, ledger, **options):
                if event['type'] == 'result':
                    event['veredito']['mode'] = 'experimental'
                yield cast(AnalysisEvent, event)
        else:
            raise ValueError('Invalid response mode')
    except Exception as exc:
        raise log_failure(exc, 'pipeline') from exc
    finally:
        request_id = getattr(g, 'request_id', 'unknown') if has_request_context() else 'offline'
        logging.getLogger(__name__).info(
            'phase=analysis request_id=%s duration_ms=%.1f observed_tokens=%s calls=%s '
            'usage_unknown_calls=%s accounting_failed=%s',
            request_id, (perf_counter()-inicio)*1000, ledger.total, ledger.calls,
            max(0, ledger.calls-len(ledger.records)), ledger.failed_accounting)


def obter_resposta(mensagem, historico=None, ledger=None, *, mode='standard', images=()):
    options = {'images': images} if images else {}
    resposta = transmitir_resposta(mensagem, historico, ledger, mode=mode, **options)
    try:
        for evento in resposta:
            if evento['type'] == 'result':
                return CompleteAnswer(evento)
    finally:
        resposta.close()
    raise RuntimeError('A análise não foi concluída.')
