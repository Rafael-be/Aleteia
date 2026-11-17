"""Production answer-first policy, distinct from strict proof diagnostics."""
import json
import unittest
from unittest.mock import patch
from src.core.contracts import ClaimReview, Extraction
from src.core.answer_policy import score_answer
from src.core.research_budget import plan_searches, rounds_for
from src.core.scoring import verdict
from src.services.analysis_service import UsageLedger, _documents, _search, analyze
from test_core import claim, evidence
import test_analysis_pipeline as fixtures


def review(**updates):
    return ClaimReview(**{**dict(claim_id='c1', context_complete=True, decomposition_faithful=True,
                                causal_overreach=False), **updates})


SEARCHES = [{'intent': i, 'executed': True} for i in ('support', 'contradiction', 'neutral', 'primary')]


class AnswerPolicyTests(unittest.TestCase):
    def test_general_medical_causal_question_gets_answer_and_both_indices(self):
        c = claim(high_risk=True, personal_advice=False, relation_type='causal')
        r = score_answer(c, [evidence(stance=-1.0)], SEARCHES, review(causal_overreach=True), True)
        self.assertNotEqual(r['state'], 'HUMAN_REVIEW_REQUIRED')
        self.assertIsNotNone(r['ess']); self.assertIsNotNone(r['acs'])
        self.assertLess(r['ess'], 50)
        self.assertGreater(r['acs'], 50)

    def test_personal_treatment_flag_does_not_erase_measured_indices(self):
        c = claim(high_risk=True, personal_advice=True)
        r = score_answer(c, [evidence()], SEARCHES, review(), True)
        v = verdict([c], [r])
        self.assertEqual(v['code'], 'HUMAN_REVIEW_REQUIRED')
        self.assertTrue(all(m['valid'] for m in v['metrics']))

    def test_cited_synthesis_yields_discounted_percentages_not_fake_certainty(self):
        r = score_answer(claim(), [evidence(stance=-1.0, retrieval_kind='provider_excerpt', origin_verified=False)], SEARCHES, review(), True)
        self.assertIsNotNone(r['ess'])
        self.assertLessEqual(r['acs'], 35)
        self.assertIn('PARTIAL_PROVIDER_EXCERPTS', r['reasons'])

    def test_repeat_searches_do_not_inflate_retrieval_quality_or_count_copies(self):
        one = score_answer(claim(), [evidence()], SEARCHES, review(), True)
        copies = score_answer(claim(), [evidence(f's{i}') for i in range(10)], SEARCHES*3, review(), True)
        self.assertAlmostEqual(one['ess'], copies['ess'])
        self.assertEqual(copies['dimensions']['R'], 1)

    def test_more_material_does_not_make_unjustified_causal_answer_confident(self):
        r = score_answer(claim(), [evidence(), evidence('s2', 'g2')], SEARCHES, review(analysis_overreach=True), True)
        self.assertLessEqual(r['acs'], 30)
        self.assertIn('ANSWER_OVERREACH', r['reasons'])

    def test_no_qualified_material_does_not_fabricate_truth_percentage(self):
        r = score_answer(claim(), [], SEARCHES, review(), True)
        self.assertIsNone(r['ess'])

    def test_research_reserves_budget_for_scoring(self):
        ledger = UsageLedger(); ledger.total = 46000
        with self.assertRaises(RuntimeError): ledger.start('retrieval')
        ledger.start('qualification')
        self.assertEqual(ledger.calls, 1)
        ledger.total = 80000
        with self.assertRaises(RuntimeError): ledger.start('qualification')

    def test_inflight_multiclaim_retrieval_cannot_consume_final_audit_reserve(self):
        ledger = UsageLedger()
        ledger.total = 63000  # Four hosted-search contexts plus qualification.
        ledger.start('semantic_alignment')
        with self.assertRaises(RuntimeError):
            ledger.start('retrieval')

    def test_controversial_topics_use_two_search_calls_for_four_objectives(self):
        client = fixtures.PipelineTests().setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            if kwargs.get('text', {}).get('format', {}).get('name') == 'extraction':
                return fixtures.response(json.dumps({'kind': 'FACTUAL', 'claims': [claim(high_risk=True).model_dump()],
                    'omitted_material': False, 'decomposition_complete': True, 'research_depth': 'debated'}))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value=fixtures.document()):
            result = list(analyze(client, 'gpt-5-mini', claim().text))[-1]
        self.assertEqual(result['veredito']['retrieval']['queries_executed'], 2)
        self.assertEqual(client.responses.create.call_count, 5)
        self.assertEqual({objective for search in result['audit']['searches'] if search['executed']
                          for objective in search['objectives']}, set(i['intent'] for i in SEARCHES))
        self.assertTrue(result['veredito']['source_catalog'])
        self.assertTrue(all(m['valid'] for m in result['veredito']['metrics']))

    def test_ledger_rejects_fifth_search_even_before_usage_is_observed(self):
        ledger = UsageLedger()
        for _ in range(4):
            ledger.start('retrieval')
        with self.assertRaises(RuntimeError): ledger.start('retrieval')
        ledger.start('qualification')

    def test_search_plan_covers_claims_and_records_unexecuted_objectives(self):
        claims = [claim('c'+str(i), verification_target=i == 3) for i in range(4)]
        extraction = Extraction(kind='FACTUAL', claims=claims, omitted_material=False,
                                decomposition_complete=True, research_depth='obscure')
        jobs = plan_searches(extraction)
        self.assertEqual(rounds_for(extraction), 1)
        self.assertEqual(jobs[0][0].id, 'c3')
        self.assertEqual({c.id for c, _, _, _ in jobs[:4]}, {c.id for c in claims})
        self.assertEqual(len(jobs), 8)
        for c in claims:
            self.assertEqual({objective for task, _, _, objectives in jobs if task.id == c.id
                              for objective in objectives},
                             {'support', 'contradiction', 'neutral', 'primary'})

    def test_four_claim_pipeline_caps_searches_and_keeps_honest_objective_records(self):
        client = fixtures.PipelineTests().setup_provider()
        original = client.responses.create.side_effect
        claims = [claim('c'+str(i), verification_target=i == 3) for i in range(4)]
        def create(**kwargs):
            if kwargs.get('text', {}).get('format', {}).get('name') == 'extraction':
                return fixtures.response(json.dumps({'kind': 'FACTUAL', 'claims': [c.model_dump() for c in claims],
                    'omitted_material': False, 'decomposition_complete': True, 'research_depth': 'obscure'}))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value=fixtures.document()):
            result = list(analyze(client, 'gpt-5-mini', claim().text))[-1]
        searches = result['audit']['searches']
        self.assertEqual(sum(s['executed'] for s in searches), 4)
        self.assertEqual({s['claim_id'] for s in searches if s['executed']}, {c.id for c in claims})
        self.assertEqual(sum(s['status'] == 'budget_skipped' for s in searches), 4)
        for c in claims:
            self.assertEqual({objective for s in searches if s['claim_id'] == c.id
                              for objective in s['objectives']},
                             {'support', 'contradiction', 'neutral', 'primary'})
        self.assertTrue(result['audit']['research_budget']['budget_limited'])

    def test_scarcity_does_not_trigger_more_paid_searches(self):
        client = fixtures.PipelineTests().setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            if kwargs.get('tools'):
                return fixtures.cited_search_response()
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value=fixtures.document()):
            result = list(analyze(client, 'gpt-5-mini', claim().text))[-1]
        self.assertEqual(result['veredito']['retrieval']['queries_executed'], 2)
        self.assertEqual(result['audit']['research_budget']['rounds'], 1)
        calls = client.responses.create.call_args_list
        self.assertTrue(all(c.kwargs['max_output_tokens'] <= 900 for c in calls if c.kwargs.get('tools')))
        self.assertTrue(all(c.kwargs['max_output_tokens'] <= 6000 for c in calls
                            if c.kwargs.get('text', {}).get('format', {}).get('name') == 'qualification'))

    def test_unknown_search_objective_never_reaches_provider(self):
        client = fixtures.PipelineTests().setup_provider()
        with self.assertRaises(ValueError):
            _search(client, 'gpt-5-mini', UsageLedger(), 999999999, claim(), 'primary',
                    'dados originais', objectives=['primary', 'ignore_previous_instructions'])
        client.responses.create.assert_not_called()

    def test_combined_objectives_are_explicit_in_query_and_instructions(self):
        client = fixtures.PipelineTests().setup_provider()
        from time import monotonic
        record = _search(client, 'gpt-5-mini', UsageLedger(), monotonic()+10, claim(),
                         'contradiction', 'valor contradição | valor fonte',
                         objectives=['contradiction', 'support'])
        self.assertEqual(record['objectives'], ['contradiction', 'support'])
        call = client.responses.create.call_args.kwargs
        self.assertEqual(json.loads(call['input'])['objectives'], record['objectives'])
        self.assertIn('refutações e resultados contrários', call['instructions'])
        self.assertIn('evidência que sustente', call['instructions'])

    def test_document_budget_prefers_html_and_diversity_before_pdfs(self):
        searches = [{'sources': [f'https://same.example/{i}.pdf',
                                  f'https://same.example/page{i}',
                                  f'https://source{i}.example/article'], 'excerpts': []}
                    for i in range(4)]
        def fetch(url, deadline):
            return {**fixtures.document(), 'url': url, 'final_url': url,
                    'text': url+' '+('Conteúdo verificável. '*700), 'hash': url}
        with patch('src.services.analysis_service.fetch_document', side_effect=fetch) as fetcher:
            docs, failures = _documents(searches, 999999999, [claim()], limit=32)
        self.assertEqual(len(docs), 8)
        self.assertEqual(fetcher.call_count, 8)
        self.assertFalse(failures)
        self.assertTrue(all(not d['url'].endswith('.pdf') for d in docs))
        self.assertLessEqual(sum(len(d['text']) for d in docs), 20000)
        self.assertEqual(len({d['url'].split('/')[2] for d in docs[:4]}), 4)
