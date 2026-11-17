"""Environment always takes precedence over local development configuration."""
from pathlib import Path
import logging
import os
from dotenv import dotenv_values, load_dotenv


def load_environment(path: Path) -> None:
    """Preserve deployment settings, but make stale local exports observable."""
    local = dotenv_values(path)
    conflicts = [name for name in ('OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_BASE_URL')
                 if name in os.environ and local.get(name) is not None
                 and os.environ[name] != local[name]]
    load_dotenv(path, override=False)
    if conflicts:
        logging.getLogger(__name__).warning(
            'Configuração OpenAI: variáveis do processo diferem do .env e têm prioridade: %s. '
            'Para usar o arquivo local, remova esses exports antes de iniciar o backend. '
            'Nenhum valor de credencial foi registrado.', ', '.join(conflicts))


load_environment(Path(__file__).resolve().parents[1] / '.env')
