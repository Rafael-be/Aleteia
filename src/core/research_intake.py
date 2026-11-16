"""Research-first recovery when semantic extraction rejects a usable topic.

This does not assert the truth of a question or fill in missing dates/entities.
It creates a bounded research task; the evidence stage must resolve a concrete
proposition before ESS may be published.
"""
import re
import unicodedata
from src.core.contracts import Claim, Extraction
from src.core.input_gate import is_noise

_REFERENTIAL = set('isso isto aquilo ele ela eles elas esse essa este esta essa essas esses '
    'qual quais quem quando onde como porque por que e eh verdade verdadeiro verdadeira '
    'falso falsa serio mesmo pode poderia voce voces me dizer explicar verificar checar '
    'saber quero gostaria sobre de da do das dos o a os as um uma uns umas na no em '
    'tem foi era ser esta estar aconteceu realmente procede pra para favor porfavor '
    'informacao informacoes noticia noticias afirmacao contexto origem fonte fontes '
    'foto imagem video audio link anexo sim nao ok obrigado obrigada oi ola bom dia boa tarde noite '
    'tudo bem seguro segura perigoso perigosa funciona prova provas'.split())


def has_topic(text):
    if is_noise(text):
        return False
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                         if not unicodedata.combining(c))
    words = re.findall(r'\w+', normalized)
    return any(w not in _REFERENTIAL for w in words)


def verification_question(message):
    open_question = bool(re.match(r'^(quem|qual|quais|quando|onde|como|quanto|quantos|por\s*qu[eê]|o\s+que)\b', message.strip().casefold()))
    return '?' in message and not open_question and len(re.findall(r'\w+', message)) > 2


def recover_research_task(extraction, message, context):
    if extraction.kind == 'FACTUAL' and extraction.claims:
        yes_no = verification_question(message)
        tasks = [c.model_copy(update={'investigative': True, 'verification_target': yes_no or c.verification_target,
                                      'critical': c.critical or len(extraction.claims) == 1})
                 if '?' in message or '?' in c.text or len(re.findall(r'\w+', c.text)) <= 2 else c for c in extraction.claims]
        return extraction.model_copy(update={'claims': tasks})
    if extraction.kind not in {'NEEDS_CONTEXT', 'FACTUAL', 'NOT_VERIFIABLE'}:
        return extraction
    topic = message if has_topic(message) else next(
        (h['content'] for h in reversed(context) if h['role'] == 'user' and has_topic(h['content'])), None)
    if not topic:
        return extraction
    # Keep normative judgements/opinions outside factual checking. The recovery
    # applies to missing context and questions, not every non-verifiable opinion.
    if extraction.kind == 'NOT_VERIFIABLE' and '?' not in message:
        return extraction
    span = topic[:1500]
    query = re.sub(r'\s+', ' ', span).strip()[:400]
    risk = extraction.risk_requires_review or any(c.high_risk for c in extraction.claims)
    pending = extraction.omitted_material or len(topic) > 1500
    task = Claim(id='research1', text=span, original_span=span,
                 context='Questão a investigar. Pesquisar origem e contexto; não presumir fatos, '
                         'data, local ou identidade não fornecidos. Explicar interpretações relevantes.',
                 materiality=1.0, critical=True, verifiable=True, high_risk=risk,
                 elements=['resposta à questão pesquisada', 'origem e condições de validade'],
                 queries=[query+' evidências estudos', query+' refutação checagem controvérsias',
                          query, query+' origem fonte primária documentação'], investigative=True,
                 verification_target=verification_question(message))
    return Extraction(kind='FACTUAL', claims=[task], omitted_material=pending,
                      decomposition_complete=not pending, risk_requires_review=risk)
