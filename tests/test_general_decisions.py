"""General context/inference rules, independent of particular people or topics."""
import unittest
from src.core.semantic_alignment import SemanticAlignment, alignment_input, apply_alignment, retain_context_candidates
from src.core.contracts import Qualification
from src.core.answer_policy import score_answer
from src.core.scoring import verdict
from src.services.source_presentation import source_key, select_sources
from src.services.markdown_service import renderizar_markdown
from test_core import claim, evidence
from test_search_support import review, target, SEARCHES
from test_analysis_pipeline import qualification, document
from src.services.analysis_service import validate_annotations


class GeneralDecisionTests(unittest.TestCase):
    def test_missing_source_grade_does_not_discard_a_valid_audited_direction(self):
        c = claim()
        data = qualification()
        data['evidence'][0].update(stance=-.5, source_quality=None)
        data['reviews'][0].update(conclusion='refutes')
        accepted, rejected = validate_annotations(Qualification.model_validate(data), [c], [document()])
        self.assertEqual(len(accepted), 1)
        self.assertFalse(rejected)
        result = score_answer(c, accepted, SEARCHES,
                              Qualification.model_validate(data).reviews[0], True)
        self.assertEqual(result['state'], 'PREDOMINANTLY_CONTRADICTED')
        self.assertLess(result['ess'], 50)
        self.assertLessEqual(result['acs'], 35)

    def test_second_reader_can_inspect_a_document_omitted_by_first_reader(self):
        q = Qualification.model_validate(qualification()).model_copy(update={'evidence': []})
        doc = {**document(), 'retrieval_kind': 'direct_document'}
        q = retain_context_candidates(q, [claim()], [doc])
        self.assertEqual(len(q.evidence), 1)
        self.assertIn(q.evidence[0].quote, doc['text'])
        self.assertIsNone(q.evidence[0].source_quality)
        self.assertEqual(q.evidence[0].stance, 0)
        payload = alignment_input(q, [claim()], [doc])
        self.assertEqual(len(payload['targets'][0]['evidence']), 1)

    def test_context_mismatch_is_not_proof_across_domains(self):
        examples = ['prisão em jogo versus pessoa real', 'proposta de lei versus lei vigente',
                    'resultado em animais versus eficácia humana', 'renda nominal versus renda real',
                    'edição histórica versus edição atual', 'homônimo versus pessoa pesquisada',
                    'citação de boato versus afirmação documental', 'sátira versus evento real']
        for description in examples:
            with self.subTest(description=description):
                c = claim(verification_target=True)
                q = Qualification.model_validate(qualification())
                payload = alignment_input(q, [c], [{**document(), 'retrieval_kind': 'direct_document'}])
                audit = SemanticAlignment.model_validate({'targets': [dict(claim_id=c.id,
                    evaluated_target=c.text, conclusion='supports', assessment=description,
                    evidence=[dict(source_id='s1', relation='supports_direct',
                        decision_scope='different_context', reason=description)])]})
                checked = apply_alignment(q, [c], payload, audit)
                self.assertEqual(checked.evidence[0].stance, 0)
                self.assertEqual(checked.reviews[0].conclusion, 'insufficient')

    def test_indirect_reasoning_is_usable_without_becoming_direct_proof(self):
        c = claim(verification_target=True)
        q = Qualification.model_validate(qualification())
        payload = alignment_input(q, [c], [{**document(), 'retrieval_kind': 'direct_document'}])
        audit = SemanticAlignment.model_validate({'targets': [dict(claim_id=c.id,
            evaluated_target=c.text, conclusion='refutes', assessment='Inferência contextual delimitada.',
            evidence=[dict(source_id='s1', relation='refutes_direct', decision_scope='indirect',
                           reason='Condição incompatível com a hipótese.')])]})
        checked = apply_alignment(q, [c], payload, audit)
        self.assertEqual(checked.evidence[0].stance, -.5)
        self.assertEqual(checked.evidence[0].refutation_kind, 'none')

    def test_reviewed_uncertainty_has_explicit_neutral_metrics(self):
        for updates in ({'entity_resolved': False}, {'search_finding': 'unclear_mentions'}):
            result = score_answer(target(), [evidence(stance=0)], SEARCHES, review(**updates), True)
            self.assertEqual(result['state'], 'INCONCLUSIVE')
            self.assertEqual(result['ess'], 50)
            self.assertLessEqual(result['acs'], 35)
            metric = verdict([target()], [result])['metrics'][0]
            self.assertEqual(metric['measurement'], 'undetermined_support')

    def test_canonical_source_identity_preserves_meaningful_query_ids(self):
        self.assertEqual(source_key('https://www.example.org/a/?utm_source=x#p'), source_key('http://example.org/a'))
        self.assertNotEqual(source_key('https://example.org/a?id=1'), source_key('https://example.org/a?id=2'))

    def test_principal_sources_include_both_sides_and_exclude_read_only_pages(self):
        docs = [{**document(), 'id': f's{i}', 'final_url': f'https://example.org/article{i}'} for i in range(1, 5)]
        ev = [evidence('s1', 'g1'), evidence('s2', 'g2', stance=-1)]
        ev.append(evidence('s3', 'g3', contribution='incidental'))
        selected = select_sources([claim()], [{'scoring_source_ids': ['s1', 's2']}], ev, docs)
        self.assertEqual(set(selected), {'s1', 's2'})
        docs[1]['final_url'] = docs[0]['final_url']+'?utm_source=duplicate'
        self.assertEqual(len(select_sources([claim()], [{'scoring_source_ids': ['s1', 's2']}], ev, docs)), 1)

    def test_named_citations_keep_safe_markdown_and_compact_class(self):
        html = renderizar_markdown('**Conclusão**\n\n[CNN Brasil](https://example.org "aleteia-source")')
        self.assertIn('<strong>Conclusão</strong>', html)
        self.assertIn('class="citacao-fonte"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertNotIn('title="aleteia-source"', html)
        self.assertNotIn('<script>', renderizar_markdown('<script>alert(1)</script>'))


if __name__ == '__main__':
    unittest.main()
