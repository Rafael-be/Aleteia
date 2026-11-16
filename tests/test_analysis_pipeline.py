"""Offline provider/network fixtures exercise the complete V2 pipeline."""
import json
import io
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import MagicMock, patch
from time import monotonic

from src.core.contracts import Qualification
from src.services.analysis_service import (UsageLedger, analyze, validate_annotations,
                                          _search, CompleteAnswer)
from src.services.evidence_fetch import public_url, resolve_public, TextHTML, fetch_document, PinnedHTTP
from test_core import claim
import test_streaming


TEXT = 'O indicador foi 20 em 2025. Este relatório apresenta os dados originais e sua metodologia pública.'
URL = 'https://example.org/report'


def document():
    return {'id': 's1', 'url': URL, 'final_url': URL, 'title': 'Relatório', 'text': TEXT,
            'hash': sha256(TEXT.encode()).hexdigest(), 'raw_hash': 'raw', 'links': [],
            'retrieved_at': '2026-11-12T12:00:00+00:00', 'truncated': False, 'cache_hit': False}


def qualification():
    return {'evidence': [{'claim_id': 'c1', 'source_id': 's1', 'quote': TEXT,
                         'stance': 1.0, 'source_quality': 1.0, 'relevance': 1.0, 'context_fit': 1.0,
                         'covered_elements': [0, 1], 'primary': True,
                         'origin_source_id': 's1', 'origin_quote': TEXT,
                         'rationale': 'O relatório documenta o valor e o período.'}],
            'reviews': [{'claim_id': 'c1', 'context_complete': True,
                         'decomposition_faithful': True, 'causal_overreach': False,
                         'assessment': 'O relatório indica o valor 20 em 2025. Há apenas uma fonte, portanto a avaliação é preliminar.'}]}


def response(text='', output=None):
    data = {'output': output or []}
    return Obj(status='completed', output_text=text,
               usage=Obj(total_tokens=10, input_tokens=8, output_tokens=2), model_dump=lambda: data)


def cited_search_response(text=TEXT):
    content = text+' [1]'
    return response(content, output=[
        {'type': 'web_search_call', 'status': 'completed',
         'action': {'type': 'search', 'query': 'indicador 2025', 'sources': []}},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': content,
         'annotations': [{'type': 'url_citation', 'url': URL, 'title': 'Relatório',
                          'start_index': len(text)+1, 'end_index': len(content)}]}]}])


class PipelineTests(unittest.TestCase):
    def test_negative_official_fact_resolves_target_without_researching_all_background(self):
        question = 'O indicador foi 20 em 2025?'
        passage = 'O indicador oficial de 2025 foi 30, de acordo com a tabela original publicada.'
        client = self.setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            stage = kwargs.get('text', {}).get('format', {}).get('name')
            if stage == 'extraction':
                task = claim(text='O indicador foi 20 em 2025.', original_span=question,
                             elements=['valor atribuído', 'ano', 'origem da confusão'])
                return response(json.dumps({'kind': 'FACTUAL', 'claims': [task.model_dump()],
                    'omitted_material': False, 'decomposition_complete': True}))
            if stage == 'qualification':
                data = qualification()
                data['evidence'][0].update(stance=-1.0, quote=passage, origin_quote=passage,
                    covered_elements=[0], refutes_elements=[0], refutation_kind='explicit_contradiction')
                data['reviews'][0].update(assessment='Não: o valor oficial para 2025 foi 30, e não 20.', resolved_claim=None)
                data['resolved_scopes'] = [{'id': 'corrected', 'parent_claim_id': 'c1',
                    'text': 'O indicador oficial de 2025 foi 30.', 'context': 'Correção documental',
                    'elements': ['valor oficial'], 'source_ids': ['s1']}]
                background = {**data['evidence'][0], 'claim_id': 'corrected', 'stance': 1.0,
                              'refutes_elements': [], 'refutation_kind': 'none'}
                data['evidence'].append(background)
                data['reviews'].append({**data['reviews'][0], 'claim_id': 'corrected', 'assessment': 'O valor oficial foi 30.'})
                return response(json.dumps(data))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value={**document(), 'text': passage}):
            result = list(analyze(client, 'gpt-5-mini', question))[-1]
        self.assertEqual(client.responses.create.call_count, 6)
        self.assertEqual(result['veredito']['code'], 'STRONGLY_CONTRADICTED')
        self.assertTrue(all(m['valid'] for m in result['veredito']['metrics']))
        self.assertEqual(result['audit']['scores'][0]['proof_basis'], 'necessary_element_refuted')
        self.assertEqual(len(result['veredito']['claim_details']), 2)
        self.assertEqual(result['veredito']['claim_details'][1]['state'], 'STRONGLY_SUPPORTED')
        self.assertLess(result['veredito']['metrics'][0]['value'], 15,
                        'O fato corrigido não pode diluir a avaliação da atribuição falsa enviada pelo usuário')

    def test_two_contexts_are_scored_separately_using_the_same_retrieval(self):
        self.check_contexts(False)

    def test_parent_annotations_get_one_bounded_scope_requalification(self):
        self.check_contexts(True)

    def check_contexts(self, parent_annotations):
        question = 'Qual foi o indicador em 2025 ou 2026?'
        passages = ['O indicador foi 20 em 2025, conforme a tabela original publicada.',
                    'O indicador foi 30 em 2026, conforme a tabela original publicada.']
        client = self.setup_provider()
        original = client.responses.create.side_effect
        qualification_count = 0
        def create(**kwargs):
            nonlocal qualification_count
            stage = kwargs.get('text', {}).get('format', {}).get('name')
            if stage == 'extraction':
                return response(json.dumps({'kind': 'FACTUAL', 'claims': [claim(text=question, original_span=question, investigative=True).model_dump()],
                    'omitted_material': False, 'decomposition_complete': True}))
            if stage == 'qualification':
                qualification_count += 1
                data = {'evidence': [], 'reviews': [], 'resolved_scopes': []}
                for index, year in enumerate((2025, 2026)):
                    identifier = f'year{year}'
                    data['resolved_scopes'].append({'id': identifier, 'parent_claim_id': 'c1',
                        'text': passages[index], 'context': str(year), 'elements': ['valor no ano'], 'source_ids': ['s1']})
                    ev = qualification()['evidence'][0]
                    ev.update(claim_id=identifier, quote=passages[index], origin_quote=passages[index], covered_elements=[0])
                    data['evidence'].append(ev)
                    review = qualification()['reviews'][0]
                    review.update(claim_id=identifier, assessment=passages[index])
                    data['reviews'].append(review)
                if parent_annotations and qualification_count == 1:
                    for item in data['evidence'] + data['reviews']:
                        item['claim_id'] = 'c1'
                if qualification_count > 1:
                    data['resolved_scopes'] = []
                return response(json.dumps(data))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value={**document(), 'text': ' '.join(passages)}):
            result = list(analyze(client, 'gpt-5-mini', question))[-1]
        self.assertEqual(client.responses.create.call_count, 7 if parent_annotations else 6)
        self.assertTrue(result['veredito']['scoped_metrics'])
        self.assertEqual(len(result['veredito']['claim_details']), 2)
        for detail in result['veredito']['claim_details']:
            self.assertTrue(all(m['valid'] for m in detail['metrics']))
            self.assertNotIn('CONTEXT_INCOMPLETE', detail['reasons'])
        self.assertNotIn('**Sustenta:**', result['text'])
        self.assertNotIn('Pesquisa realizada', result['text'])
        self.assertEqual(len(result['veredito']['source_details']), 2)

    def test_enem_short_question_still_searches_when_extractor_asks_for_context(self):
        question = 'a redação do enem foi sobre cinema brasileiro?'
        passage = 'Em 2019, o tema da redação do Enem foi Democratização do acesso ao cinema no Brasil.'
        client = self.setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            stage = kwargs.get('text', {}).get('format', {}).get('name')
            if stage == 'extraction':
                return response(json.dumps({'kind': 'NEEDS_CONTEXT', 'claims': [],
                    'omitted_material': False, 'decomposition_complete': False}))
            if stage == 'qualification':
                data = qualification()
                data['evidence'][0].update(claim_id='research1', quote=passage, origin_quote=passage)
                data['reviews'][0].update(claim_id='research1', resolved_claim=passage,
                    resolution_source_ids=['s1'],
                    assessment='Em 2019, o tema foi o acesso ao cinema no Brasil. A pergunta não informa a edição do exame.')
                return response(json.dumps(data))
            return original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', return_value={**document(), 'text': passage}):
            result = list(analyze(client, 'gpt-5-mini', question))[-1]
        self.assertEqual(client.responses.create.call_count, 6)
        self.assertEqual(result['veredito']['retrieval']['queries_executed'], 4)
        self.assertTrue(result['audit']['research_recovery'])
        self.assertIn('Em 2019', result['text'])
        self.assertIn('A pergunta não informa a edição', result['text'])
        self.assertNotIn('Envie a afirmação completa', result['text'])

    def setup_provider(self):
        client = MagicMock()
        extraction = {'kind': 'FACTUAL', 'claims': [claim().model_dump()],
                      'omitted_material': False, 'decomposition_complete': True}
        def create(**kwargs):
            if kwargs.get('tools'):
                self.assertEqual(kwargs['max_tool_calls'], 1)
                self.assertEqual(kwargs['tool_choice'], 'required')
                self.assertFalse(kwargs['store'])
                return response(output=[{'type': 'web_search_call', 'status': 'completed',
                    'action': {'type': 'search', 'query': 'indicador 2025', 'sources': [{'url': URL}]}}])
            stage = kwargs['text']['format']['name']
            return response(json.dumps(extraction if stage == 'extraction' else qualification()))
        client.responses.create.side_effect = create
        return client

    def run_pipeline(self, client, ledger=None):
        with patch('src.services.analysis_service.fetch_document', return_value=document()):
            return list(analyze(client, 'gpt-5-mini', claim().text, ledger=ledger))

    def test_complete_flow_with_observed_searches_snapshots_and_metrics(self):
        client = self.setup_provider()
        usage = []
        events = self.run_pipeline(client, UsageLedger(usage.append))
        result = events[-1]
        self.assertEqual(result['type'], 'result')
        self.assertEqual(client.responses.create.call_count, 6)  # extract + 4 searches + qualify; no writer
        self.assertEqual(result['tokens'], sum(usage))
        self.assertEqual(result['veredito']['version'], 2)
        self.assertFalse(result['veredito']['calibrated'])
        self.assertEqual(result['veredito']['code'], 'STRONGLY_SUPPORTED')
        self.assertGreaterEqual(result['veredito']['metrics'][1]['value'], 65)
        self.assertIn('O relatório indica o valor 20', result['text'])
        self.assertTrue(all(m['valid'] for m in result['veredito']['metrics']))
        self.assertEqual(len(result['audit']['searches']), 4)
        self.assertEqual(result['audit']['documents'][0]['text'], TEXT)
        self.assertEqual(result['audit']['evidence'][0]['offset'], 0)
        self.assertIn(f']({URL})', result['text'])
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta'), result['text'])

    def test_noise_uses_no_provider_and_short_reply(self):
        client = MagicMock()
        events = list(analyze(client, 'gpt-5-mini', 'asdfghjkl'))
        client.responses.create.assert_not_called()
        self.assertEqual(events[-1]['tokens'], 0)
        self.assertLess(len(events[-1]['text']), 100)
        self.assertTrue(all(m['value'] is None for m in events[-1]['veredito']['metrics']))

    def test_fabricated_quote_cannot_unlock_scores(self):
        data = qualification()
        data['evidence'][0]['quote'] = 'Este trecho foi completamente inventado pelo modelo.'
        evidence, rejected = validate_annotations(Qualification(**data), [claim()], [document()])
        self.assertFalse(evidence)
        self.assertEqual(rejected[0]['reason'], 'INVALID_ANCHOR')

    def test_derivation_requires_both_origin_span_and_real_link(self):
        data = qualification()
        data['evidence'][0].update(primary=False, origin_source_id='s2')
        origin = {**document(), 'id': 's2', 'url': 'https://primary.example/report',
                  'final_url': 'https://primary.example/report'}
        result, _ = validate_annotations(Qualification(**data), [claim()], [document(), origin])
        self.assertFalse(result[0]['origin_verified'])
        linked = {**document(), 'links': [origin['url']]}
        result, _ = validate_annotations(Qualification(**data), [claim()], [linked, origin])
        self.assertTrue(result[0]['origin_verified'])

    def test_unknown_source_or_out_of_range_elements_are_rejected(self):
        for changes in [{'source_id': 'invented'}, {'covered_elements': [99]}, {'claim_id': 'invented'}]:
            data = qualification()
            data['evidence'][0].update(changes)
            result, rejected = validate_annotations(Qualification(**data), [claim()], [document()])
            self.assertFalse(result)
            self.assertTrue(rejected)

    def test_refutation_must_reference_an_element_examined_by_the_exact_quote(self):
        data = qualification()
        data['evidence'][0].update(stance=-1.0, covered_elements=[0], refutes_elements=[1],
                                    refutation_kind='explicit_contradiction')
        result, rejected = validate_annotations(Qualification(**data), [claim()], [document()])
        self.assertFalse(result)
        self.assertEqual(rejected[0]['reason'], 'INVALID_REFUTATION')

    def test_no_snapshots_means_no_qualification_and_no_score(self):
        client = self.setup_provider()
        with patch('src.services.analysis_service.fetch_document', side_effect=ValueError('blocked')):
            result = list(analyze(client, 'gpt-5-mini', claim().text))[-1]
        self.assertEqual(client.responses.create.call_count, 5)
        self.assertEqual(result['veredito']['code'], 'INCONCLUSIVE')
        self.assertTrue(all(m['value'] is None for m in result['veredito']['metrics']))

    def test_provider_link_text_is_not_source_authority(self):
        client = MagicMock()
        client.responses.create.return_value = response('[Fonte](https://invented.example)')
        record = _search(client, 'gpt-5-mini', UsageLedger(), monotonic()+10, claim(), 'neutral', 'consulta')
        self.assertFalse(record['executed'])
        self.assertFalse(record['sources'])

    def test_sdk_citation_is_preserved_when_complete_source_list_is_absent(self):
        client = MagicMock()
        client.responses.create.return_value = cited_search_response()
        record = _search(client, 'gpt-5-mini', UsageLedger(), monotonic()+10, claim(), 'neutral', 'consulta')
        self.assertTrue(record['executed'])
        self.assertEqual(record['sources'], [URL])
        self.assertEqual(record['excerpts'][0]['text'], TEXT)

    def test_completed_search_survives_incomplete_final_provider_message(self):
        client = MagicMock()
        result = cited_search_response()
        result.status = 'incomplete'
        client.responses.create.return_value = result
        record = _search(client, 'gpt-5-mini', UsageLedger(), monotonic()+10, claim(), 'neutral', 'consulta')
        self.assertTrue(record['executed'])
        self.assertEqual(record['sources'], [URL])

    def test_blocked_pages_use_cited_summary_with_low_acs_and_no_fabricated_ess(self):
        client = self.setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            return cited_search_response() if kwargs.get('tools') else original(**kwargs)
        client.responses.create.side_effect = create
        with patch('src.services.analysis_service.fetch_document', side_effect=ValueError('blocked')):
            result = list(analyze(client, 'gpt-5-mini', claim().text))[-1]
        self.assertEqual(result['veredito']['assessment_level'], 'preliminary')
        self.assertIsNone(result['veredito']['metrics'][0]['value'])
        self.assertIsNotNone(result['veredito']['metrics'][1]['value'])
        self.assertLessEqual(result['veredito']['metrics'][1]['value'], 25)
        self.assertIn('O relatório indica o valor 20', result['text'])
        self.assertEqual(result['veredito']['source_details'][0]['retrieval_kind'], 'provider_excerpt')
        self.assertNotIn('Síntese citada da busca — página não inspecionada', result['text'])
        e = result['audit']['evidence'][0]
        self.assertFalse(e['origin_verified'])
        self.assertFalse(e['primary'])
        self.assertEqual(result['veredito']['retrieval']['provider_excerpts'], 1)

    def test_expired_budget_never_starts_provider(self):
        client = MagicMock()
        record = _search(client, 'gpt-5-mini', UsageLedger(), monotonic()-1, claim(), 'neutral', 'consulta')
        self.assertEqual(record['status'], 'failed')
        client.responses.create.assert_not_called()

    def test_usage_is_recorded_before_invalid_model_output_fails(self):
        client = MagicMock()
        client.responses.create.return_value = response('not json')
        ledger = UsageLedger()
        with self.assertRaises(Exception):
            list(analyze(client, 'gpt-5-mini', claim().text, ledger=ledger))
        self.assertEqual(ledger.total, 10)
        self.assertTrue(ledger.attempted)

    def test_usage_failure_stops_more_paid_calls(self):
        ledger = UsageLedger(MagicMock(side_effect=RuntimeError('database unavailable')))
        client = self.setup_provider()
        with self.assertRaises(RuntimeError):
            list(analyze(client, 'gpt-5-mini', claim().text, ledger=ledger))
        self.assertTrue(ledger.failed_accounting)
        self.assertEqual(client.responses.create.call_count, 1)
        self.assertEqual(ledger.total, 10)

    def test_qualification_failure_abstains_without_fabricating_metrics(self):
        client = self.setup_provider()
        original = client.responses.create.side_effect
        def create(**kwargs):
            if kwargs.get('text', {}).get('format', {}).get('name') == 'qualification':
                return response('{"evidence": "invalid"}')
            return original(**kwargs)
        client.responses.create.side_effect = create
        result = self.run_pipeline(client)[-1]
        self.assertEqual(result['veredito']['code'], 'INCONCLUSIVE')
        self.assertTrue(result['audit']['qualification_failed'])
        self.assertTrue(all(m['value'] is None for m in result['veredito']['metrics']))

    def test_version_two_with_empty_metrics_is_not_reparsed_from_text(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        controller.chat_model.get_mensagens_por_conversa.return_value = [
            {'prompt': 'p', 'resposta': '**Veredicto:** FALSO',
             'veredito': {'version': 2, 'code': 'NOT_VERIFIABLE', 'metrics': []}}]
        client.application.add_url_rule('/historico/<conversa_id>', view_func=controller.get_mensagens_por_conversa)
        result = client.get('/historico/c').json
        self.assertEqual(result['mensagens'][0]['veredito']['code'], 'NOT_VERIFIABLE')

    def test_audit_is_stored_but_never_returned_in_chat_payload(self):
        from src.models.chatModel import ChatModel
        model = ChatModel(MagicMock())
        model.collection, model.db_available = MagicMock(), True
        model.collection.insert_one.return_value.inserted_id = 'id'
        result = model.save_mensagem('u', 'c', 'p', 'r', {'version': 2}, audit={'snapshot': 'private'})
        self.assertNotIn('analysis_audit', result)
        self.assertNotIn('audit_expires_at', result)
        stored = model.collection.insert_one.call_args.args[0]
        self.assertEqual(stored['analysis_audit']['snapshot'], 'private')
        self.assertIn('audit_expires_at', stored)

    def test_crossing_midnight_records_tokens_against_reserved_day(self):
        from src.models.userModel import UserModel
        model = UserModel(MagicMock())
        model.collection, model.db_available = MagicMock(), True
        model.registrar_tokens_usados('u', 10, dia='2026-11-11')
        self.assertEqual(model.collection.update_one.call_args.args[0],
                         {'firebase_uid': 'u', 'uso_diario.data': '2026-11-11'})

    def test_disconnect_after_provider_use_keeps_quota_and_records_spent_tokens(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        def events(*args, ledger=None):
            ledger.start()
            ledger.record(response(), 'extraction')
            yield {'type': 'delta', 'text': 'Parcial'}
        with patch('src.controller.chatController.transmitir_resposta', side_effect=events):
            stream = client.post('/mensagem', json={'prompt': claim().text, 'conversa_id': 'c'},
                                 headers={'Accept': 'text/event-stream'}, buffered=False)
            next(iter(stream.response))
            stream.close()
        self.assertTrue(controller.user_model.finalizar_reserva.call_args.args[-1])
        controller.user_model.registrar_tokens_usados.assert_called_once_with('uid', 10, dia=None)

    def test_local_noise_refunds_analysis_quota_without_model_usage(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        with patch('src.services.openai_services.client') as provider:
            response_data = client.post('/mensagem', json={'prompt': 'asdfghjkl', 'conversa_id': 'c'})
        self.assertEqual(response_data.status_code, 200)
        provider.responses.create.assert_not_called()
        self.assertFalse(controller.user_model.finalizar_reserva.call_args.args[-1])
        controller.user_model.registrar_tokens_usados.assert_not_called()

    def test_json_and_sse_persist_identical_structured_analysis(self):
        result = self.run_pipeline(self.setup_provider())[-1]
        client, controller = test_streaming.StreamingTests().criar_cliente()
        with patch('src.controller.chatController.obter_resposta', return_value=CompleteAnswer(result)):
            json_result = client.post('/mensagem', json={'prompt': claim().text, 'conversa_id': 'c'}).json
        json_save = controller.chat_model.save_mensagem.call_args
        with patch('src.controller.chatController.transmitir_resposta',
                   return_value=(e for e in [result])):
            response_data = client.post('/mensagem', json={'prompt': claim().text, 'conversa_id': 'c'},
                headers={'Accept': 'text/event-stream'}).text
        frames = [json.loads(f.removeprefix('data: ')) for f in response_data.strip().split('\n\n')]
        self.assertEqual(frames[-1]['type'], 'done')
        self.assertEqual(json_result['veredito'], frames[-1]['veredito'])
        self.assertEqual(json_save, controller.chat_model.save_mensagem.call_args)


class FetchSecurityTests(unittest.TestCase):
    def setUp(self):
        from src.services.evidence_fetch import _CACHE, _CACHE_LOCK
        with _CACHE_LOCK:
            _CACHE.clear()

    def test_dangerous_urls_rejected_without_network(self):
        for url in ['file:///etc/passwd', 'http://127.0.0.1', 'http://169.254.169.254/latest',
                    'http://[::1]', 'https://user:pass@example.org/', 'https://example.org:8080',
                    'https://localhost', 'https://something.local/', 'https://example.org/\r\nX:x',
                    'https://example.org\\@127.0.0.1/', 'http://[::ffff:127.0.0.1]',
                    'http://[64:ff9b::7f00:1]', 'http://[2002:7f00:1::]']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)

    def test_dns_mixed_public_private_is_blocked(self):
        with patch('src.services.evidence_fetch.socket.getaddrinfo', return_value=[
                (2, 1, 6, '', ('93.184.216.34', 443)), (2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                resolve_public('example.org', 443, 2)

    def test_script_content_removed_from_snapshot(self):
        parser = TextHTML()
        parser.feed('<p>Fato</p><script>malicious()</script><style>hidden</style><p>Dados</p>')
        self.assertNotIn('malicious', ''.join(parser.parts))
        self.assertNotIn('hidden', ''.join(parser.parts))

    @patch('src.services.evidence_fetch.resolve_public', return_value='93.184.216.34')
    @patch('src.services.evidence_fetch.PinnedHTTP')
    def test_redirect_to_private_host_is_blocked_before_connection(self, connection, resolver):
        connection.return_value.getresponse.return_value.status = 302
        connection.return_value.getresponse.return_value.getheader.return_value = 'http://127.0.0.1/admin'
        with self.assertRaises(ValueError):
            fetch_document(URL, monotonic()+10)
        self.assertEqual(connection.call_count, 1)
        self.assertEqual(resolver.call_count, 1)

    @patch('src.services.evidence_fetch.resolve_public', return_value='93.184.216.34')
    @patch('src.services.evidence_fetch.PinnedHTTP')
    def test_compression_and_nontext_documents_are_rejected(self, connection, resolver):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        for headers in [{'Content-Type': 'text/html', 'Content-Encoding': 'gzip'},
                        {'Content-Type': 'application/pdf'}]:
            response.getheader.side_effect = lambda k, default=None: headers.get(k, default)
            with self.assertRaises(ValueError):
                fetch_document(URL, monotonic()+10)
            response.read1.assert_not_called()

    @patch('src.services.evidence_fetch.resolve_public', return_value='93.184.216.34')
    @patch('src.services.evidence_fetch.PinnedHTTP')
    def test_large_page_keeps_a_bounded_partial_snapshot(self, connection, resolver):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        headers = {'Content-Type': 'text/html', 'Content-Length': '999999999'}
        response.getheader.side_effect = lambda k, default=None: headers.get(k, default)
        stream = io.BytesIO((f'<p>{TEXT}</p>'+' '*500).encode())
        response.read1.side_effect = stream.read
        with patch('src.services.evidence_fetch.MAX_BYTES', 128):
            doc = fetch_document(URL, monotonic()+10)
        self.assertTrue(doc['truncated'])
        self.assertLessEqual(stream.tell(), 128)
        self.assertIn('indicador foi 20', doc['text'])

    @patch('src.services.evidence_fetch.socket.create_connection')
    @patch('src.services.evidence_fetch.ssl.create_default_context')
    def test_dns_address_is_pinned_and_tls_uses_original_hostname(self, context, create_socket):
        connection = PinnedHTTP('example.org', '93.184.216.34', 3, True)
        connection.connect()
        create_socket.assert_called_once_with(('93.184.216.34', 443), 3)
        context.return_value.wrap_socket.assert_called_once_with(create_socket.return_value, server_hostname='example.org')

    @patch('src.services.evidence_fetch.resolve_public', return_value='93.184.216.34')
    @patch('src.services.evidence_fetch.PinnedHTTP')
    def test_snapshot_and_bounded_cache_avoid_repeated_download(self, connection, resolver):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda k, default=None: {'Content-Type': 'text/html'}.get(k, default)
        response.read1.side_effect = [f'<html><p>{TEXT}</p></html>'.encode(), b'']
        first = fetch_document(URL, monotonic()+10)
        second = fetch_document(URL, monotonic()+10)
        self.assertEqual(first['text'], TEXT)
        self.assertEqual(first['hash'], sha256(TEXT.encode()).hexdigest())
        self.assertTrue(second['cache_hit'])
        self.assertEqual(connection.call_count, 1)


if __name__ == '__main__':
    unittest.main()
