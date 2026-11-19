"""Answer-first policy: numerical evidence indices, never invented probabilities.

The strict proof engine remains an audit diagnostic. Publication is based on
qualified relevant evidence and measured process completion, with uncertainty
expressed in the indices and wording rather than automatic abstention.
"""
from collections import Counter
from src.core.scoring import DEFAULTS, geometric_measured, masses, robustness, score_claim as strict_score


REQUIRED_OBJECTIVES = frozenset({'support', 'contradiction', 'neutral', 'primary'})


def search_objectives(search):
    return set(search.get('objectives', [search.get('intent')])) & REQUIRED_OBJECTIVES


def research_completion(searches):
    """Return planned objectives that did not complete with usable search output.

    The planner records every required objective, including those skipped by a
    budget cap. A provider URL is not enough: production searches carry
    ``usable_sources`` only after a document snapshot or cited excerpt was
    recovered for that exact search record.
    Minimal legacy fixtures omit status/source fields and remain accepted as a
    completed search when they explicitly set ``executed``.
    """
    planned = set().union(*(search_objectives(search) for search in searches)) if searches else set()
    missing = set()
    for objective in planned:
        candidates = [search for search in searches if objective in search_objectives(search)]
        completed = False
        for search in candidates:
            if not search.get('executed') or search.get('status') in {'failed', 'unobserved', 'budget_skipped'}:
                continue
            has_observed_sources = ('sources' not in search and 'excerpts' not in search
                                    and 'usable_sources' not in search)
            has_usable_output = (bool(search['usable_sources']) if 'usable_sources' in search
                                 else bool(search.get('sources') or search.get('excerpts')))
            if has_observed_sources or has_usable_output:
                completed = True
                break
        if not completed:
            missing.add(objective)
    return {'complete': not missing, 'required': planned, 'missing': missing}


def apply_research_gate(result, searches):
    """Keep measured indices but never publish direction from incomplete research."""
    completion = research_completion(searches)
    result['research_complete'] = completion['complete']
    result['missing_research_objectives'] = sorted(completion['missing'])
    if not completion['complete']:
        result['state'] = 'INCONCLUSIVE'
        result['preliminary'] = True
        if 'RETRIEVAL_INCOMPLETE' not in result['reasons']:
            result['reasons'].insert(0, 'RETRIEVAL_INCOMPLETE')
    return result


def attribute_stability(evidence, p=DEFAULTS):
    """Sensitivity to rubric uncertainty, separate from losing all observations.

    Removing the only inspected source measures evidence dependence, not a
    failure of the procedure. Keep that experiment in the diagnostic instead
    of treating an empty evidence set as an opposing observation.
    """
    baseline = masses(evidence, p)['candidate_ess']
    candidates = []
    for shift in (-.05, .05):
        changed = [{**e, **{k: min(1, max(0, e[k]+shift))
                            for k in ('source_quality', 'relevance', 'context_fit')}} for e in evidence]
        candidates.append(masses(changed, p)['candidate_ess'])
    return max(0, 1-max(abs(candidate-baseline) for candidate in candidates)/50)


def score_search_finding(claim, evidence, searches, review, complete, result, p=DEFAULTS):
    """Report observed lack of support, never a fabricated refutation mass."""
    objectives = {i for s in searches if s.get('executed') for i in search_objectives(s)}
    if not (claim.verifiable and review and review.evaluated_target ==
            (review.resolved_claim if claim.investigative and not claim.verification_target
             and review.resolved_claim else claim.text)):
        return result
    contextual = [e for e in evidence if e['stance'] == 0]
    directional = [e for e in evidence if e['stance'] and
        e.get('decision_scope', 'applicable') in ('applicable', 'indirect') and
        e.get('contribution', 'decision') != 'incidental' and
        (e.get('context_fit') is None or e['context_fit'] >= .5) and
        (e.get('relevance') is None or e['relevance'] >= .5)]
    if directional and not review.analysis_overreach:
        # A separate provisional estimator uses observed semantic direction
        # and retrieval type only. It does NOT fill missing SQ/R/CF grades.
        counts = Counter(e['group'] for e in directional)
        contributions = [e['stance'] / counts[e['group']] *
                         (p.provider_excerpt_weight if e.get('retrieval_kind') == 'provider_excerpt' else 1)
                         for e in directional]
        positive = sum(max(x, 0) for x in contributions)
        negative = sum(max(-x, 0) for x in contributions)
        mass = positive+negative
        ess = 50*(1+(positive-negative)/(mass+p.rho))
        state = 'CONTESTED' if positive and negative else 'PREDOMINANTLY_SUPPORTED' if positive else 'PREDOMINANTLY_CONTRADICTED'
        review_factor = 1.0 if complete and review.decomposition_faithful else 25/35
        known = sum((e.get(k) or 0) for e in directional
                    for k in ('source_quality', 'relevance', 'context_fit'))/(3*len(directional))
        traceability = sum(p.provider_excerpt_weight if e.get('retrieval_kind') == 'provider_excerpt'
                           else 1.0 for e in directional)/len(directional)
        acs = 35 * review_factor * len(objectives)/4 * (known + traceability)/2
        result.update(state='HUMAN_REVIEW_REQUIRED' if claim.personal_advice else state,
            ess=ess, acs=acs, acs_upper_bound=None,
            ess_measurement='provisional_direction', positive=positive, negative=negative, mass=mass,
            reasons=['ATTRIBUTES_MISSING', 'PROVISIONAL_DIRECTION'], preliminary=True,
            scoring_source_ids=[e['source_id'] for e in directional], scoring_policy='provisional-direction-v1')
        return result
    if not searches:
        return result
    absence = (claim.verification_target and not claim.personal_advice
        and claim.relation_type in ('categorical', 'attribution') and complete
        and review.decomposition_faithful and not review.analysis_overreach
        and review.conclusion == 'insufficient' and review.search_finding == 'no_support_found'
        and review.entity_resolved and review.absence_weakens_claim and len(objectives) == 4
        and contextual and not any(e['stance'] for e in evidence)
        and all(s.get('executed') for s in searches))
    direct = [e for e in contextual if e.get('retrieval_kind') != 'provider_excerpt']
    traceability = 1.0 if direct else .5 if contextual else 0.0
    context = 1.0 if review.entity_resolved else .5
    dimensions = {'D': float(complete and review.decomposition_faithful),
                  'R': len(objectives)/4, 'T': traceability, 'C': context}
    reliability = (.75 if direct else .60) if absence else .35
    acs = 100*geometric_measured(list(dimensions.values()))*reliability
    # Zero is exactly zero supporting observations in this inspected set. It
    # is NOT the directional ESS formula or an assertion of 0% factual truth.
    result.update(state='NO_SUPPORT_FOUND' if absence else 'HUMAN_REVIEW_REQUIRED'
                  if claim.personal_advice else 'INCONCLUSIVE',
        ess=0.0 if absence else 50.0, acs=acs, acs_upper_bound=None,
        ess_measurement='observed_support' if absence else 'undetermined_support', dimensions=dimensions,
        reasons=['SEARCH_WITHOUT_SUPPORT' if absence else 'DIRECTION_UNDETERMINED'],
        preliminary=True, proof_basis='search_without_support' if absence else 'research_limited',
        evidence_used=len(contextual), evidence_excluded=len(evidence)-len(contextual),
        scoring_source_ids=[e['source_id'] for e in contextual], scoring_policy='search-support-v1')
    return result


def score_answer(claim, evidence, searches, review, decomposition_complete, p=DEFAULTS):
    condensed = []
    for intent in ('support', 'contradiction', 'neutral', 'primary'):
        matching = [s for s in searches if intent in search_objectives(s)]
        if matching:
            condensed.append(next((s for s in matching if s.get('executed')), matching[0]))
    result = strict_score(claim, evidence, condensed, review, decomposition_complete, p)
    result['strict_diagnostic'] = {k: result[k] for k in ('state', 'ess', 'acs', 'reasons')}
    usable = [e for e in evidence if e['stance'] and all(e.get(k) is not None for k in
              ('source_quality', 'relevance', 'context_fit')) and e['relevance'] >= .5 and e['context_fit'] >= .5]
    if not usable or not claim.verifiable:
        if claim.verifiable and claim.high_risk and not claim.personal_advice:
            result['state'] = 'INCONCLUSIVE'
        return apply_research_gate(score_search_finding(claim, evidence, searches, review,
                                                        decomposition_complete, result, p), searches)
    weighted = []
    for e in usable:
        # Discount derived synthesis in the mass, without pretending its text
        # was independently checked against the underlying page.
        factor = p.provider_excerpt_weight if e.get('retrieval_kind') == 'provider_excerpt' else 1.0
        weighted.append({**e, 'stance': e['stance']*factor})
    direct = [e for e in weighted if e.get('retrieval_kind') != 'provider_excerpt']
    # A cautious direction (e.g. causality not established) is not a defect in
    # how well that finding was documented. Sufficiency of the procedure uses
    # inspected evidential capacity; ESS alone uses signed directional strength.
    direct_capacity = masses([{**e, 'stance': 1.0} for e in direct], p)['mass']
    direct_covered = {i for e in direct for i in e['covered_elements']}
    direct_complete = len(direct_covered) == len(claim.elements) or result['proof_basis'] == 'necessary_element_refuted'
    direct_sufficient = direct_complete and direct_capacity >= p.minimum_mass
    # A derivative search summary cannot dilute or multiply sufficient
    # inspected proof. It remains visible in the source audit and catalogue.
    basis = direct if direct_sufficient else weighted
    m = masses(basis, p)
    if m['mass'] <= 0:
        return apply_research_gate(result, searches)
    completion = research_completion(searches)
    retrieval = len(completion['required'] - completion['missing'])/len(REQUIRED_OBJECTIVES)
    covered = {i for e in basis for i in e['covered_elements']}
    coverage = len(covered)/len(claim.elements)
    if result['proof_basis'] == 'necessary_element_refuted':
        coverage = 1.0
    # D measures completed structural and semantic checks. A missing semantic
    # check earns no credit for that half; it is not a guessed ground-truth recall.
    decomposition = (float(decomposition_complete) + float(bool(review and review.decomposition_faithful)))/2
    # Quality earns explicit credit; a large collection of weak sources does
    # not become adequate merely by accumulating mass.
    counts = Counter(e['group'] for e in basis)
    group_weights = [1/(len(counts)*counts[e['group']]) for e in basis]
    quality = geometric_measured([e['source_quality'] for e in basis], group_weights)
    capacity = masses([{**e, 'stance': p.provider_excerpt_weight
                       if e.get('retrieval_kind') == 'provider_excerpt' else 1.0}
                       for e in basis], p)['mass']
    adequacy = min(1, capacity/p.minimum_mass)*coverage*quality
    context = geometric_measured([e['context_fit'] for e in basis], group_weights)
    stability = attribute_stability(basis, p)
    excerpt_share = sum(w for e, w in zip(basis, group_weights)
                        if e.get('retrieval_kind') == 'provider_excerpt')
    unverified_direct_share = sum(w for e, w in zip(basis, group_weights)
        if e.get('retrieval_kind') != 'provider_excerpt' and not e.get('origin_verified'))
    traceability = 1 - .65*excerpt_share - .15*unverified_direct_share
    dimensions = {'D': decomposition, 'R': retrieval, 'E': adequacy, 'C': context,
                  'Rob': stability, 'T': traceability}
    # Multiplicative discounts retain differences in quality and coverage
    # even among answers with the same kind of source limitation.
    acs = 100*geometric_measured([decomposition, retrieval, adequacy, context, stability])*traceability
    if not review:
        acs = min(acs, 50)
    if not decomposition_complete or (review and not review.decomposition_faithful):
        acs = min(acs, 50)
    if review and review.analysis_overreach:
        acs = min(acs, 30)
    ess = m['candidate_ess']
    if claim.personal_advice:
        state = 'HUMAN_REVIEW_REQUIRED'
    elif m['conflict'] >= p.conflict and m['positive'] and m['negative']:
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
        state = 'CONTESTED' if m['positive'] and m['negative'] else 'INCONCLUSIVE'
    warnings = []
    if coverage < 1: warnings.append('PARTIAL_COVERAGE')
    if excerpt_share: warnings.append('PARTIAL_PROVIDER_EXCERPTS')
    if direct_sufficient and any(e.get('retrieval_kind') == 'provider_excerpt' and
            e['stance']*(m['positive']-m['negative']) < 0 for e in weighted):
        warnings.append('UNVERIFIED_COUNTEREVIDENCE')
        acs *= .85
    if acs < p.acceptance: warnings.append('LOW_ACS')
    if not decomposition_complete or (review and not review.decomposition_faithful):
        warnings.append('DECOMPOSITION_INCOMPLETE')
    if review and review.analysis_overreach: warnings.append('ANSWER_OVERREACH')
    result.update(m, state=state, ess=ess, acs=acs, acs_upper_bound=None,
                  dimensions=dimensions, reasons=warnings, preliminary=acs < p.acceptance,
                  evidence_used=len(basis), evidence_excluded=len(evidence)-len(basis),
                  source_removal_stability=robustness(basis, p),
                  scoring_source_ids=[e['source_id'] for e in basis],
                  evidential_capacity=capacity,
                  scoring_policy='anchored-economical-v3')
    return apply_research_gate(result, searches)
