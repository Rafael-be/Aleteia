"""Contrato de eventos independente do provedor e das futuras fases da pesquisa."""

import re

VERDICT_MARKER = "**Veredicto:**"
VERDICTS = ("PARCIALMENTE VERDADEIRO", "VERDADEIRO", "FALSO", "INCONCLUSIVO")
# Aceita títulos, negrito antes/depois dos dois-pontos e as duas grafias.
_ROTULO = r"[ \t]*(?:#{1,6}[ \t]+)?(?:\*{1,2}|__)?veredi(?:c)?to(?:\*{1,2}|__)?[ \t]*:[ \t]*(?:\*{1,2}|__)?"
_LINHA_VEREDITO = re.compile(r"^" + _ROTULO + r"([^\r\n]*)(?:\r?\n[ \t]*((?:\*{1,2}|__)?(?:PARCIALMENTE VERDADEIRO|VERDADEIRO|FALSO|INCONCLUSIVO)[^\r\n]*))?", re.I | re.M)
_VALOR = re.compile(r"^(PARCIALMENTE VERDADEIRO|VERDADEIRO|FALSO|INCONCLUSIVO)\b", re.I)


def etapa(codigo: str, mensagem: str) -> dict:
    return {"type": "stage", "stage": codigo, "message": mensagem}


def separar_veredito(texto: str) -> tuple[str, dict]:
    """O veredito é um objeto extensível; métricas futuras não dependem do Markdown."""
    codigo = "INCONCLUSIVO"
    for match in _LINHA_VEREDITO.finditer(texto):
        valor = (match.group(1).strip() or match.group(2) or "").strip("*_ \t")
        classificacao = _VALOR.match(valor)
        if classificacao:
            codigo = classificacao.group(1).upper()
            break
    corpo = _LINHA_VEREDITO.sub("", texto).strip()
    return corpo, {"version": 1, "code": codigo, "metrics": []}


class FiltroVeredito:
    """Retém possíveis linhas de veredito; libera o restante incrementalmente."""

    def __init__(self):
        self.pendente = ""
        self.linha_liberada = False
        self.aguarda_valor = False

    @staticmethod
    def _possivel_rotulo(texto):
        prefixo = texto.lstrip(" \t#*_ ").lower()
        return not prefixo or any(rotulo.startswith(prefixo) for rotulo in ("veredicto", "veredito")) or bool(
            re.match(r"^veredi(?:c)?to(?:\*{0,2}|_{0,2})[ \t]*:?[ \t]*$", prefixo))

    def adicionar(self, delta: str) -> str:
        self.pendente += delta
        saida = []
        while "\n" in self.pendente:
            linha, self.pendente = self.pendente.split("\n", 1)
            saida.append(self._linha(linha, completa=True))
            self.linha_liberada = False
        if self.linha_liberada or (not self.aguarda_valor and not self._possivel_rotulo(self.pendente)
                                  and not re.match(r"^" + _ROTULO, self.pendente, re.I)):
            saida.append(self.pendente)
            self.pendente = ""
            self.linha_liberada = True
        return "".join(saida)

    def _linha(self, linha, completa=False):
        rotulo = re.match(r"^" + _ROTULO, linha, re.I) if not self.linha_liberada else None
        if rotulo:
            self.aguarda_valor = not linha[rotulo.end():].strip("*_ \t\r")
            return ""
        if self.aguarda_valor:
            self.aguarda_valor = False
            if _VALOR.match(linha.strip("*_ \t\r")):
                return ""
        return linha + ("\n" if completa else "")

    def finalizar(self) -> str:
        texto = self._linha(self.pendente)
        self.pendente = ""
        return texto
