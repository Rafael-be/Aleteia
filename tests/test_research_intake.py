"""Short inputs trigger research, while truly missing referents request detail."""
import unittest
from src.core.contracts import Extraction, ClaimReview
from src.core.research_intake import has_topic, recover_research_task
from test_core import claim, evidence, score


class ResearchIntakeTests(unittest.TestCase):
    def pending(self, **changes):
        return Extraction(**{**dict(kind='NEEDS_CONTEXT', claims=[], omitted_material=False,
                                  decomposition_complete=False), **changes})

    def test_basic_short_inputs_trigger_four_search_intents(self):
        for text in ['a redação do enem foi sobre cinema brasileiro?', 'café faz mal?',
                     'PIB?', 'vacina causa autismo?', 'quem inventou o avião?', '2+2?']:
            with self.subTest(text=text):
                result = recover_research_task(self.pending(), text, [])
                self.assertEqual(result.kind, 'FACTUAL')
                self.assertTrue(result.claims[0].investigative)
                self.assertEqual(result.claims[0].original_span, text)
                self.assertEqual(len(result.claims[0].queries), 4)

    def test_pronouns_without_antecedent_do_not_invent_a_subject(self):
        for text in ['isso é verdade?', 'é seguro?', 'quem é ele?', 'qual é a fonte?']:
            self.assertFalse(has_topic(text), text)
            self.assertEqual(recover_research_task(self.pending(), text, []).kind, 'NEEDS_CONTEXT')

    def test_followup_uses_users_topic_instead_of_assistant_instructions(self):
        context = [{'role': 'user', 'content': 'a redação do enem foi sobre cinema brasileiro?'},
                   {'role': 'assistant', 'content': 'Não há dados suficientes.'}]
        result = recover_research_task(self.pending(), 'isso é verdade?', context)
        self.assertEqual(result.claims[0].original_span, context[0]['content'])

    def test_hard_limits_scope_and_risk_survive_recovery(self):
        self.assertEqual(recover_research_task(self.pending(kind='OUT_OF_SCOPE'), 'oi', []).kind, 'OUT_OF_SCOPE')
        self.assertEqual(recover_research_task(self.pending(kind='NOT_VERIFIABLE'), 'Eu gosto de cinema', []).kind, 'NOT_VERIFIABLE')
        result = recover_research_task(self.pending(risk_requires_review=True, personal_advice=True), 'Qual remédio tomar?', [])
        self.assertTrue(result.claims[0].high_risk)
        self.assertTrue(result.claims[0].personal_advice)

    def test_question_remains_investigative_if_model_rephrases_it_as_a_statement(self):
        question = 'a redação do enem foi sobre cinema brasileiro?'
        extraction = self.pending(kind='FACTUAL', claims=[claim(
            text='A redação do Enem foi sobre cinema brasileiro.', original_span=question)],
            decomposition_complete=True)
        task = recover_research_task(extraction, question, []).claims[0]
        self.assertTrue(task.investigative)
        self.assertEqual(task.original_span, question)
        self.assertTrue(task.verification_target)

    def test_contextual_corrections_do_not_replace_the_original_verification_target(self):
        from src.core.contracts import Qualification, ResolvedScope
        from src.services.analysis_service import apply_resolved_scopes
        original = claim(text='O evento de 2026 teve o tema X.', investigative=True, verification_target=True)
        q = Qualification(evidence=[], reviews=[], resolved_scopes=[ResolvedScope(
            id='background', parent_claim_id=original.id, text='O tema X ocorreu em 2018.',
            context='2018', elements=['tema em 2018'], source_ids=['s1'])])
        scopes, _ = apply_resolved_scopes(q, [original], [{'id': 's1'}])
        self.assertEqual(scopes[0].text, original.text)
        self.assertTrue(scopes[0].verification_target)
        self.assertEqual(len(scopes), 2)

    def test_reason_question_stays_open_next_to_verification_question(self):
        verification = 'essa imagem é verdade?'
        reason = 'por que ele escreveu isso na mão?'
        extraction = self.pending(kind='FACTUAL', claims=[
            claim(original_span=verification, text=verification),
            claim('reason', original_span=reason, text=reason),
        ])
        first, second = recover_research_task(extraction, f'{verification} {reason}', []).claims
        self.assertTrue(first.verification_target)
        self.assertTrue(second.investigative)
        self.assertFalse(second.verification_target)

    def test_open_question_cannot_receive_ess_until_source_grounded_resolution(self):
        task = claim(text='Qual foi o indicador?', investigative=True)
        items = [evidence(), evidence('s2', 'g2')]
        unresolved = score(items, task)
        self.assertIsNone(unresolved['ess'])
        self.assertIn('QUESTION_NOT_RESOLVED', unresolved['reasons'])
        review = ClaimReview(claim_id=task.id, context_complete=True, decomposition_faithful=True,
                             causal_overreach=False, resolved_claim='O indicador foi 20 em 2025.',
                             resolution_source_ids=['s1', 's2'])
        resolved = score(items, task, review=review)
        self.assertIsNotNone(resolved['ess'])
        self.assertEqual(resolved['resolved_claim'], review.resolved_claim)
        invalid = score(items, task, review=review.model_copy(update={'resolution_source_ids': ['invented']}))
        self.assertIsNone(invalid['ess'])
