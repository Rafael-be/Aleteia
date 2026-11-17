"""Blind direction checking: an inspected quote never becomes its own target."""
import unittest
from src.core.contracts import Qualification
from src.core.semantic_alignment import (SemanticAlignment, alignment_input, apply_alignment)
from test_analysis_pipeline import qualification, document, TEXT
from test_core import claim


class SemanticAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.claim = claim(verification_target=True)
        self.qualification = Qualification.model_validate(qualification())
        self.document = {**document(), 'retrieval_kind': 'direct_document'}
        self.payload = alignment_input(self.qualification, [self.claim], [self.document])

    def decision(self, **updates):
        target = dict(claim_id='c1', evaluated_target=self.claim.text, conclusion='refutes',
                      assessment='O documento contradiz a hipótese apresentada.',
                      evidence=[dict(source_id='s1', relation='refutes_direct', reason='Valor incompatível.')])
        return SemanticAlignment.model_validate({'targets': [{**target, **updates}]})

    def test_second_reader_does_not_receive_first_votes_answer_or_resolution(self):
        serialized = str(self.payload)
        self.assertNotIn('stance', serialized)
        self.assertNotIn('assessment', serialized)
        self.assertNotIn('conclusion', serialized)
        self.assertNotIn('resolved_claim', serialized)
        self.assertEqual(self.payload['targets'][0]['evaluated_target'], self.claim.text)
        self.assertEqual(self.payload['targets'][0]['evidence'][0]['quote'], TEXT)

    def test_independent_direction_replaces_wrong_positive_without_arithmetic_flip(self):
        updated = apply_alignment(self.qualification, [self.claim], self.payload, self.decision())
        self.assertEqual(self.qualification.evidence[0].stance, 1)
        self.assertEqual(updated.evidence[0].stance, -1)
        self.assertEqual(updated.reviews[0].conclusion, 'refutes')
        self.assertIsNone(updated.reviews[0].resolved_claim)

    def test_different_target_missing_or_duplicate_ids_are_rejected(self):
        for changes in ({'evaluated_target': 'Uma correção verdadeira diferente'},
                        {'evidence': []},
                        {'evidence': [dict(source_id='unknown', relation='neutral', reason='Sem suporte.')]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_alignment(self.qualification, [self.claim], self.payload, self.decision(**changes))
        bad = self.decision()
        bad.targets.append(bad.targets[0])
        with self.assertRaises(ValueError):
            apply_alignment(self.qualification, [self.claim], self.payload, bad)

    def test_unanchored_evidence_cannot_reach_auditor_or_scoring(self):
        q = self.qualification.model_copy(update={'evidence': [self.qualification.evidence[0].model_copy(
            update={'quote': 'Uma frase inventada ausente do documento.'})]})
        payload = alignment_input(q, [self.claim], [self.document])
        self.assertEqual(payload['targets'][0]['evidence'], [])
        audit = self.decision(conclusion='insufficient', evidence=[])
        updated = apply_alignment(q, [self.claim], payload, audit)
        self.assertEqual(updated.evidence, [])

    def test_partial_contradiction_does_not_reuse_direct_refutation_marker(self):
        q = self.qualification.model_copy(update={'evidence': [self.qualification.evidence[0].model_copy(
            update={'refutation_kind': 'explicit_contradiction', 'refutes_elements': [0]})]})
        judgment = self.decision(evidence=[dict(source_id='s1', relation='refutes_partial',
            reason='A causalidade não foi demonstrada; impossibilidade não foi provada.')])
        updated = apply_alignment(q, [self.claim], self.payload, judgment)
        self.assertEqual(updated.evidence[0].stance, -.5)
        self.assertEqual(updated.evidence[0].refutes_elements, [])
        self.assertEqual(updated.evidence[0].refutation_kind, 'none')

    def test_correlation_cannot_become_support_for_causal_hypothesis(self):
        causal = self.claim.model_copy(update={'relation_type': 'causal'})
        judgment = self.decision(conclusion='insufficient', evidence=[dict(source_id='s1',
            relation='supports_partial', inference_basis='association_only',
            reason='Associação sem identificação causal.')])
        updated = apply_alignment(self.qualification, [causal], self.payload, judgment)
        self.assertEqual(updated.evidence[0].stance, 0)
        statistical = causal.model_copy(update={'relation_type': 'statistical'})
        updated = apply_alignment(self.qualification, [statistical], self.payload, judgment)
        self.assertEqual(updated.evidence[0].stance, .5)

    def test_causal_uncertainty_is_not_a_direct_disproof(self):
        causal = self.claim.model_copy(update={'relation_type': 'causal'})
        judgment = self.decision(evidence=[dict(source_id='s1', relation='refutes_direct',
            inference_basis='causal_uncertainty', reason='Causalidade não estabelecida.')])
        updated = apply_alignment(self.qualification, [causal], self.payload, judgment)
        self.assertEqual(updated.evidence[0].stance, -.5)
        self.assertEqual(updated.evidence[0].refutation_kind, 'none')

    def test_secondary_summary_is_not_a_primary_causal_result(self):
        causal = self.claim.model_copy(update={'relation_type': 'causal'})
        q = self.qualification.model_copy(update={'evidence': [self.qualification.evidence[0].model_copy(
            update={'primary': False, 'origin_source_id': None, 'origin_quote': None})]})
        payload = alignment_input(q, [causal], [self.document])
        judgment = self.decision(evidence=[dict(source_id='s1', relation='refutes_direct',
            inference_basis='causal_result', reason='Síntese declara causalidade não confirmada.')])
        updated = apply_alignment(q, [causal], payload, judgment)
        self.assertEqual(updated.evidence[0].stance, -.5)
        self.assertEqual(updated.evidence[0].refutation_kind, 'none')


if __name__ == '__main__':
    unittest.main()
