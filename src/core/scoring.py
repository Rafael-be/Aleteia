"""Candidate formulas from the memorial. No network, prompts or secret state."""
from dataclasses import asdict, dataclass
from collections import Counter
import math

METHOD_VERSION = 'core-v5.0-candidate'


@dataclass(frozen=True)
class Parameters:
    # Engineering baseline, deliberately not claimed to be empirically calibrated.
    version: str = 'contextual-decision-2026-11-v9'
    alpha: float = 1/3
    beta: float = 1/3
    delta: float = 1/3
    gamma: float = 1.0
    rho: float = 0.20
    lambda_mass: float = 2.0
    minimum_mass: float = 0.60
    acceptance: float = 65.0
    incomplete_process_cap: float = 50.0
    single_group_cap: float = 55.0
    uncertain_origin_cap: float = 35.0
    traceable_document_cap: float = 75.0
    provider_excerpt_cap: float = 25.0
    provider_excerpt_weight: float = 0.25
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
        if any(not 0 <= cap <= 100 for cap in (self.single_group_cap, self.uncertain_origin_cap, self.traceable_document_cap, self.provider_excerpt_cap)):
            raise ValueError('Invalid evidence cap')
        if not 0 <= self.provider_excerpt_weight <= 1:
            raise ValueError('Invalid excerpt weight')
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
    candidates = evidence
    # Retrieval candidates are not all proof. An irrelevant page, another year,
    # or an unqualified annotation must not invalidate otherwise sufficient proof.
    evidence = [e for e in candidates if e['stance'] != 0 and
                all(e.get(k) is not None for k in ('source_quality', 'relevance', 'context_fit')) and
                e['relevance'] >= .5 and e['context_fit'] >= .5]
    if not evidence:
        evidence = [e for e in candidates if e['stance'] != 0 and
                    (e.get('relevance') is None or e['relevance'] >= .5) and
                    (e.get('context_fit') is None or e['context_fit'] >= .5)]
    # A provider's cited synthesis can inform a preliminary answer, but it is
    # not a verbatim primary artifact and cannot contribute to public ESS.
    direct = [e for e in evidence if e.get('retrieval_kind') != 'provider_excerpt']
    m = masses(direct, p)
    complete_search = len(searches) == 4 and all(s.get('executed') for s in searches)
    qualified = [e for e in evidence if all(e.get(k) is not None for k in
                 ('source_quality', 'relevance', 'context_fit'))]
    covered = {i for e in qualified if e['relevance'] >= .5 and e['context_fit'] >= .5 and e['stance'] != 0
               for i in e['covered_elements']}
    coverage = len(covered)/len(claim.elements)
    direct_covered = {i for e in qualified if e in direct and e['relevance'] >= .5
                      and e['context_fit'] >= .5 and e['stance'] != 0 for i in e['covered_elements']}
    direct_coverage = len(direct_covered)/len(claim.elements)
    decisive_refutations = [e for e in direct if e['stance'] == -1 and
        e.get('refutation_kind') == 'explicit_contradiction' and e.get('refutes_elements') and
        set(e['refutes_elements']) <= set(e['covered_elements']) and
        all(type(i) is int and 0 <= i < len(claim.elements) for i in e['refutes_elements']) and
        e['source_quality'] is not None and e['source_quality'] >= .75 and
        e['relevance'] == 1 and e['context_fit'] == 1]
    # A necessary conjunct explicitly falsified is a complete refutation, even
    # when other conjuncts or the historical origin remain unproven. This never
    # turns partial positive support into confirmation of the entire claim.
    refutation_sufficient = bool(decisive_refutations)
    decision_coverage = 1.0 if refutation_sufficient else direct_coverage
    process_coverage = 1.0 if refutation_sufficient else coverage
    known = bool(evidence) and len(qualified) == len(evidence)
    causal_failure = bool(review and claim.relation_type == 'causal' and review.causal_overreach)
    context = bool(review and (review.context_complete or refutation_sufficient) and not causal_failure)
    decomposition = bool(decomposition_complete and review and review.decomposition_faithful)
    provenance = bool(direct) and all(e['origin_verified'] for e in direct)
    decisive_primary = any(e.get('primary') and e['origin_verified'] and e['source_quality'] is not None and e['source_quality'] >= .75
                           and e['relevance'] == 1 and e['context_fit'] == 1 for e in direct)
    direct_sufficient = decision_coverage == 1 and m['mass'] >= p.minimum_mass
    decisive_document = direct_sufficient and any(e['source_quality'] is not None and e['source_quality'] >= .75 and
                        e['relevance'] == 1 and e['context_fit'] == 1 for e in direct)
    process_qualified = direct if direct_sufficient else qualified
    excerpts_needed = not direct_sufficient and any(e.get('retrieval_kind') == 'provider_excerpt' for e in evidence)
    procedural_mass = m['mass'] + p.provider_excerpt_weight * masses(
        [e for e in qualified if e.get('retrieval_kind') == 'provider_excerpt'], p)['mass']
    reasons = []
    resolved = bool(review and review.resolved_claim and review.resolved_claim.strip()
                    and review.resolution_source_ids and
                    set(review.resolution_source_ids) <= {e['source_id'] for e in evidence})
    for ok, reason in [(claim.verifiable, 'NOT_VERIFIABLE'), (complete_search, 'RETRIEVAL_INCOMPLETE'),
                       (decision_coverage == 1, 'MATERIAL_COVERAGE_INCOMPLETE'), (known, 'ATTRIBUTES_MISSING'),
                       (context, 'CONTEXT_INCOMPLETE'), (decomposition, 'DECOMPOSITION_INCOMPLETE'),
                       (bool(direct), 'DIRECT_EVIDENCE_REQUIRED'), (m['mass'] >= p.minimum_mass, 'INSUFFICIENT_EVIDENCE')]:
        if not ok:
            reasons.append(reason)
    if claim.investigative and not claim.verification_target and not resolved:
        reasons.append('QUESTION_NOT_RESOLVED')
    dimensions = {
        'D': float(decomposition) if review else None,
        'R': sum(bool(s.get('executed')) for s in searches)/4,
        'E': min(1, procedural_mass/p.minimum_mass)*process_coverage if known else None,
        'C': (geometric([e['context_fit'] for e in process_qualified]) *
              (0 if causal_failure else 1 if review.context_complete or refutation_sufficient else .5)) if process_qualified and review else None,
        'Rob': robustness(process_qualified, p) if known else None,
    }
    acs = geometric(list(dimensions.values()))
    acs = 100*acs if acs is not None else None
    if acs is not None and (not complete_search or process_coverage < 1):
        acs = min(acs, p.incomplete_process_cap)
    if acs is not None and not decisive_document and len({e['group'] for e in process_qualified if e['stance']}) < 2:
        acs = min(acs, p.single_group_cap)
    if acs is not None and not provenance and not decisive_primary:
        acs = min(acs, p.traceable_document_cap if decisive_document else p.uncertain_origin_cap)
    if acs is not None and excerpts_needed:
        acs = min(acs, p.provider_excerpt_cap)
    acs_upper_bound = None
    if acs is None and evidence and claim.verifiable:
        # Missing dimensions remain unknown. Compute an UPPER BOUND on the
        # geometric model, not a guessed point score: every unknown is ≤1.
        acs_upper_bound = 100*geometric([1.0 if z is None else z for z in dimensions.values()])
        caps = [p.incomplete_process_cap] if not complete_search or process_coverage < 1 else []
        if not decisive_document and len({e['group'] for e in process_qualified if e['stance']}) < 2:
            caps.append(p.single_group_cap)
        if not provenance and not decisive_primary:
            caps.append(p.traceable_document_cap if decisive_document else p.uncertain_origin_cap)
        if excerpts_needed:
            caps.append(p.provider_excerpt_cap)
        acs_upper_bound = min([acs_upper_bound]+caps)
    ess = m['candidate_ess'] if not reasons else None
    if evidence and not provenance and not decisive_primary:
        reasons.append('PROVENANCE_UNCERTAIN')
    if excerpts_needed:
        reasons.append('PROVIDER_EXCERPT_ONLY' if not direct else 'PARTIAL_PROVIDER_EXCERPTS')
    if qualified and not decisive_document and len({e['group'] for e in process_qualified if e['stance']}) < 2:
        reasons.append('LIMITED_INDEPENDENT_SOURCES')
    positive_groups = {e['group'] for e in evidence if e['stance'] > 0}
    negative_groups = {e['group'] for e in evidence if e['stance'] < 0}
    independent_conflict = any(a != b for a in positive_groups for b in negative_groups)
    if not claim.verifiable:
        state = 'NOT_VERIFIABLE'
        acs = None
        acs_upper_bound = None
    elif claim.high_risk:
        state = 'HUMAN_REVIEW_REQUIRED'
    elif ess is None or acs is None or acs < p.acceptance:
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
    return {'claim_id': claim.id, 'state': state, 'ess': ess, 'acs': acs, 'acs_upper_bound': acs_upper_bound,
            'resolved_claim': claim.text if claim.verification_target else review.resolved_claim if claim.investigative and resolved else None,
            'proof_basis': 'necessary_element_refuted' if refutation_sufficient else 'full_material_coverage' if direct_coverage == 1 else 'incomplete',
            'material_coverage': direct_coverage, 'decision_coverage': decision_coverage,
            'decisive_refutation_sources': [e['source_id'] for e in decisive_refutations],
            'causal_gate_applied': causal_failure,
            'preliminary': bool(evidence) and state == 'INCONCLUSIVE',
            'evidence_used': len(evidence), 'evidence_excluded': len(candidates)-len(evidence),
            'reasons': reasons, 'dimensions': dimensions, **m}


def metric(identifier, value, reason=None, upper_bound=None, measurement=None):
    result = {'id': identifier, 'label': 'Sustentação das evidências' if identifier == 'ESS' else 'Qualidade da análise',
            'unit': '%',
            'value': round(value, 1) if value is not None else None, 'min': 0, 'max': 100,
            'valid': value is not None, 'reason': reason if value is None else None}
    if value is None and upper_bound is not None:
        result['upper_bound'] = round(upper_bound, 1)
        result['measurement'] = 'upper_bound'
    if measurement == 'observed_support' and identifier == 'ESS':
        result.update(measurement=measurement, label='Sustentação encontrada na pesquisa')
    if measurement == 'undetermined_support' and identifier == 'ESS':
        result.update(measurement=measurement, label='Sustentação indeterminada · ponto neutro da escala')
    if measurement == 'provisional_direction' and identifier == 'ESS':
        result.update(measurement=measurement, label='Sustentação provisória · atributos incompletos')
    return result


def verdict(claims, results, incomplete=False, p=DEFAULTS):
    """Conservative multiclaim summary: no missing material claim is averaged away."""
    ess = acs = None
    state = 'INCONCLUSIVE'
    if results and not incomplete:
        if all(r['state'] == 'NOT_VERIFIABLE' for r in results):
            state = 'NOT_VERIFIABLE'
        elif len(results) == 1:
            state, ess, acs = results[0]['state'], results[0]['ess'], results[0]['acs']
        elif any(r['state'] == 'HUMAN_REVIEW_REQUIRED' for r in results):
            state = 'HUMAN_REVIEW_REQUIRED'
        else:
            # Averages across dependent/heterogeneous propositions are intentionally withheld.
            states = {r['state'] for r in results}
            if len(states) == 1:
                state = next(iter(states))
            elif all('SUPPORTED' in s for s in states):
                state = 'PREDOMINANTLY_SUPPORTED'
            elif all('CONTRADICTED' in s for s in states):
                state = 'PREDOMINANTLY_CONTRADICTED'
            elif all('SUPPORTED' in s or 'CONTRADICTED' in s for s in states):
                state = 'MIXED'
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
            'assessment_level': 'preliminary' if any(r.get('preliminary') for r in results) else 'standard',
            'parameter_version': p.version, 'calibrated': False,
            'scope': 'claim' if len(results) == 1 else 'analysis',
            'metrics': [metric('ESS', ess, reason, measurement=results[0].get('ess_measurement')
                               if len(results) == 1 else None), metric('ACS', acs, reason,
                        upper_bound=results[0].get('acs_upper_bound') if len(results) == 1 and not incomplete else None)],
            'claims': [{k: r[k] for k in ('claim_id', 'state', 'ess', 'acs', 'reasons')} for r in results]}
