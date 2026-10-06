import argparse
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build
import build_special39 as special


class Assets:
    def copy(self, value): return value


class Special39AssemblyTests(unittest.TestCase):
    def bundle(self):
        bundle = {'documents': [], 'questions': [], 'sources': []}
        for identity in special.DOC_IDS:
            ids = []
            for n in range(1, 40):
                section, marks, kind = special.blueprint(n)
                qid = f'{identity}-q{n:02}'
                q = {'id': qid, 'number': n, 'origin': 'original', 'section': section,
                     'marks': marks, 'type': kind, 'text': 'Test question', 'answer': 'Test solution',
                     'verified': True, 'answer_verified': True, 'competency': True,
                     'competency_marks': marks, 'competency_rationale': 'Evidence reasoning',
                     'source_pattern_ids': ['ncert-11'], 'marking_scheme': [{'step': 'Reason', 'marks': marks}]}
                if n <= 20: q.update(options=['one', 'two', 'three', 'four'], correct_option='A')
                if n <= 7: q['diagram_image'] = f'{special.PREFIX}{identity}-{n}.svg'
                bundle['questions'].append(q)
                ids.append(qid)
            bundle['documents'].append({'id': identity, 'title': identity, 'kind': 'practice',
                                        'status': 'ready', 'marks': 80, 'question_ids': ids})
        return bundle

    def test_exact_blueprint_and_independent_solution_marks(self):
        report = special.validate_blueprint(self.bundle())
        self.assertEqual(len(report), 4)
        for paper in report:
            self.assertEqual(paper['questions'], 39)
            self.assertEqual(paper['marks'], 80)
            self.assertEqual(paper['sections'], {'A': 20, 'B': 6, 'C': 7, 'D': 3, 'E': 3})
            self.assertEqual(paper['section_marks'], {'A': 20, 'B': 12, 'C': 21, 'D': 15, 'E': 12})
        bad = self.bundle()
        bad['questions'][33]['marking_scheme'][0]['marks'] = 4
        with self.assertRaisesRegex(build.Blocked, 'step marks'):
            special.validate_blueprint(bad)

    def test_seven_or_five_diagrams_per_paper_pass_four_fail(self):
        bundle = self.bundle()
        report = special.validate_blueprint(bundle)
        self.assertEqual(sum(p['distinct_svg_assets'] for p in report), 28)
        self.assertTrue(all(p['diagram_questions'] == 7 for p in report))
        for start in range(0, 156, 39):
            for q in bundle['questions'][start+5:start+7]:
                q.pop('diagram_image')
        self.assertTrue(all(p['diagram_questions'] == 5 for p in special.validate_blueprint(bundle)))
        bundle['questions'][0].pop('diagram_image')
        with self.assertRaisesRegex(build.Blocked, '>=5 diagram-linked'):
            special.validate_blueprint(bundle)

    def test_competency_boundary_48_pass_47_fail(self):
        bundle = self.bundle()
        for start in range(0, 156, 39):
            left = 48
            for q in bundle['questions'][start:start+39]:
                q['competency_marks'] = min(left, q['marks'])
                left -= q['competency_marks']
                q['competency'] = q['competency_marks'] > 0
        self.assertEqual(special.validate_blueprint(bundle)[0]['competency_marks'], 48)
        bundle['questions'][0].update(competency=False, competency_marks=0)
        with self.assertRaisesRegex(build.Blocked, '>=48'):
            special.validate_blueprint(bundle)

    def test_ids_order_verification_and_diagram_floor_fail_closed(self):
        for edit, expected in [
            (lambda b: b['documents'][0]['question_ids'].reverse(), 'ordered'),
            (lambda b: b['questions'][0].update(answer_verified=False), 'reviewed'),
            (lambda b: b['questions'][0].update(text='Question\nOR\nOther'), 'OR')]:
            with self.subTest(expected=expected):
                bundle = self.bundle(); edit(bundle)
                with self.assertRaisesRegex(build.Blocked, expected): special.validate_blueprint(bundle)

    def test_additive_merge_preserves_baseline_and_authored_answers(self):
        base = {'documents': [{'id': 'old'}], 'questions': [{'id': 'old-q'}], 'sources': []}
        before = deepcopy(base)
        bundle = self.bundle()
        data, docs = special.merge_special(base, bundle, Assets())
        self.assertEqual(base, before)
        self.assertEqual(data['documents'][0], base['documents'][0])
        self.assertEqual(len(data['questions']), 157)
        self.assertEqual(len(docs), 4)
        self.assertTrue(all(d['title'].startswith('Special39 / competency practice') for d in docs))
        self.assertEqual(data['questions'][1]['answer'], bundle['questions'][0]['answer'])
        with self.assertRaisesRegex(build.Blocked, 'already exist'):
            special.merge_special(data, bundle, Assets())

    def test_missing_handoff_blocks_before_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(special, 'AUTHOR', Path(tmp)), patch.object(special.archives, 'snapshot_public') as snapshot:
            with self.assertRaisesRegex(build.Blocked, 'handoff missing'):
                special.run(argparse.Namespace(masters_only=False))
            snapshot.assert_not_called()

    def test_alias_rejects_traversal_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory(dir=build.ASSEMBLY) as tmp:
            root = Path(tmp); author = root / 'author'; (author / 'assets').mkdir(parents=True)
            source = author / 'assets' / 'test.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
            stage = root / 'site'
            with patch.object(special, 'AUTHOR', author):
                assets = special.SpecialAssets(stage)
                value = assets.copy({'src': special.PREFIX + 'test.svg', 'alt': 'Original circuit'})
                self.assertEqual((stage / value['src']).read_bytes(), source.read_bytes())
                self.assertEqual(value['alt'], 'Original circuit')
                with self.assertRaisesRegex(build.Blocked, 'Unsafe'):
                    assets.copy(special.PREFIX + '../test.svg')

    def test_accept_stage_failure_restores_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); target = root / 'stage'; target.mkdir(); (target / 'old').write_text('preserved')
            with patch.object(special.shutil, 'copytree', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): special.accept_stage(root / 'new', target)
            self.assertEqual((target / 'old').read_text(), 'preserved')
            self.assertFalse((root / 'stage-previous').exists())


if __name__ == '__main__': unittest.main()
