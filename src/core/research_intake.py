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


def open_question(message):
    return bool(re.match(r'^(quem|qual|quais|quando|onde|como|quanto|quantos|por\s*qu[eê]|o\s+que)\b',
                         message.strip().casefold()))


def verification_question(message):
    return '?' in message and not open_question(message) and len(re.findall(r'\w+', message)) > 2


def recover_research_task(extraction, message, context):
    if extraction.kind == 'FACTUAL' and extraction.claims:
        yes_no = verification_question(message)
        tasks = []
        for claim in extraction.claims:
            assertion = (not claim.investigative and not open_question(message)
                         and len(re.findall(r'\w+', claim.text)) > 2)
            target = yes_no or claim.verification_target or assertion
            # Extraction is not an evidence source. Do not promote a model's
            # guessed civil name, date or identity into established context.
            prior_user = '\n'.join(h['content'][-140:] for h in context[-2:]
                                    if h.get('role') == 'user')
            literal_context = 'Entrada do usuário: '+message[:650]
            if prior_user:
                literal_context += '\nContexto anterior do usuário: '+prior_user
            updates = {'personal_advice': claim.personal_advice or extraction.personal_advice,
                       'context': literal_context[:1000]}
            if '?' in message or '?' in claim.text or len(re.findall(r'\w+', claim.text)) <= 2:
                updates.update(investigative=True, verification_target=target,
                               critical=claim.critical or len(extraction.claims) == 1)
            if target:
                # Never let semantic extraction replace the submitted hypothesis
                # with its answer. Preserve negation, typos and stated context;
                # only the later assessment may explain or correct the wording.
                updates.update(text=claim.original_span, verification_target=True)
            tasks.append(claim.model_copy(update=updates))
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
    target = verification_question(span) or (not open_question(span) and '?' not in span
                                            and len(re.findall(r'\w+', span)) > 2)
    risk = extraction.risk_requires_review or any(c.high_risk for c in extraction.claims)
    pending = extraction.omitted_material or len(topic) > 1500
    task = Claim(id='research1', text=span, original_span=span,
                 context='Questão a investigar. Pesquisar origem e contexto; não presumir fatos, '
                         'data, local ou identidade não fornecidos. Explicar interpretações relevantes.',
                 materiality=1.0, critical=True, verifiable=True, high_risk=risk,
                 elements=['resposta à questão pesquisada', 'origem e condições de validade'],
                 queries=[query+' evidências estudos', query+' refutação checagem controvérsias',
                          query, query+' origem fonte primária documentação'], investigative=True,
                 verification_target=target)
    task = task.model_copy(update={'personal_advice': extraction.personal_advice or any(c.personal_advice for c in extraction.claims)})
    return Extraction(kind='FACTUAL', claims=[task], omitted_material=pending,
                      decomposition_complete=not pending, risk_requires_review=risk,
                      research_depth=extraction.research_depth, personal_advice=task.personal_advice)
