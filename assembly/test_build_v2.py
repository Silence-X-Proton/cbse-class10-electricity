import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pymupdf
import build
import build_v2 as v2


class PassthroughAssets:
    def copy(self, value):
        return value


class V2Tests(unittest.TestCase):
    def q(self, number=1, **extra):
        q = {'id': f'v2-{number}', 'origin': 'official', 'exam_type': 'PYQ',
             'year': 2025, 'session': '2025', 'source_id': 'exact-source-31-2-1',
             'source_title': 'Official Science 31/2/1', 'paper_code': '31/2/1',
             'source_url': 'https://www.cbse.gov.in/paper.pdf', 'question_number': str(number),
             'original_section': 'B', 'pages': [3], 'marks': 2, 'type': 'short2',
             'verified': True, 'answer_verified': False, 'text': 'Identical wording in independent source occurrences.',
             'evidence_images': ['assets/research/crop.png']}
        q.update(extra)
        return q

    def base(self):
        return {'questions': [], 'sources': [], 'documents': []}

    def test_missing_gate_never_calls_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(v2, 'ROOT', Path(tmp)), patch.object(v2, 'snapshot_public') as snapshot:
            with self.assertRaises(build.Blocked):
                v2.run(argparse.Namespace(max_pages=750))
            snapshot.assert_not_called()

    def test_gate_requires_ready_validation_and_complete_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'research/pyq_v2'
            folder.mkdir(parents=True)
            payloads = {'question_bank.json': {'status': 'ready', 'questions': []},
                        'publication_metadata.json': {}, 'ledger.json': [], 'quarantine.json': [],
                        'coverage.json': {}, 'validation.json': {'status': 'ready', 'errors': []}}
            for name, value in payloads.items():
                (folder / name).write_text(json.dumps(value))
            self.assertTrue(v2.load_handoff(root)[1])
            (folder / 'READY.md').write_text('# READY\n')
            self.assertEqual(v2.load_handoff(root)[1], [])
            (folder / 'validation.json').write_text('{"status":"ready","errors":["crop uncertain"]}')
            self.assertIn('Research validation has not passed', v2.load_handoff(root)[1])

    def test_all_occurrences_short1_and_alternatives_uncapped(self):
        qs = [self.q(n, question_number=str(n)) for n in range(1, 101)]
        qs += [self.q(101, question_number='10 OR', choice_group='choice-10', marks=1, type='short1'),
               self.q(102, question_number='10', choice_group='choice-10')]
        qs += [self.q(103, exam_type='SQP', session='2025-26')]
        docs = v2.collections(list(reversed(qs)))
        master = next(d for d in docs if d['id'] == 'pyq-master')
        self.assertEqual(len(master['question_ids']), 102)
        self.assertLess(master['question_ids'].index('v2-2'), master['question_ids'].index('v2-10'))
        for doc in docs:
            self.assertNotIn('marks', doc)
            self.assertNotIn('duration_minutes', doc)
        for exam in ('PYQ', 'SQP'):
            expected = Counter(q['id'] for q in qs if q['exam_type'] == exam)
            for scope in ('master', 'year'):
                self.assertEqual(Counter(qid for d in docs if d['collection_type'] == exam.lower() and d['collection_scope'] == scope for qid in d['question_ids']), expected)

    def test_merge_preserves_identity_wording_marks_and_holds(self):
        raw = self.q(1, answer='Unverified answer never publish', answer_evidence_images=['bad.png'])
        unverified = self.q(2, verified=False)
        data, held = v2.merge_records(self.base(), [raw, unverified], {}, [], PassthroughAssets())
        self.assertEqual(len(data['questions']), 1)
        q = data['questions'][0]
        for key in ('source_id', 'question_number', 'marks', 'text', 'verified'):
            self.assertEqual(q[key], raw[key])
        self.assertNotIn('answer', q)
        self.assertNotIn('answer_evidence_images', q)
        self.assertEqual(held[0]['id'], 'v2-2')
        self.assertEqual(raw['answer'], 'Unverified answer never publish')
        self.assertEqual(data['sources'][0]['id'], raw['source_id'])

    def test_v1_conflict_and_quarantine_block_not_overwrite(self):
        raw = self.q()
        base, _ = v2.merge_records(self.base(), [raw], {}, [], PassthroughAssets())
        before = deepcopy(base)
        with self.assertRaisesRegex(build.Blocked, 'differs'):
            v2.merge_records(base, [self.q(marks=3)], {}, [], PassthroughAssets())
        with self.assertRaisesRegex(build.Blocked, 'quarantine conflicts'):
            v2.merge_records(base, [], {}, [{'id': raw['id']}], PassthroughAssets())
        self.assertEqual(base, before)

    def test_source_id_conflict_and_duplicate_question_id_block(self):
        with self.assertRaisesRegex(build.Blocked, 'Conflicting source_id'):
            v2.merge_records(self.base(), [self.q(1), self.q(2, source_title='Other paper')], {}, [], PassthroughAssets())
        with self.assertRaisesRegex(build.Blocked, 'duplicate'):
            v2.merge_records(self.base(), [self.q(1), self.q(1)], {}, [], PassthroughAssets())

    def test_overlay_cannot_upgrade_verification(self):
        metadata = {'v2-1': {'verified': True, 'metadata_review': {'page': 1}}}
        with self.assertRaises(build.Blocked):
            v2.merge_records(self.base(), [self.q(verified=False)], metadata, [], PassthroughAssets())

    def test_ledger_preserves_false_zero_and_does_not_infer_review(self):
        ledger = [{'id': 'pdf-1', 'year': 2025, 'status': 'partial_review', 'reviewed': False,
                   'published_questions': 0, 'reviewed_pages': [1], 'exhaustive': False}]
        result = v2.compact_ledger(ledger)[0]
        self.assertIs(result['reviewed'], False)
        self.assertIs(result['exhaustive'], False)
        self.assertEqual(result['published_questions'], 0)
        with self.assertRaises(build.Blocked):
            v2.compact_ledger(ledger + ledger)

    def fake_renderer(self, doc, lookup, stage):
        output = stage / 'downloads' / (doc['id'] + '.pdf')
        output.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open() as pdf:
            for qid in doc['question_ids']:
                page = pdf.new_page()
                page.insert_text((50, 50), qid)
            pdf.save(output)
        doc['pdf'] = output.relative_to(stage).as_posix()
        return {'id': doc['id']}

    def test_measured_volume_split_membership_and_no_stale_files(self):
        doc = {'id': 'pyq-master', 'title': 'Master', 'question_ids': [f'q{n}' for n in range(17)]}
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            volumes, stats = v2.render_volumes(doc, {}, stage, max_pages=5, renderer=self.fake_renderer)
            self.assertEqual([q for d in volumes for q in d['question_ids']], doc['question_ids'])
            self.assertEqual(len(volumes), 4)
            self.assertEqual(len(list((stage / 'downloads').glob('*.pdf'))), 4)
            for i, volume in enumerate(volumes, 1):
                self.assertEqual(volume['volume_number'], i)
                self.assertEqual(volume['volume_count'], 4)
                self.assertLess(volume['pdf_bytes'], v2.MAX_BYTES)
                self.assertLessEqual(volume['pdf_pages'], 5)
            self.assertNotIn('pdf', doc)

    def test_exact_byte_ceiling_is_rejected(self):
        doc = {'id': 'pyq-master', 'title': 'Master', 'question_ids': ['q1']}
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            self.fake_renderer(doc, {}, stage)
            size = (stage / doc['pdf']).stat().st_size
            with self.assertRaisesRegex(build.Blocked, 'single record'):
                v2.render_volumes(doc, {}, stage, max_bytes=size, renderer=self.fake_renderer)


if __name__ == '__main__':
    unittest.main()
