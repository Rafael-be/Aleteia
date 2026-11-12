"""Integração resiliente com a API de reputação de e-mail da Abstract."""

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

LOGGER = logging.getLogger(__name__)
ABSTRACT_EMAIL_URL = "https://emailreputation.abstractapi.com/v1/"
TIMEOUT_SECONDS = 4


def _incerto(motivo: str) -> dict:
    return {"status": "incerto", "motivo": motivo}


def _valor_booleano(valor):
    """Lê tanto os booleanos atuais quanto o formato ``{value: bool}`` legado."""
    return valor.get("value") if isinstance(valor, dict) else valor


def verificar_email_existe(email: str) -> dict:
    """Traduz a resposta da Abstract em confirmado, rejeitado ou incerto.

    Problemas de rede, quota e respostas inesperadas nunca sobem para o
    controller: a validação é apenas uma ajuda de UX, não um bloqueio externo.
    """
    api_key = os.getenv("ABSTRACT_EMAIL_API_KEY")
    if not api_key:
        return _incerto("api_nao_configurada")

    query = urlencode({"api_key": api_key, "email": email})
    try:
        with urlopen(f"{ABSTRACT_EMAIL_URL}?{query}", timeout=TIMEOUT_SECONDS) as resposta:
            if resposta.status != 200:
                return _incerto("api_indisponivel")
            dados = json.load(resposta)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        LOGGER.info("Validação de e-mail da Abstract indisponível: %s", type(exc).__name__)
        return _incerto("api_indisponivel")

    entregabilidade = dados.get("email_deliverability", {})
    status = str(entregabilidade.get("status", dados.get("deliverability", ""))).lower()
    qualidade = dados.get("email_quality", {})
    catch_all = _valor_booleano(qualidade.get("is_catchall", dados.get("is_catchall_email")))

    if catch_all:
        return _incerto("dominio_catch_all")
    if status in {"deliverable", "true"}:
        return {"status": "confirmado", "motivo": "entregavel"}
    if status in {"undeliverable", "false"}:
        return {"status": "rejeitado", "motivo": "nao_entregavel"}
    return _incerto("resultado_inconclusivo")
