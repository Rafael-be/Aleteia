"""Public operational failures, separate from epistemic analysis decisions."""
import logging
from openai import APIConnectionError, APITimeoutError, APIStatusError
from pydantic import ValidationError


class AnalysisError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def operational_error(exc):
    """Do not expose upstream bodies: they can echo keys, prompts and documents."""
    if isinstance(exc, AnalysisError):
        return exc
    if isinstance(exc, APIStatusError):
        if exc.status_code == 401:
            return AnalysisError('provider_authentication_failed',
                'A configuração da IA no servidor foi recusada pelo provedor. Verifique a credencial da API no backend.')
        if exc.status_code in {403, 404}:
            return AnalysisError('provider_access_failed',
                'O servidor não tem acesso ao modelo ou recurso de IA configurado. Verifique a configuração do backend.')
        if exc.status_code == 429:
            return AnalysisError('provider_rate_limited',
                'O provedor de IA atingiu um limite de uso ou saldo. Tente novamente mais tarde.')
        if exc.status_code == 400:
            return AnalysisError('provider_configuration_failed',
                'O provedor recusou a configuração da análise. Verifique o modelo e o contrato da API no backend.')
    if isinstance(exc, APITimeoutError):
        return AnalysisError('provider_timeout', 'A consulta à IA excedeu o tempo limite. Tente novamente.')
    if isinstance(exc, APIConnectionError):
        return AnalysisError('provider_connection_failed', 'O servidor não conseguiu se conectar ao provedor de IA.')
    if isinstance(exc, ValidationError):
        return AnalysisError('analysis_validation_failed',
            'Não foi possível validar os dados retornados pela IA. A análise não foi concluída.')
    return AnalysisError('analysis_unavailable', 'Não foi possível concluir a análise. Tente novamente.')


def log_failure(exc, stage):
    error = operational_error(exc)
    logging.getLogger(__name__).error('analysis_failed stage=%s code=%s status=%s exception_type=%s',
        stage, error.code, getattr(exc, 'status_code', None), type(exc).__name__)
    return error
