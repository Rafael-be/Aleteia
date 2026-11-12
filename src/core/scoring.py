"""Candidate formulas from the memorial. No network, prompts or secret state."""
from dataclasses import asdict, dataclass
from collections import Counter
import math

METHOD_VERSION = 'core-v2.0-candidate'


@dataclass(frozen=True)
class Parameters:
    # Engineering baseline, deliberately not claimed to be empirically calibrated.
    version: str = 'equal-weights-2026-11-v1'
    alpha: float = 1/3
    beta: float = 1/3
    delta: float = 1/3
    gamma: float = 1.0
    rho: float = 0.20
    lambda_mass: float = 2.0
    minimum_mass: float = 0.60
    acceptance: float = 65.0
    incomplete_process_cap: float = 50.0
    conflict: float = 0.45
    strong: float = 85.0
    directional: float = 60.0

    def __post_init__(self):
        values = [v for v in asdict(self).values() if not isinstance(v, str)]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Nonfinite parameter')
        if min(self.alpha, self.beta, self.delta) < 0 or not math.isclose(self.alpha+self.beta+self.delta, 1):
            raise ValueError('Invalid simplex')
        if self.gamma != 1 or min(self.rho, self.lambda_mass, self.minimum_mass) <= 0:
            raise ValueError('Invalid regularization')
        if not 0 <= self.acceptance <= 100 or not 0 <= self.incomplete_process_cap <= 100 or not 0 <= self.conflict <= 1:
            raise ValueError('Invalid gate')
        if not 50 < self.directional < self.strong <= 100:
            raise ValueError('Invalid direction thresholds')


DEFAULTS = Parameters()


def unit(value):
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Expected finite unit number')
    return float(value)


def geometric(values, weights=None):
    if not values or any(v is None for v in values):
        return None
    values = [unit(v) for v in values]
    weights = [1/len(values)] * len(values) if weights is None else weights
    if len(weights) != len(values) or any(unit(w) < 0 for w in weights) or not math.isclose(sum(weights), 1):
        raise ValueError('Invalid weights')
    applicable = [(v, w) for v, w in zip(values, weights) if w > 0]
    if any(v == 0 for v, _ in applicable):
        return 0.0
    return math.exp(sum(w*math.log(v) for v, w in applicable))


def masses(evidence, p=DEFAULTS):
    counts = Counter(e['group'] for e in evidence)
    positive, negative = 0.0, 0.0
    seen = set()
    for e in evidence:
        if e['source_id'] in seen:
            raise ValueError('Duplicate document within claim')
        seen.add(e['source_id'])
        s = e['stance']
        if type(s) not in (int, float) or not math.isfinite(s) or not -1 <= s <= 1:
            raise ValueError('Invalid stance')
        weight = geometric([e['source_quality'], e['relevance'], e['context_fit']],
                           [p.alpha, p.beta, p.delta])
        if weight is None:
            continue
        contribution = weight * counts[e['group']]**(-p.gamma) * s
        positive += max(contribution, 0)
        negative += max(-contribution, 0)
    mass = positive + negative
    candidate = 50*(1+(positive-negative)/(mass+p.rho))
    conflict = (2*min(positive, negative)/mass if mass else 0) * (-math.expm1(-p.lambda_mass*mass))
    return {'positive': positive, 'negative': negative, 'mass': mass,
            'candidate_ess': candidate, 'conflict': conflict}


def robustness(evidence, p=DEFAULTS):
    """Source-removal and ±0.05 attribute sensitivity; NOT semantic robustness."""
    if not evidence:
        return None
    baseline = masses(evidence, p)['candidate_ess']
    candidates = []
    for group in sorted({e['group'] for e in evidence}):
        candidates.append(masses([e for e in evidence if e['group'] != group], p)['candidate_ess'])
    for shift in (-0.05, 0.05):
        changed = [{**e, **{k: min(1, max(0, e[k]+shift)) if e[k] is not None else None
                            for k in ('source_quality', 'relevance', 'context_fit')}} for e in evidence]
        candidates.append(masses(changed, p)['candidate_ess'])
    return max(0.0, 1-max(abs(x-baseline) for x in candidates)/50)


def score_claim(claim, evidence, searches, review, decomposition_complete, p=DEFAULTS):
    m = masses(evidence, p)
    complete_search = len(searches) == 4 and all(s.get('executed') for s in searches)
    qualified = [e for e in evidence if all(e.get(k) is not None for k in
                 ('source_quality', 'relevance', 'context_fit'))]
    covered = {i for e in qualified if e['relevance'] >= .5 and e['context_fit'] >= .5 and e['stance'] != 0
               for i in e['covered_elements']}
    coverage = len(covered)/len(claim.elements)
    known = bool(evidence) and len(qualified) == len(evidence)
    context = bool(review and review.context_complete and not review.causal_overreach)
    decomposition = bool(decomposition_complete and review and review.decomposition_faithful)
    provenance = bool(evidence) and all(e['origin_verified'] for e in evidence if e['stance'] != 0)
    reasons = []
    for ok, reason in [(claim.verifiable, 'NOT_VERIFIABLE'), (complete_search, 'RETRIEVAL_INCOMPLETE'),
                       (coverage == 1, 'MATERIAL_COVERAGE_INCOMPLETE'), (known, 'ATTRIBUTES_MISSING'),
                       (context, 'CONTEXT_INCOMPLETE'), (decomposition, 'DECOMPOSITION_INCOMPLETE'),
                       (provenance, 'PROVENANCE_UNCERTAIN'), (m['mass'] >= p.minimum_mass, 'INSUFFICIENT_EVIDENCE')]:
        if not ok:
            reasons.append(reason)
    dimensions = {
        'D': 1.0 if decomposition else None,
        'R': sum(bool(s.get('executed')) for s in searches)/4,
        'E': min(1, m['mass']/p.minimum_mass)*coverage if known and provenance else None,
        'C': geometric([e['context_fit'] for e in qualified]) if qualified and context else None,
        'Rob': robustness(qualified, p) if known and provenance else None,
    }
    acs = geometric(list(dimensions.values()))
    acs = 100*acs if acs is not None else None
    if acs is not None and (not complete_search or coverage < 1):
        acs = min(acs, p.incomplete_process_cap)
    ess = m['candidate_ess'] if not reasons else None
    positive_groups = {e['group'] for e in evidence if e['stance'] > 0}
    negative_groups = {e['group'] for e in evidence if e['stance'] < 0}
    independent_conflict = any(a != b for a in positive_groups for b in negative_groups)
    if not claim.verifiable:
        state = 'NOT_VERIFIABLE'
        acs = None
    elif claim.high_risk:
        state = 'HUMAN_REVIEW_REQUIRED'
    elif reasons or acs is None or acs < p.acceptance:
        state = 'INCONCLUSIVE'
        if acs is not None and acs < p.acceptance:
            reasons.append('LOW_ACS')
    elif m['conflict'] >= p.conflict and independent_conflict:
        state = 'CONTESTED'
    elif ess >= p.strong:
        state = 'STRONGLY_SUPPORTED'
    elif ess >= p.directional:
        state = 'PREDOMINANTLY_SUPPORTED'
    elif ess <= 100-p.strong:
        state = 'STRONGLY_CONTRADICTED'
    elif ess <= 100-p.directional:
        state = 'PREDOMINANTLY_CONTRADICTED'
    else:
        state = 'INCONCLUSIVE'
    return {'claim_id': claim.id, 'state': state, 'ess': ess, 'acs': acs,
            'reasons': reasons, 'dimensions': dimensions, **m}


def metric(identifier, value, reason=None):
    return {'id': identifier, 'label': 'Sustentação das evidências' if identifier == 'ESS' else 'Qualidade da análise',
            'value': round(value, 1) if value is not None else None, 'min': 0, 'max': 100,
            'valid': value is not None, 'reason': reason if value is None else None}


def verdict(claims, results, incomplete=False, p=DEFAULTS):
    """Conservative multiclaim summary: no missing material claim is averaged away."""
    ess = acs = None
    state = 'INCONCLUSIVE'
    if results and not incomplete:
        if all(r['state'] == 'NOT_VERIFIABLE' for r in results):
            state = 'NOT_VERIFIABLE'
        elif any(r['state'] == 'HUMAN_REVIEW_REQUIRED' for r in results):
            state = 'HUMAN_REVIEW_REQUIRED'
        elif len(results) == 1:
            state, ess, acs = results[0]['state'], results[0]['ess'], results[0]['acs']
        else:
            # Averages across dependent/heterogeneous propositions are intentionally withheld.
            states = {r['state'] for r in results}
            if len(states) == 1:
                state = next(iter(states))
            critical = [r for c, r in zip(claims, results) if c.critical]
            if any('CONTRADICTED' in r['state'] for r in critical):
                state = 'PREDOMINANTLY_CONTRADICTED'
            if any(r['state'] == 'INCONCLUSIVE' for r in results):
                state = 'INCONCLUSIVE'
    reason = 'MULTIPLE_CLAIMS' if len(results) > 1 and not incomplete else 'REQUIREMENTS_NOT_MET'
    if len(results) == 1 and results[0]['reasons']:
        reason = results[0]['reasons'][0]
    if state == 'HUMAN_REVIEW_REQUIRED':
        reason = 'HUMAN_REVIEW_REQUIRED'
    return {'version': 2, 'code': state, 'method_version': METHOD_VERSION,
            'parameter_version': p.version, 'calibrated': False,
            'scope': 'claim' if len(results) == 1 else 'analysis',
            'metrics': [metric('ESS', ess, reason), metric('ACS', acs, reason)],
            'claims': [{k: r[k] for k in ('claim_id', 'state', 'ess', 'acs', 'reasons')} for r in results]}
