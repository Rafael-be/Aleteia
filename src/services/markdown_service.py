"""Renderização segura de markdown produzido exclusivamente pela IA."""

import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from src.services.chat_events import separar_veredito


_MARKDOWN = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
).enable("table")


def _link_seguro(url):
    """Only web links and local fragments; reject data/file/script schemes."""
    try:
        return not any(ord(c) < 32 for c in url) and urlsplit(url).scheme.lower() in {'', 'http', 'https'}
    except ValueError:
        return False


_MARKDOWN.validateLink = _link_seguro


def renderizar_markdown(texto: str) -> str:
    """Converte markdown em HTML sem permitir HTML bruto na resposta."""
    texto = str(texto or "")
    fontes = re.search(
        r"^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*|__)?Fontes consultadas(?:\*\*|__)?[ \t]*:",
        texto,
        re.IGNORECASE | re.MULTILINE,
    )
    if fontes:
        # Mantém o corpo inteiro, mas recupera o estilo próprio das fontes.
        return (
            _MARKDOWN.render(texto[:fontes.start()])
            + '<div class="resposta-fontes">\n'
            + _MARKDOWN.render(texto[fontes.start():])
            + '</div>\n'
        )
    return _MARKDOWN.render(texto)


def formatar_resposta_ia(texto: str) -> dict[str, str | None]:
    """Separa as seções conhecidas e renderiza somente conteúdo da IA."""
    texto, _ = separar_veredito(str(texto or ""))
    match_analise = re.search(
        r"\*\*Análise:\*\*\s*([\s\S]*?)(?:\*\*Fontes consultadas:\*\*|$)",
        texto,
        re.IGNORECASE,
    )
    match_fontes = re.search(
        r"\*\*Fontes consultadas:\*\*\s*([\s\S]*)",
        texto,
        re.IGNORECASE,
    )
    analise = match_analise.group(1).strip() if match_analise else texto.strip()
    fontes = match_fontes.group(1).strip() if match_fontes else None
    return {
        # Corpo completo: não descarta introduções ou trechos fora das seções.
        "corpo_html": renderizar_markdown(texto),
        "analise_html": renderizar_markdown(analise),
        "fontes_html": renderizar_markdown(fontes) if fontes else None,
    }
