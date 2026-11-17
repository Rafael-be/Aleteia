"""Absence is an observed search finding, never proof of a person's history."""
import json
import unittest
from unittest.mock import patch
from src.core.answer_policy import score_answer
from src.core.contracts import ClaimReview
from src.core.scoring import verdict
from src.services.analysis_service import analyze
from test_core import claim, evidence
import test_analysis_pipeline as fixtures

QUESTION = 'o streamer alanzoka foi preso?'
SEARCHES = [{'intent': i, 'executed': True} for i in ('primary', 'neutral', 'contradiction', 'support')]


def target():
    return claim(text=QUESTION, original_span=QUESTION, verification_target=True)


def review(**updates):
    return ClaimReview(**{**dict(claim_id='c1', evaluated_target=QUESTION,
        context_complete=True, decomposition_faithful=True, causal_overreach=False,
        conclusion='insufficient', search_finding='no_support_found', entity_resolved=True,
        absence_weakens_claim=True, assessment='Não encontrei confirmação nas fontes consultadas.'), **updates})


class SearchSupportTests(unittest.TestCase):
    def test_context_and_completed_search_yield_indices_without_claiming_refutation(self):
        result = score_answer(target(), [evidence(stance=0.0, source_quality=None)], SEARCHES, review(), True)
        self.assertEqual(result['state'], 'NO_SUPPORT_FOUND')
        self.assertEqual(result['ess'], 0)
        self.assertEqual(result['positive'], 0)
        self.assertEqual(result['negative'], 0)
        self.assertGreater(result['acs'], 50)
        self.assertNotEqual(result['proof_basis'], 'necessary_element_refuted')
        self.assertEqual(verdict([target()], [result])['metrics'][0]['measurement'], 'observed_support')

    def test_cited_context_also_yields_lower_measured_process_quality(self):
        result = score_answer(target(), [evidence(stance=0.0, source_quality=None,
            retrieval_kind='provider_excerpt')], SEARCHES, review(), True)
        self.assertEqual(result['state'], 'NO_SUPPORT_FOUND')
        self.assertLessEqual(result['acs'], 60)

    def test_failure_ambiguity_confused_reports_or_missing_context_are_not_absence(self):
        for updates in ({'entity_resolved': False}, {'absence_weakens_claim': False},
                        {'search_finding': 'unclear_mentions'}, {'analysis_overreach': True}):
            with self.subTest(updates=updates):
                result = score_answer(target(), [evidence(stance=0.0)], SEARCHES, review(**updates), True)
                self.assertNotEqual(result['state'], 'NO_SUPPORT_FOUND')
        for searches, items in ((SEARCHES[:-1], [evidence(stance=0.0)]), (SEARCHES, []),
                (SEARCHES, [evidence(stance=.5, source_quality=None)]),
                ([{**s, 'executed': False} for s in SEARCHES], [evidence(stance=0.0)])):
            result = score_answer(target(), items, searches, review(), True)
            self.assertNotEqual(result['state'], 'NO_SUPPORT_FOUND')

    def test_absence_cannot_decide_causal_or_personal_questions(self):
        for updates in ({'relation_type': 'causal'}, {'personal_advice': True}, {'verifiable': False}):
            result = score_answer(target().model_copy(update=updates), [evidence(stance=0.0)], SEARCHES, review(), True)
            self.assertNotEqual(result['state'], 'NO_SUPPORT_FOUND')

    def test_complete_pipeline_retains_neutral_sources_and_gives_useful_answer(self):
        client = fixtures.PipelineTests().setup_provider()
        original = client.responses.create.side_effect
        passage = 'Documento simulado: canal de Alanzoka apresenta uma transmissão pública recente.'
        data = fixtures.qualification()
        data['evidence'][0].update(quote=passage, stance=0.0, source_quality=None,
            primary=False, origin_source_id=None, origin_quote=None)
        data['reviews'] = [review().model_dump()]
        def create(**kwargs):
            stage = kwargs.get('text', {}).get('format', {}).get('name')
            if stage == 'extraction':
                return fixtures.response(json.dumps(dict(kind='FACTUAL', claims=[target().model_dump()],
                    omitted_material=False, decomposition_complete=True)))
            if stage == 'qualification':
                return fixtures.response(json.dumps(data))
            if stage == 'semantic_alignment':
                payload = json.loads(kwargs['input'])
                self.assertEqual(len(payload['targets'][0]['searches']), 2)
                result = fixtures.semantic_fixture(payload, data)
                result['targets'][0].update(search_finding='no_support_found', entity_resolved=True,
                    absence_weakens_claim=True)
                return fixtures.response(json.dumps(result))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value={**fixtures.document(), 'text': passage}):
            result = list(analyze(client, 'gpt-5-mini', QUESTION))[-1]
        self.assertEqual(result['veredito']['code'], 'NO_SUPPORT_FOUND')
        self.assertTrue(all(m['valid'] for m in result['veredito']['metrics']))
        self.assertIn('Não encontrei confirmação', result['text'])
        self.assertTrue(result['veredito']['source_details'])
        self.assertEqual(client.responses.create.call_count, 5)


if __name__ == '__main__':
    unittest.main()
