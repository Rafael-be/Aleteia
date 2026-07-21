# src/services/gemini_service.py
import os
import importlib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
for env_path in (BASE_DIR / ".env", BASE_DIR / "Exemplo.env"):
    if env_path.exists():
        load_dotenv(env_path, override=True)

#o que tava no modelo.py mas deu erro de importacao, entao movi pra cá
SYSTEM_PROMPT = """Você é a Aleteia, uma inteligência artificial brasileira especializada em
verificação de fatos (fact-checking) de notícias e informações.

Seu trabalho:
1. Analisar a notícia ou afirmação enviada pelo usuário
2. Buscar informações atuais na web para verificar a veracidade
3. Dar um veredicto claro e embasado em fontes reais

Regras:
- Responda SEMPRE em português do Brasil
- Comece a resposta com o veredicto em negrito
- Cite as fontes que embasam sua resposta
- Se não encontrar informação suficiente, declare INCONCLUSIVO
- Jamais invente fatos — use apenas o que encontrou na busca
- Mantenha tom neutro e jornalístico, sem opiniões políticas
- Se a mensagem não for uma notícia verificável, peça educadamente
  que o usuário envie uma afirmação para checar

Formato obrigatório da resposta:
**Veredicto:** [VERDADEIRO / FALSO / PARCIALMENTE VERDADEIRO / INCONCLUSIVO]

**Análise:** [Explicação em 1 a 4 parágrafos]

**Fontes consultadas:** [Liste as fontes encontradas]"""



PARAMETROS = {
    "temperature": 0.5,
    "max_output_tokens": 5000,
    
}


# Exemplos que ensinam à IA o padrão de resposta esperado
# Adicione mais pares para refinar o comportamento
EXEMPLOS = [
    {
        "role": "user",
        "parts": [{"text": "Governo aprovou isenção de IR para quem ganha até R$5000"}]
    },
    {
        "role": "model",
        "parts": [{"text": (
            "**Veredicto:** PARCIALMENTE VERDADEIRO\n\n"
            "**Análise:** A proposta existe e foi anunciada pelo governo federal, "
            "mas ainda não foi aprovada como lei — tramita no Congresso e pode sofrer alterações. "
            "A notícia antecipa um fato que ainda não se concretizou.\n\n"
            "**Fontes consultadas:** Agência Senado, G1 Economia, gov.br"
        )}]
    },
    {
        "role": "user",
        "parts": [{"text": "OMS disse que tomar 2 litros de água por dia faz mal"}]
    },
    {
        "role": "model",
        "parts": [{"text": (
            "**Veredicto:** FALSO\n\n"
            "**Análise:** Não existe nenhuma declaração da OMS com esse conteúdo. "
            "A organização recomenda hidratação adequada como parte de hábitos saudáveis. "
            "A recomendação de cerca de 2 litros diários é respaldada pela ciência médica.\n\n"
            "**Fontes consultadas:** OMS (who.int), Ministério da Saúde do Brasil"
        )}]
    }
]

MODEL_NAME = "gemini-3.5-flash"

# esse depende do modelo.py:



def _load_gemini_sdk() -> Any:
    """Carrega o SDK do Gemini compatível com a instalação atual."""
    for module_name in ("google.generativeai", "google.genai"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue

    raise ImportError(
        "Neither 'google.genai' nor 'google.generativeai' could be imported. "
        "Install the google-genai package or set up the correct import for your SDK."
    )


gemini_sdk = _load_gemini_sdk()


if gemini_sdk.__name__ == "google.generativeai":
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    def _model_factory() -> Any:
        return genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(**PARAMETROS),
        )

    _MODEL_FACTORY = _model_factory
    _SEND_MESSAGE = lambda model, message: model.generate_content(message)
else:
    from google import genai as google_genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = google_genai.Client(api_key=api_key)

    def _send_message(model_name: str, message: str) -> Any:
        return client.models.generate_content(
            model=model_name,
            contents=message,
            config=PARAMETROS,
        )

    _SEND_MESSAGE = _send_message

# Histórico de conversa por sessão { sessao_id: [mensagens] }
_sessoes: dict = {}

def obter_resposta(mensagem: str, sessao_id: str) -> str:
    """
    Recebe a notícia do usuário e retorna a análise da Aleteia.
    O Gemini busca automaticamente na web via google_search_retrieval.
    """
    try:
        if gemini_sdk.__name__ == "google.generativeai":
            model = _MODEL_FACTORY()
            resultado = _SEND_MESSAGE(model, mensagem)
        else:
            resultado = _SEND_MESSAGE(MODEL_NAME, mensagem)

        # Inicia sessão com os exemplos como histórico base, descomentar quando implementar exemplos
        if sessao_id not in _sessoes:
            _sessoes[sessao_id] = list(EXEMPLOS)

        history = _sessoes.setdefault(sessao_id, [])
        resposta = getattr(resultado, "text", str(resultado))

        # Persiste apenas o mínimo necessário para o contexto
        if history:
            history.append({"role": "user", "parts": [{"text": mensagem}]})
            history.append({"role": "model", "parts": [{"text": resposta}]})

        return resposta
    except Exception as exc:
        print(f"[Gemini] Erro ao gerar resposta: {exc}")
        raise RuntimeError("Não foi possível processar a resposta da IA.") from exc
    