"""Memorial examples, metamorphic properties and public metric validity gates."""
import math
import unittest
from dataclasses import replace
from pydantic import ValidationError
from src.core.contracts import Claim, ClaimReview, EvidenceAnnotation
from src.core.input_gate import is_noise
from src.core.scoring import DEFAULTS, geometric, masses, score_claim, verdict, metric


def claim(identifier='c1', **changes):
    data = dict(id=identifier, text='O indicador foi 20 em 2025.', original_span='O indicador foi 20 em 2025.',
                context='2025', materiality=1.0, critical=True, verifiable=True, high_risk=False,
                elements=['valor', 'ano'], queries=['valor fonte', 'valor contradição', 'valor dados', 'valor primário'])
    return Claim(**{**data, **changes})


def evidence(identifier='s1', group='g1', stance=1.0, **changes):
    return {**dict(source_id=identifier, group=group, claim_id='c1', stance=stance,
                  source_quality=1.0, relevance=1.0, context_fit=1.0, origin_verified=True,
                  covered_elements=[0, 1]), **changes}


def score(items, c=None, **changes):
    c = c or claim()
    args = dict(claim=c, evidence=items, searches=[{'executed': True}]*4,
                review=ClaimReview(claim_id=c.id, context_complete=True,
                                   decomposition_faithful=True, causal_overreach=False),
                decomposition_complete=True)
    return score_claim(**{**args, **changes})


class CoreTests(unittest.TestCase):
    def test_direct_refutation_of_necessary_element_is_sufficient_without_all_background(self):
        c = claim(elements=['edição', 'tema atribuído', 'origem histórica'], investigative=True, verification_target=True)
        e = evidence(stance=-1.0, primary=True, covered_elements=[1], refutes_elements=[1],
                     refutation_kind='explicit_contradiction')
        r = score([e], c)
        self.assertEqual(r['state'], 'STRONGLY_CONTRADICTED')
        self.assertLess(r['ess'], 15)
        self.assertGreaterEqual(r['acs'], 65)
        self.assertAlmostEqual(r['material_coverage'], 1/3)
        self.assertEqual(r['decision_coverage'], 1)
        self.assertEqual(r['proof_basis'], 'necessary_element_refuted')
        self.assertNotIn('MATERIAL_COVERAGE_INCOMPLETE', r['reasons'])
        from src.core.contracts import ClaimReview
        partial_context = ClaimReview(claim_id=c.id, context_complete=False,
            decomposition_faithful=True, causal_overreach=False)
        self.assertIsNotNone(score([e], c, review=partial_context)['ess'],
                             'Contexto completo da contraprova não exige investigar detalhes já dispensáveis')

    def test_partial_confirmation_does_not_get_refutation_shortcut(self):
        c = claim(elements=['ano', 'tema', 'autor'])
        e = evidence(covered_elements=[1], refutes_elements=[1], refutation_kind='explicit_contradiction')
        self.assertIsNone(score([e], c)['ess'])

    def test_wrong_context_weak_or_provider_only_contradictions_are_not_decisive(self):
        c = claim(elements=['ano', 'tema', 'autor'])
        base = evidence(stance=-1.0, covered_elements=[1], refutes_elements=[1], refutation_kind='explicit_contradiction')
        for change in [{'context_fit': 0.0}, {'stance': -.5}, {'refutation_kind': 'none'},
                       {'retrieval_kind': 'provider_excerpt'}, {'refutes_elements': [99]}]:
            with self.subTest(change=change):
                self.assertIsNone(score([{**base, **change}], c)['ess'])

    def test_decisive_counterproof_does_not_suppress_real_independent_conflict(self):
        c = claim(elements=['ano', 'tema', 'autor'])
        negative = evidence(stance=-1.0, covered_elements=[1], refutes_elements=[1], refutation_kind='explicit_contradiction')
        positive = evidence('s2', 'g2', covered_elements=[0, 1, 2])
        self.assertEqual(score([negative, positive], c)['state'], 'CONTESTED')

    def test_theme_containing_causal_words_is_an_attribution_not_a_causal_claim(self):
        from src.core.contracts import ClaimReview
        e = evidence(stance=-1.0, covered_elements=[0], refutes_elements=[0], refutation_kind='explicit_contradiction')
        review = ClaimReview(claim_id='c1', context_complete=True, decomposition_faithful=True, causal_overreach=True)
        attribution = score([e], claim(relation_type='attribution'), review=review)
        self.assertIsNotNone(attribution['ess'])
        self.assertFalse(attribution['causal_gate_applied'])
        causal = score([e], claim(relation_type='causal'), review=review)
        self.assertIsNone(causal['ess'])
        self.assertTrue(causal['causal_gate_applied'])

    def test_complete_mixed_results_are_not_mislabeled_as_insufficient_material(self):
        positive = score([evidence(), evidence('s2', 'g2')], claim(critical=False))
        negative = score([evidence(stance=-1.0), evidence('s2', 'g2', -1.0)], claim('c2', critical=False))
        self.assertEqual(verdict([claim(critical=False), claim('c2', critical=False)], [positive, negative])['code'], 'MIXED')

    def test_memorial_example(self):
        items = [evidence(stance=1.0, source_quality=.24, relevance=.24, context_fit=.24),
                 evidence('s2', 'g2', -1.0, source_quality=.06, relevance=.06, context_fit=.06)]
        result = masses(items)
        self.assertAlmostEqual(result['candidate_ess'], 68)
        self.assertAlmostEqual(result['conflict'], .1804753455623894)

    def test_low_mass_never_published(self):
        result = score([evidence(source_quality=.02, relevance=.02, context_fit=.02)])
        self.assertAlmostEqual(masses([evidence(source_quality=.02, relevance=.02, context_fit=.02)])['candidate_ess'], 54.54545454545)
        self.assertIsNone(result['ess'])
        self.assertEqual(result['state'], 'INCONCLUSIVE')

    def test_copies_do_not_inflate_mass_or_score(self):
        one = masses([evidence()])
        copies = masses([evidence(f's{i}') for i in range(10)])
        self.assertAlmostEqual(one['mass'], copies['mass'])
        self.assertAlmostEqual(one['candidate_ess'], copies['candidate_ess'])

    def test_direction_symmetry_and_monotonicity(self):
        positive = masses([evidence()])['candidate_ess']
        negative = masses([evidence(stance=-1.0)])['candidate_ess']
        self.assertAlmostEqual(positive, 100-negative)
        self.assertGreater(masses([evidence(), evidence('s2', 'g2')])['candidate_ess'], positive)

    def test_empty_and_missing_are_not_fifty_or_zero(self):
        self.assertIsNone(score([])['ess'])
        self.assertIsNone(score([])['acs'])
        missing = score([evidence(source_quality=None)])
        self.assertIsNone(missing['ess'])
        self.assertIsNone(missing['acs'])
        self.assertEqual(geometric([1, 0, 1]), 0)
        self.assertIsNone(geometric([1, None, 1]))
        self.assertEqual(geometric([0, 1], [0, 1]), 1)

    def test_conflict_distinct_from_absence(self):
        conflict = score([evidence(), evidence('s2', 'g2', -1.0)])
        self.assertEqual(conflict['state'], 'CONTESTED')
        self.assertAlmostEqual(conflict['ess'], 50)
        self.assertGreater(conflict['acs'], 65)
        self.assertEqual(score([])['state'], 'INCONCLUSIVE')

    def test_unknown_origin_caps_acs_while_unobserved_search_blocks_ess(self):
        limited = score([evidence(origin_verified=False, source_quality=.5)])
        self.assertIsNotNone(limited['ess'])
        self.assertLessEqual(limited['acs'], 35)
        self.assertTrue(limited['preliminary'])
        self.assertIn('PROVENANCE_UNCERTAIN', limited['reasons'])
        self.assertIsNone(score([evidence()], searches=[{'executed': True}]*3)['ess'])
        self.assertIsNone(score([evidence()], decomposition_complete=False)['ess'])
        self.assertIsNone(score([evidence(covered_elements=[0])])['ess'])

    def test_contradicted_can_have_high_acs(self):
        r = score([evidence(stance=-1.0), evidence('s2', 'g2', -1.0)])
        self.assertLess(r['ess'], 10)
        self.assertGreater(r['acs'], 90)

    def test_two_independent_direct_documents_still_allow_decisive_verdict(self):
        r = score([evidence(), evidence('s2', 'g2')])
        self.assertEqual(r['state'], 'STRONGLY_SUPPORTED')
        self.assertGreater(r['acs'], 90)
        self.assertFalse(r['preliminary'])

    def test_single_direct_source_answers_preliminarily_with_lower_acs(self):
        r = score([evidence(source_quality=.5)])
        self.assertIsNotNone(r['ess'])
        self.assertLessEqual(r['acs'], 55)
        self.assertTrue(r['preliminary'])
        self.assertIn('LIMITED_INDEPENDENT_SOURCES', r['reasons'])

    def test_one_complete_verified_primary_document_is_sufficient(self):
        primary = evidence(primary=True)
        r = score([primary])
        self.assertEqual(r['state'], 'STRONGLY_SUPPORTED')
        self.assertGreaterEqual(r['acs'], 65)
        self.assertNotIn('LIMITED_INDEPENDENT_SOURCES', r['reasons'])

    def test_competent_complete_secondary_document_is_not_automatically_unusable(self):
        r = score([evidence(source_quality=.75, origin_verified=False)])
        self.assertIsNotNone(r['ess'])
        self.assertGreaterEqual(r['acs'], 65)
        self.assertLessEqual(r['acs'], 75)
        self.assertIn('PROVENANCE_UNCERTAIN', r['reasons'])

    def test_irrelevant_and_optional_weak_sources_do_not_poison_direct_proof(self):
        primary = evidence(primary=True)
        extra = evidence('s2', 'unknown', retrieval_kind='provider_excerpt', origin_verified=False)
        wrong_year = evidence('s3', 'g3', -1.0, context_fit=0.0)
        unknown_neutral = evidence('s4', 'g4', 0.0, source_quality=None)
        baseline = score([primary])
        actual = score([primary, extra, wrong_year, unknown_neutral])
        self.assertEqual(actual['ess'], baseline['ess'])
        self.assertGreaterEqual(actual['acs'], 65)
        self.assertNotIn('PARTIAL_PROVIDER_EXCERPTS', actual['reasons'])
        self.assertEqual(actual['evidence_excluded'], 2)

    def test_unknown_attributes_offer_an_upper_bound_not_a_fabricated_point_score(self):
        r = score([evidence(source_quality=None, origin_verified=False, retrieval_kind='provider_excerpt')])
        self.assertIsNone(r['ess'])
        self.assertIsNone(r['acs'])
        self.assertIsNotNone(r['acs_upper_bound'])
        self.assertLessEqual(r['acs_upper_bound'], 25)
        value = metric('ACS', r['acs'], 'ATTRIBUTES_MISSING', upper_bound=r['acs_upper_bound'])
        self.assertFalse(value['valid'])
        self.assertIsNone(value['value'])
        self.assertEqual(value['measurement'], 'upper_bound')
        self.assertLessEqual(value['upper_bound'], 25)
        self.assertIsNone(score([])['acs_upper_bound'])

    def test_risk_and_nonverifiability_precede_direction(self):
        self.assertEqual(score([evidence()], claim(high_risk=True))['state'], 'HUMAN_REVIEW_REQUIRED')
        r = score([evidence()], claim(verifiable=False))
        self.assertEqual(r['state'], 'NOT_VERIFIABLE')
        self.assertIsNone(r['ess'])
        self.assertIsNone(r['acs'])

    def test_multi_claim_does_not_average_away_missing_or_critical(self):
        c1, c2 = claim(), claim('c2')
        a, b = score([evidence()]), score([], c2)
        v = verdict([c1, c2], [a, b])
        self.assertEqual(v['code'], 'INCONCLUSIVE')
        self.assertTrue(all(m['value'] is None for m in v['metrics']))
        self.assertTrue(all(m['value'] is None for m in verdict([c1], [a], incomplete=True)['metrics']))

    def test_invalid_numbers_rejected(self):
        for value in [True, math.nan, math.inf, -1, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                geometric([value])
        with self.assertRaises(ValueError):
            masses([evidence(), evidence()])
        with self.assertRaises(ValueError):
            replace(DEFAULTS, rho=0)
        with self.assertRaises(ValidationError):
            claim(materiality=True)
        from test_analysis_pipeline import qualification
        for changes in [{'stance': True}, {'source_quality': .99}, {'relevance': False}]:
            data = qualification()['evidence'][0]
            data.update(changes)
            with self.assertRaises(ValidationError):
                EvidenceAnnotation(**data)

    def test_noise_gate_conservative(self):
        for text in ['!!!', 'asdfghjkl', 'aaaaaaaaaaaa', '   ', '\x00\x01']:
            self.assertTrue(is_noise(text), text)
        for text in ['COVID?', 'PIB 2025?', 'O que significa qwerty?', '2+2?', '∫', 'π?', 'Isso é verdade?', 'x', '你好']:
            self.assertFalse(is_noise(text), text)


if __name__ == '__main__':
    unittest.main()
