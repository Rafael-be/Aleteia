"""Observabilidade opcional, sem conteúdo de conversas ou credenciais."""

import os
from contextlib import nullcontext


_SENTRY = None


def _rate(value: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _scrub(value):
    if isinstance(value, dict):
        return {key: "[Filtered]" if key.lower() in {"authorization", "cookie", "set-cookie", "token", "password", "prompt", "resposta", "message"}
                else _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def configure_sentry(app) -> bool:
    """Inicializa o SDK somente quando há DSN; falhas nunca interrompem o app."""
    global _SENTRY
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        def before_send(event, _hint):
            event["request"] = _scrub(event.get("request", {}))
            event.get("request", {}).pop("data", None)
            event["extra"] = _scrub(event.get("extra", {}))
            event.pop("user", None)
            return event

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=_rate(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05"), 0.05),
            send_default_pii=False,
            before_send=before_send,
        )
        _SENTRY = sentry_sdk
        return True
    except Exception:
        app.logger.warning("Sentry could not be initialized")
        return False


def trace_span(op: str):
    """Cria um span técnico sem atributos de usuário; torna-se no-op sem SDK."""
    return _SENTRY.start_span(op=op) if _SENTRY else nullcontext()
