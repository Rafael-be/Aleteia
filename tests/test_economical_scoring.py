"""Evidence quality, direction and dependence in the economical publication policy."""
import unittest
from typing import Literal

from src.core.answer_policy import score_answer
from src.core.contracts import ClaimReview
from test_core import claim, evidence


SEARCHES = [{'intent': intent, 'executed': True}
            for intent in ('support', 'contradiction', 'neutral', 'primary')]
Conclusion = Literal['supports', 'refutes', 'mixed', 'insufficient']


def reviewed(target, conclusion: Conclusion = 'supports'):
    return ClaimReview(claim_id=target.id, context_complete=True,
        decomposition_faithful=True, causal_overreach=False,
        evaluated_target=target.text, conclusion=conclusion)


def assessed(items, conclusion: Conclusion = 'supports'):
    target = claim()
    return score_answer(target, items, SEARCHES, reviewed(target, conclusion), True)


class EconomicalScoringTests(unittest.TestCase):
    def test_well_documented_partial_direction_does_not_mean_low_process_quality(self):
        direct = evidence(stance=-.5, source_quality=.75, retrieval_kind='direct_document',
                          origin_verified=False)
        result = assessed([direct], 'refutes')
        self.assertLess(result['ess'], 40)
        self.assertGreaterEqual(result['acs'], 80)
        supplemented = assessed([direct]+[
            evidence('summary'+str(i), 'unknown', stance=-.5, source_quality=.5,
                     retrieval_kind='provider_excerpt', origin_verified=False) for i in range(8)], 'refutes')
        self.assertAlmostEqual(result['ess'], supplemented['ess'])
        self.assertAlmostEqual(result['acs'], supplemented['acs'])
        self.assertEqual(supplemented['scoring_source_ids'], ['s1'])

    def test_failed_decomposition_review_cannot_receive_high_quality(self):
        target = claim()
        review = reviewed(target).model_copy(update={'decomposition_faithful': False})
        result = score_answer(target, [evidence()], SEARCHES, review, True)
        self.assertLessEqual(result['acs'], 50)
        self.assertIn('DECOMPOSITION_INCOMPLETE', result['reasons'])

    def test_one_fully_qualified_direct_source_can_have_high_process_confidence(self):
        cases: tuple[tuple[float, Conclusion], ...] = ((1.0, 'supports'), (-1.0, 'refutes'))
        for stance, conclusion in cases:
            with self.subTest(stance=stance):
                result = assessed([evidence(stance=stance, retrieval_kind='direct_document')], conclusion)
                self.assertGreater(result['acs'], 85)
                self.assertEqual(result['evidence_used'], 1)
                self.assertGreater(abs(result['ess']-50), 35)
                self.assertLess(result['source_removal_stability'], result['dimensions']['Rob'])

    def test_weak_source_does_not_earn_high_quality_by_itself(self):
        result = assessed([evidence(source_quality=.25, retrieval_kind='direct_document')])
        self.assertLessEqual(result['acs'], 85)
        self.assertLess(result['acs'], assessed([evidence()])['acs'])

    def test_source_limits_do_not_flatten_different_cases_to_the_same_quality(self):
        for kind, old_cap in (('direct_document', 85), ('provider_excerpt', 35)):
            with self.subTest(kind=kind):
                better = assessed([evidence(source_quality=1.0, retrieval_kind=kind, origin_verified=False)])
                weaker = assessed([evidence(source_quality=.75, context_fit=.5,
                                            retrieval_kind=kind, origin_verified=False)])
                self.assertLessEqual(better['acs'], old_cap)
                self.assertGreater(better['acs'], weaker['acs'])

    def test_one_hundred_same_origin_copies_leave_both_indices_unchanged(self):
        baseline = assessed([evidence()])
        copies = assessed([evidence('copy'+str(i)) for i in range(100)])
        self.assertAlmostEqual(baseline['ess'], copies['ess'])
        self.assertAlmostEqual(baseline['acs'], copies['acs'])

    def test_repeating_weaker_origin_cannot_dilute_process_quality(self):
        strong = evidence('strong', 'primary')
        weak = evidence('weak', 'secondary', source_quality=.25)
        baseline = assessed([strong, weak])
        repeated = assessed([strong, weak]+[
            evidence('copy'+str(i), 'secondary', source_quality=.25) for i in range(100)])
        self.assertAlmostEqual(baseline['ess'], repeated['ess'])
        self.assertAlmostEqual(baseline['acs'], repeated['acs'])

    def test_agreeing_search_syntheses_do_not_dilute_sufficient_direct_proof(self):
        direct = evidence(retrieval_kind='direct_document')
        baseline = assessed([direct])
        supplemented = assessed([direct]+[
            evidence('summary'+str(i), 'summary', source_quality=.5,
                     retrieval_kind='provider_excerpt', origin_verified=False) for i in range(8)])
        self.assertAlmostEqual(baseline['ess'], supplemented['ess'])
        self.assertAlmostEqual(baseline['acs'], supplemented['acs'])
        self.assertEqual(supplemented['scoring_source_ids'], ['s1'])

    def test_independent_direct_conflict_cannot_be_published_as_directional_certainty(self):
        result = assessed([evidence('for', 'g1'), evidence('against', 'g2', stance=-1.0)], 'mixed')
        self.assertEqual(result['state'], 'CONTESTED')
        self.assertAlmostEqual(result['ess'], 50)
        # ACS describes the quality of this conclusion; it need not be low
        # when a sound review correctly identifies conflicting observations.
        self.assertIsNotNone(result['acs'])

    def test_unverified_contradictory_synthesis_is_visible_without_overriding_direct_proof(self):
        baseline = assessed([evidence(retrieval_kind='direct_document')])
        result = assessed([evidence(retrieval_kind='direct_document'),
            evidence('summary', 'unknown', stance=-1.0, source_quality=.5,
                     retrieval_kind='provider_excerpt', origin_verified=False)])
        self.assertAlmostEqual(baseline['ess'], result['ess'])
        self.assertLessEqual(result['acs'], 85)
        self.assertIn('UNVERIFIED_COUNTEREVIDENCE', result['reasons'])

    def test_absent_rubric_attributes_do_not_generate_factual_certainty(self):
        for attribute in ('source_quality', 'relevance', 'context_fit'):
            with self.subTest(attribute=attribute):
                item = evidence()
                item[attribute] = None
                result = assessed([item])
                self.assertGreater(result['ess'], 50)
                self.assertEqual(result['ess_measurement'], 'provisional_direction')
                self.assertEqual(result['state'], 'PREDOMINANTLY_SUPPORTED')
                self.assertLessEqual(result['acs'], 35)


if __name__ == '__main__':
    unittest.main()
