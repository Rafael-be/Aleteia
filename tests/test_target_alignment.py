"""Original hypotheses, corrected answers and evidence directions stay distinct."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from src.core.contracts import Extraction, Qualification
from src.core.research_intake import recover_research_task
from src.services.analysis_service import analyze, apply_resolved_scopes, validate_annotations
from test_core import claim
from test_analysis_pipeline import document, qualification, response
import test_analysis_pipeline as fixtures


class TargetAlignmentTests(unittest.TestCase):
    def extracted(self, original, correction):
        extraction = Extraction(kind='FACTUAL', claims=[claim(text=correction, original_span=original)],
                                omitted_material=False, decomposition_complete=True)
        return recover_research_task(extraction, original, []).claims[0]

    def annotated(self, target, stance, conclusion):
        data = qualification()
        data['evidence'][0]['stance'] = stance
        data['reviews'][0].update(evaluated_target=target.text, conclusion=conclusion)
        return data

    def test_extractor_cannot_replace_causal_question_by_its_corrected_answer(self):
        original = 'paracetamol causa autismo no bebê se a mão ingerir durante a gestação?'
        target = self.extracted(original, 'Não foi demonstrado que paracetamol na gestação cause autismo.')
        self.assertEqual(target.text, original)
        self.assertEqual(target.original_span, original)
        self.assertTrue(target.verification_target)

    def test_original_negation_survives_extraction_without_guessing_its_polarity(self):
        original = 'Paracetamol não causa autismo durante a gestação?'
        target = self.extracted(original, 'Paracetamol causa autismo na gestação.')
        self.assertEqual(target.text, original)
        self.assertTrue(target.verification_target)

    def test_declarative_assertions_keep_the_submitted_hypothesis_without_question_mark(self):
        for original in ['Paracetamol causa autismo na gestação.', 'Paracetamol não causa autismo na gestação.']:
            with self.subTest(original=original):
                target = self.extracted(original, 'A conclusão corrigida não substitui a hipótese.')
                self.assertTrue(target.verification_target)
                self.assertEqual(target.text, original)

    def test_recovery_does_not_turn_declarative_hypothesis_into_its_correction(self):
        original = 'Paracetamol causa autismo durante a gestação.'
        extraction = Extraction(kind='NEEDS_CONTEXT', claims=[], omitted_material=False,
                                decomposition_complete=False)
        target = recover_research_task(extraction, original, []).claims[0]
        self.assertTrue(target.verification_target)
        self.assertEqual(target.text, original)

    def test_referential_hypothesis_preserves_extraction_context(self):
        original = 'Isso causa autismo?'
        extraction = Extraction(kind='FACTUAL', claims=[claim(text='Paracetamol causa autismo?',
            original_span=original, context='Isso se refere ao paracetamol discutido no turno anterior.')],
            omitted_material=False, decomposition_complete=True)
        target = recover_research_task(extraction, original, [
            {'role': 'user', 'content': 'Quero saber sobre paracetamol durante a gestação.'}]).claims[0]
        self.assertEqual(target.text, original)
        self.assertIn('paracetamol', target.context)
        self.assertTrue(target.verification_target)

    def test_extraction_cannot_invent_civil_identity_as_trusted_context(self):
        original = 'o alanzoka foi preso?'
        extraction = Extraction(kind='FACTUAL', claims=[claim(text=original,
            original_span=original, context='Alanzoka é Rodrigo de Sousa.')],
            omitted_material=False, decomposition_complete=True)
        target = recover_research_task(extraction, original, []).claims[0]
        self.assertIn(original, target.context)
        self.assertNotIn('Rodrigo de Sousa', target.context)

    def test_explicit_user_identity_is_retained_as_data(self):
        original = 'Alan Ferreira, conhecido como Alanzoka, foi preso?'
        extraction = Extraction(kind='FACTUAL', claims=[claim(text=original,
            original_span=original, context='Pessoa conhecida.')],
            omitted_material=False, decomposition_complete=True)
        target = recover_research_task(extraction, original, []).claims[0]
        self.assertIn('Alan Ferreira', target.context)

    def test_open_topic_is_not_promoted_to_an_assertion(self):
        original = 'História da descoberta do autismo'
        extraction = Extraction(kind='FACTUAL', claims=[claim(text=original, original_span=original,
            investigative=True)], omitted_material=False, decomposition_complete=True)
        target = recover_research_task(extraction, original, []).claims[0]
        self.assertFalse(target.verification_target)

    def test_same_source_can_refute_positive_hypothesis_and_support_negated_hypothesis(self):
        passage = ('Os estudos analisados não estabeleceram relação causal entre uso de paracetamol '
                   'na gestação e autismo na criança; essa conclusão não demonstra impossibilidade.')
        for original, stance, conclusion in [
                ('Paracetamol causa autismo na gestação?', -1.0, 'refutes'),
                ('Não há relação causal estabelecida entre paracetamol na gestação e autismo?', 1.0, 'supports')]:
            with self.subTest(original=original):
                target = self.extracted(original, original)
                data = self.annotated(target, stance, conclusion)
                data['evidence'][0].update(quote=passage, origin_quote=passage)
                accepted, rejected = validate_annotations(Qualification.model_validate(data), [target],
                    [{**document(), 'text': passage}])
                self.assertFalse(rejected)
                self.assertEqual(accepted[0]['stance'], stance)

    def test_corrected_target_cannot_unlock_positive_ess_for_original_false_claim(self):
        target = self.extracted('Paracetamol causa autismo na gestação?', 'Não foi estabelecida causalidade.')
        data = self.annotated(target, 1.0, 'supports')
        data['reviews'][0]['evaluated_target'] = 'Não foi estabelecida causalidade.'
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], [document()])
        self.assertFalse(accepted)
        self.assertIn('TARGET_ALIGNMENT', [r['reason'] for r in rejected])

    def test_correct_negative_conclusion_with_inverted_evidence_fails_closed(self):
        target = self.extracted('Paracetamol causa autismo na gestação?', 'Paracetamol causa autismo.')
        data = self.annotated(target, 1.0, 'refutes')
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], [document()])
        self.assertFalse(accepted)
        self.assertIn('CONCLUSION_ALIGNMENT', [r['reason'] for r in rejected])
        # Validation does not guess whether to invert the evidence or the review.
        self.assertEqual(data['evidence'][0]['stance'], 1.0)

    def test_absent_target_binding_cannot_publish_directional_evidence(self):
        target = claim()
        data = self.annotated(target, 1.0, 'supports')
        del data['reviews'][0]['evaluated_target']
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], [document()])
        self.assertFalse(accepted)
        self.assertIn('TARGET_ALIGNMENT', [r['reason'] for r in rejected])

    def test_minority_opposing_evidence_is_preserved(self):
        target = claim()
        data = self.annotated(target, 1.0, 'supports')
        docs = [document()]
        for identifier, stance, domain in [('s2', 1.0, 'second.example'), ('s3', -.5, 'third.example')]:
            passage = f'Fonte {identifier}: observação independente do indicador e seu ano, com método público.'
            docs.append({**document(), 'id': identifier, 'url': f'https://{domain}/data',
                         'final_url': f'https://{domain}/data', 'text': passage})
            item = deepcopy(data['evidence'][0])
            item.update(source_id=identifier, stance=stance, quote=passage,
                        origin_source_id=identifier, origin_quote=passage)
            data['evidence'].append(item)
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], docs)
        self.assertFalse(rejected)
        self.assertEqual(len(accepted), 3)
        self.assertTrue(any(item['stance'] < 0 for item in accepted))

    def test_direction_uses_final_weighted_mass_instead_of_source_count(self):
        target = claim()
        data = self.annotated(target, 1.0, 'supports')
        docs = [document()]
        for identifier in ['s2', 's3']:
            passage = f'Síntese {identifier}: resultado contrário ao indicador; documento original não foi recebido.'
            docs.append({**document(), 'id': identifier, 'url': f'https://{identifier}.example/data',
                         'final_url': f'https://{identifier}.example/data', 'text': passage,
                         'retrieval_kind': 'provider_excerpt'})
            item = deepcopy(data['evidence'][0])
            item.update(source_id=identifier, stance=-1.0, quote=passage,
                        origin_source_id=None, origin_quote=None, primary=False)
            data['evidence'].append(item)
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], docs)
        self.assertFalse(rejected)
        self.assertEqual(len(accepted), 3)

    def test_closed_question_rejects_resolution_even_if_review_echoes_original_target(self):
        target = self.extracted('O indicador foi 20 em 2025?', 'O indicador foi 20 em 2025.')
        data = self.annotated(target, 1.0, 'supports')
        data['reviews'][0].update(resolved_claim='O indicador foi 30 em 2025.', resolution_source_ids=['s1'])
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], [document()])
        self.assertFalse(accepted)
        self.assertIn('TARGET_ALIGNMENT', [r['reason'] for r in rejected])

    def test_open_question_can_resolve_a_grounded_proposition(self):
        target = claim(text='Qual foi o indicador?', investigative=True)
        proposition = 'O indicador foi 20 em 2025.'
        data = self.annotated(target, 1.0, 'supports')
        data['reviews'][0].update(resolved_claim=proposition, evaluated_target=proposition,
                                 resolution_source_ids=['s1'])
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [target], [document()])
        self.assertFalse(rejected)
        self.assertEqual(len(accepted), 1)

    def test_explanatory_scope_preserves_original_target_and_its_negation(self):
        original = 'A redação de 2026 não foi sobre cinema?'
        target = self.extracted(original, 'A redação de 2019 foi sobre cinema.')
        data = self.annotated(target, -1.0, 'refutes')
        data['resolved_scopes'] = [{'id': 'history', 'parent_claim_id': target.id,
            'text': 'A redação de 2019 foi sobre cinema.', 'context': '2019',
            'elements': ['tema de 2019'], 'source_ids': ['s1']}]
        claims, lineage = apply_resolved_scopes(Qualification.model_validate(data), [target], [document()])
        self.assertEqual(claims[0].text, original)
        self.assertTrue(claims[0].verification_target)
        self.assertEqual(lineage, {'history': target.id})
        self.assertFalse(claims[1].verification_target)

    def test_blind_reader_repairs_first_reader_inversion_against_original_hypothesis(self):
        cases = [
            ('paracetamol causa autismo no bebê se a mão ingerir durante a gestação?',
             1.0, 'supports', 'refutes_partial', 'refutes', 'Não. As fontes não estabelecem relação causal.'),
            ('Paracetamol não tem relação causal estabelecida com autismo na gestação?',
             -1.0, 'refutes', 'supports_partial', 'supports', 'Sim. As fontes não estabelecem relação causal.')]
        passage = ('A análise dos estudos não estabeleceu relação causal entre uso de paracetamol '
                   'durante a gestação e autismo na criança. Isso não constitui prova de impossibilidade.')
        for original, wrong_stance, wrong_conclusion, audited_relation, audited_conclusion, answer in cases:
            with self.subTest(original=original):
                client = fixtures.PipelineTests().setup_provider()
                provider = client.responses.create.side_effect

                def create(**kwargs):
                    stage = kwargs.get('text', {}).get('format', {}).get('name')
                    if stage == 'extraction':
                        task = claim(text='Uma resposta corrigida que não pode substituir a hipótese.',
                            original_span=original, relation_type='causal', elements=['relação causal'])
                        return response(json.dumps({'kind': 'FACTUAL', 'claims': [task.model_dump()],
                            'omitted_material': False, 'decomposition_complete': True}))
                    if stage == 'qualification':
                        data = qualification()
                        data['evidence'][0].update(stance=wrong_stance, quote=passage,
                            origin_quote=passage, covered_elements=[0])
                        data['reviews'][0].update(evaluated_target=original, conclusion=wrong_conclusion,
                                                 assessment='A primeira leitura confundiu a resposta com a hipótese.')
                        return response(json.dumps(data))
                    if stage == 'semantic_alignment':
                        payload = json.loads(kwargs['input'])
                        self.assertEqual(payload['targets'][0]['evaluated_target'], original)
                        self.assertNotIn('stance', payload['targets'][0]['evidence'][0])
                        self.assertNotIn('assessment', payload['targets'][0])
                        return response(json.dumps({'targets': [{'claim_id': 'c1',
                            'evaluated_target': original, 'conclusion': audited_conclusion, 'assessment': answer,
                            'evidence': [{'source_id': 's1', 'relation': audited_relation,
                                          'reason': 'A direção é relativa à hipótese original preservada.'}]}]}))
                    return provider(**kwargs)

                client.responses.create.side_effect = create
                with patch('src.services.analysis_service.fetch_document', return_value={**document(), 'text': passage}):
                    result = list(analyze(client, 'gpt-5-mini', original))[-1]
                self.assertEqual(result['audit']['evaluated_claims'][0]['text'], original)
                ess = result['veredito']['metrics'][0]['value']
                self.assertIsNotNone(ess)
                self.assertLess(ess, 40) if audited_conclusion == 'refutes' else self.assertGreater(ess, 60)
                self.assertIn(answer, result['text'])
                self.assertNotIn('A primeira leitura confundiu', result['text'])
                self.assertEqual(result['veredito']['retrieval']['queries_executed'], 2)
                self.assertEqual(client.responses.create.call_count, 6)
                self.assertEqual({objective for search in result['audit']['searches']
                                  for objective in search['objectives']},
                                 {'support', 'contradiction', 'neutral', 'primary'})
