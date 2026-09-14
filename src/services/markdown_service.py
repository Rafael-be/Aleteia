"""Renderização segura de markdown produzido exclusivamente pela IA."""

import re

from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
).enable("table")


def renderizar_markdown(texto: str) -> str:
    """Converte markdown em HTML sem permitir HTML bruto na resposta."""
    return _MARKDOWN.render(str(texto or ""))


def formatar_resposta_ia(texto: str) -> dict[str, str | None]:
    """Separa as seções conhecidas e renderiza somente conteúdo da IA."""
    texto = str(texto or "")
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
        "analise_html": renderizar_markdown(analise),
        "fontes_html": renderizar_markdown(fontes) if fontes else None,
    }