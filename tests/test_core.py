"""Memorial examples, metamorphic properties and public metric validity gates."""
import math
import unittest
from dataclasses import replace
from pydantic import ValidationError
from src.core.contracts import Claim, ClaimReview, EvidenceAnnotation
from src.core.input_gate import is_noise
from src.core.scoring import DEFAULTS, geometric, masses, score_claim, verdict


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
    def test_memorial_example(self):
        items = [evidence(stance=1.0, source_quality=.24, relevance=.24, context_fit=.24),
                 evidence('s2', 'g2', -1.0, source_quality=.06, relevance=.06, context_fit=.06)]
        result = masses(items)
        self.assertAlmostEqual(result['candidate_ess'], 68)
        self.assertAlmostEqual(result['conflict'], .1804753455623894)

    def test_low_mass_never_published(self):
        result = score([evidence(source_quality=.02, relevance=.02, context_fit=.02)])
        self.assertAlmostEqual(result['candidate_ess'], 54.54545454545)
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

    def test_unknown_origin_and_unobserved_search_block_ess(self):
        self.assertIsNone(score([evidence(origin_verified=False)])['ess'])
        self.assertIsNone(score([evidence()], searches=[{'executed': True}]*3)['ess'])
        self.assertIsNone(score([evidence()], decomposition_complete=False)['ess'])
        self.assertIsNone(score([evidence(covered_elements=[0])])['ess'])

    def test_contradicted_can_have_high_acs(self):
        r = score([evidence(stance=-1.0), evidence('s2', 'g2', -1.0)])
        self.assertLess(r['ess'], 10)
        self.assertGreater(r['acs'], 90)

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
