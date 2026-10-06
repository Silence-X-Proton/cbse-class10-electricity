"""Run: /opt/venv/bin/python -m unittest discover -s assembly -p test_pdf_special39.py -v"""
from copy import deepcopy
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

try:
    from .pdf_special39 import render_special39, Special39RenderError
except ImportError:
    from pdf_special39 import render_special39, Special39RenderError


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300" viewBox="0 0 800 300">
<title>Original circuit</title><desc>Test vector circuit with readable source labels</desc>
<rect width="800" height="300" fill="white"/>
<g fill="none" stroke="black" stroke-width="3">
<path d="M60 80 H280 M400 80 H740 V240 H60 V80"/>
<rect x="280" y="60" width="120" height="40"/>
<circle cx="560" cy="80" r="25"/>
</g><circle cx="60" cy="80" r="5"/><circle cx="740" cy="80" r="5"/>
<g font-family="sans-serif" font-size="20" fill="black">
<text x="260" y="45">SOURCE_LABEL Ω ρ 10⁻⁶</text>
<text x="552" y="87">A</text><text x="200" y="220">Ideal wires; constant temperature</text>
</g></svg>'''


class Special39PDFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        (self.stage / 'circuit.svg').write_text(SVG)
        (self.stage / 'answer.svg').write_text(SVG.replace('SOURCE_LABEL', 'ANSWER_VECTOR'))
        self.lookup = {}
        # Expected inventory is independently specified, not imported from renderer.
        distribution = [('A', 20, 1), ('B', 6, 2), ('C', 7, 3), ('D', 3, 5), ('E', 3, 4)]
        number = 0
        for section, count, marks in distribution:
            for _ in range(count):
                number += 1
                qid = f'special-39-01-q{number:02}'
                q = {'id': qid, 'origin': 'original', 'section': section, 'number': number,
                     'marks': marks, 'text': f'QUESTION_TEXT_{number:02} Compute V = IR. Ω < & >.',
                     'answer': f'SOLUTION_ONLY_{number:02} Full working: infer the current, apply V = IR, and check units.',
                     'answer_verified': False,
                     'marking_scheme': [{'step': f'MARKING_ONLY_{number:02} Explain inference.', 'marks': marks}],
                     'competency': number % 2 == 0, 'competency_rationale': f'RATIONALE_ONLY_{number:02} Compare measured trends.',
                     'source_pattern_ids': [f'SOURCE_PATTERN_{number:02}', 'ncert-11'],
                     'ncert_refs': ['Section 11.2, Activity 11.1']}
                if number <= 20:
                    q.update(options=['First option Ω', 'Second option', 'Third option', 'Fourth option'], correct_option='B')
                if number in (2, 21, 28, 34, 37):
                    q['diagram_image'] = {'src': 'circuit.svg', 'alt': 'Not a substitute for the vector'}
                self.lookup[qid] = q
        self.doc = {'id': 'special-39-01', 'kind': 'practice', 'status': 'ready',
                    'title': 'Electricity — special 39', 'marks': 80, 'duration_minutes': 180,
                    'question_ids': list(self.lookup), 'sections': [
                        {'heading': 'General instructions', 'bullets': ['Keep exact original units.']},
                        {'heading': 'Source-pattern rationale', 'paragraphs': ['DOCUMENT_RATIONALE_ONLY']},
                        {'heading': 'Solutions supplement', 'paragraphs': ['DOCUMENT_SOLUTION_ONLY']}]}

    def render(self):
        stats = render_special39(self.doc, self.lookup, self.stage)
        pdf = pymupdf.open(self.stage / self.doc['pdf'])
        self.addCleanup(pdf.close)
        return stats, pdf

    def assert_bounds(self, pdf):
        for page in pdf:
            self.assertAlmostEqual(page.rect.width, 595.2756, places=2)
            self.assertAlmostEqual(page.rect.height, 841.8898, places=2)
            self.assertEqual(page.rotation, 0)
            self.assertEqual(page.rect, page.cropbox)
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    rect = pymupdf.Rect(line['bbox'])
                    self.assertGreaterEqual(rect.x0, 44.8)
                    self.assertLessEqual(rect.x1, 550.5)
                    self.assertGreaterEqual(rect.y0, 18)
                    self.assertLessEqual(rect.y1, 821)
                    for span in line['spans']:
                        self.assertGreaterEqual(span['size'], 7.99)
            for drawing in page.get_drawings():
                rect = drawing['rect']
                self.assertGreaterEqual(rect.x0, 44.8)
                self.assertLessEqual(rect.x1, 550.5)
                self.assertGreaterEqual(rect.y0, 37.8)
                self.assertLessEqual(rect.y1, 793)

    def test_all_39_questions_answers_marks_navigation_and_atomic_metadata(self):
        before, questions = deepcopy(self.doc), deepcopy(self.lookup)
        stats, pdf = self.render()
        self.assertEqual(sum(q['marks'] for q in self.lookup.values()), 80)
        self.assertEqual(stats['question_count'], 39)
        self.assertEqual(self.doc['pdf'], 'downloads/special-39-01.pdf')
        self.assertEqual(self.doc['pdf_pages'], len(pdf))
        self.assertEqual(self.doc['pdf_bytes'], (self.stage / self.doc['pdf']).stat().st_size)
        self.assertEqual(self.lookup, questions)
        self.assertEqual({k: v for k, v in self.doc.items() if not k.startswith('pdf')}, before)
        front = '\n'.join(pdf[i].get_text() for i in range(stats['solution_start_page']-1))
        solutions = '\n'.join(pdf[i].get_text() for i in range(stats['solution_start_page']-1, stats['appendix_start_page']-1))
        appendix = '\n'.join(pdf[i].get_text() for i in range(stats['appendix_start_page']-1, len(pdf)))
        self.assertEqual(re.findall(r'^Question (\d+)\s+\|', front, re.M), [str(i) for i in range(1, 40)])
        self.assertEqual(re.findall(r'^Solution (\d+) —', solutions, re.M), [str(i) for i in range(1, 40)])
        for i in range(1, 40):
            self.assertIn(f'special-39-01-q{i:02}', front)
            self.assertIn(f'QUESTION_TEXT_{i:02}', front)
            self.assertIn(f'SOLUTION_ONLY_{i:02}', solutions)
            self.assertIn(f'MARKING_ONLY_{i:02}', solutions)
            self.assertIn(f'RATIONALE_ONLY_{i:02}', appendix)
            self.assertIn(f'SOURCE_PATTERN_{i:02}', appendix)
        for token in ('SOLUTION_ONLY', 'MARKING_ONLY', 'RATIONALE_ONLY', 'SOURCE_PATTERN', 'Correct option:'):
            self.assertNotIn(token, front)
        self.assertNotIn('RATIONALE_ONLY', solutions)
        self.assertIn('DOCUMENT_SOLUTION_ONLY', solutions)
        self.assertIn('DOCUMENT_RATIONALE_ONLY', appendix)
        self.assertIn('Competency classification: No', appendix)
        self.assertIn('not an official examination paper', front)
        self.assertIn('A. First option Ω', front)
        self.assertIn('Ω < & >', front)
        toc = pdf.get_toc()
        self.assertEqual(len([t for level, t, p in toc if level == 1 and re.fullmatch('Section [A-E]', t)]), 5)
        questions_toc = [(t, p) for level, t, p in toc if level == 2 and re.match(r'Question \d+  \|', t)]
        self.assertEqual(len(questions_toc), 39)
        for row, (title, page) in zip(stats['question_pages'], questions_toc):
            self.assertEqual(page, row['page'])
            self.assertIn(row['question_id'], pdf[page-1].get_text())
            self.assertIn(f'Solution {row["number"]} —', pdf[row['solution_page']-1].get_text())
        for i, page in enumerate(pdf, 1):
            self.assertIn(f'Page {i} of {len(pdf)}', page.get_text())
        self.assert_bounds(pdf)

    def test_real_svglib_text_vector_all_aliases_and_rear_answer_diagram(self):
        q = self.lookup['special-39-01-q02']
        q['evidence_images'] = ['circuit.svg', {'src': 'circuit.svg'}]
        q['answer_evidence_images'] = [{'src': 'answer.svg'}]
        stats, pdf = self.render()
        self.assertEqual(stats['svg_count'], 6)
        text = '\n'.join(p.get_text() for p in pdf)
        self.assertEqual(text.count('SOURCE_LABEL Ω ρ 10⁻⁶'), 5)
        self.assertEqual(text.count('ANSWER_VECTOR'), 1)
        self.assertTrue(all(not p.get_images(full=True) for p in pdf), 'No raster PDF XObjects')
        for figure in stats['figures']:
            page = pdf[figure['page']-1]
            self.assertGreaterEqual(len(page.get_drawings()), 7)
            self.assertGreaterEqual(figure['minimum_label_pt'], 8.5)
            labels = [s for b in page.get_text('dict')['blocks'] if b['type'] == 0
                      for line in b['lines'] for s in line['spans']
                      if 'SOURCE_LABEL' in s['text'] or 'ANSWER_VECTOR' in s['text']]
            self.assertTrue(labels)
            self.assertTrue(all(s['size'] >= 8.5 for s in labels))
            if figure['asset'] == 'answer.svg':
                self.assertGreaterEqual(figure['page'], stats['solution_start_page'])
        self.assert_bounds(pdf)

    def test_graph_axes_viewbox_transforms_and_overflow_labels_remain_vector(self):
        graph = '''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="360" viewBox="0 0 400 180">
        <g fill="none" stroke="black" stroke-width="1.5">
        <path d="M45 15 V145 H355 M45 145 L300 30"/>
        <circle cx="130" cy="107" r="3"/><circle cx="215" cy="69" r="3"/>
        </g><g font-family="sans-serif" font-size="10">
        <text x="5" y="12">I / A</text><text x="330" y="165">V / V</text>
        <text x="85" y="25">VECTOR_GRAPH</text>
        <text x="-12" y="175">OVERFLOW_LABEL</text></g></svg>'''
        (self.stage / 'graph.svg').write_text(graph)
        self.lookup['special-39-01-q03']['diagrams'] = ['graph.svg']
        self.doc['sections'][0]['images'] = [{'src': 'graph.svg'}]
        stats, pdf = self.render()
        text = '\n'.join(page.get_text() for page in pdf)
        self.assertEqual(text.count('VECTOR_GRAPH'), 2)
        self.assertEqual(text.count('OVERFLOW_LABEL'), 2)
        self.assertEqual(text.count('I / A'), 2)
        self.assertEqual(text.count('V / V'), 2)
        self.assertEqual(stats['svg_count'], 7)
        self.assertTrue(all(not page.get_images() for page in pdf))
        self.assert_bounds(pdf)

    def test_long_questions_options_solutions_appendix_and_cover_paginate(self):
        q = self.lookup['special-39-01-q01']
        q['text'] = ('LONG_QUESTION Ω < & >. ' * 1600) + ' QUESTION_END'
        q['options'][0] = ('LONG_OPTION ' * 1000) + ' OPTION_END'
        q['answer'] = ('LONG_SOLUTION reasoning and units. ' * 1600) + ' SOLUTION_END'
        q['competency_rationale'] = ('LONG_RATIONALE inference. ' * 1000) + ' RATIONALE_END'
        self.doc['sections'][0]['paragraphs'] = [('COVER_INSTRUCTIONS ' * 900) + ' COVER_END']
        stats, pdf = self.render()
        self.assertGreater(len(pdf), 35)
        front = '\n'.join(pdf[i].get_text() for i in range(stats['solution_start_page']-1))
        rear = '\n'.join(pdf[i].get_text() for i in range(stats['solution_start_page']-1, len(pdf)))
        for token in ('QUESTION_END', 'OPTION_END', 'COVER_END'):
            self.assertIn(token, front)
        for token in ('SOLUTION_END', 'RATIONALE_END'):
            self.assertIn(token, rear)
            self.assertNotIn(token, front)
        self.assert_bounds(pdf)

    def test_optional_aliases_preserve_original_text_without_inventing_data(self):
        q = self.lookup['special-39-01-q01']
        q['question_text'] = q.pop('text')
        q['solution'] = q.pop('answer')
        q['options'] = {'A': 'Exact first', 'B': 'Exact second', 'C': 'Exact third', 'D': 'Exact fourth'}
        q['source_pattern_refs'] = [{'id': 'precise-ref', 'rationale': 'Exact author rationale'}]
        q['marking_scheme'] = [{'criterion': 'CRITERION_WORDING', 'marks': 0.5}, {'text': 'TEXT_WORDING', 'marks': 0.5}]
        absent = self.lookup['special-39-01-q39']
        for key in ('answer', 'marking_scheme', 'competency', 'competency_rationale', 'source_pattern_ids', 'ncert_refs'):
            absent.pop(key)
        _, pdf = self.render()
        text = '\n'.join(page.get_text() for page in pdf)
        for token in ('CRITERION_WORDING', 'TEXT_WORDING', 'Exact author rationale', 'A. Exact first', 'No model answer supplied.', 'No source-pattern or rationale metadata supplied.'):
            self.assertIn(token, text)
        self.assertNotIn('SOLUTION_ONLY_39', text)
        self.assertNotIn('\ufffd', text)

    def test_oversize_small_transformed_labels_rasters_and_external_refs_rejected(self):
        variants = [SVG.replace('width="800" height="300"', 'width="8000" height="3000"').replace('viewBox="0 0 800 300"', 'viewBox="0 0 8000 3000"'),
                    SVG.replace('height="300"', 'height="5000"').replace('0 0 800 300', '0 0 800 5000'),
                    SVG.replace('font-size="20"', 'font-size="4"'),
                    SVG.replace('<g font-family', '<g transform="scale(0.1)" font-family'),
                    SVG.replace('</svg>', '<image href="https://example.invalid/raster.png"/></svg>'),
                    SVG.replace('</svg>', '<use href="https://example.invalid/source.svg#x"/></svg>'),
                    SVG.replace('</svg>', '<clipPath id="x"><rect width="20" height="20"/></clipPath></svg>'),
                    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + SVG,
                    '<svg broken']
        for content in variants:
            with self.subTest(content=content[:80]):
                (self.stage / 'bad.svg').write_text(content)
                self.lookup['special-39-01-q01']['diagram_image'] = 'bad.svg'
                before = deepcopy(self.doc)
                with self.assertRaises(Special39RenderError):
                    render_special39(self.doc, self.lookup, self.stage)
                self.assertEqual(self.doc, before)
                self.assertFalse((self.stage / 'downloads').exists())

    def test_failures_preserve_previous_pdf_and_cleanup_temporary_file(self):
        self.render()
        output = self.stage / self.doc['pdf']
        previous, before = output.read_bytes(), deepcopy(self.doc)
        module = render_special39.__module__
        with patch(module + '.Canvas.save', side_effect=OSError('injected write failure')):
            with self.assertRaisesRegex(OSError, 'injected write failure'):
                render_special39(self.doc, self.lookup, self.stage)
        self.assertEqual(output.read_bytes(), previous)
        self.assertEqual(self.doc, before)
        self.assertEqual(list(output.parent.glob('.special39-*')), [])
        self.lookup['special-39-01-q01']['diagram_image'] = '../outside.svg'
        with self.assertRaises(Special39RenderError):
            render_special39(self.doc, self.lookup, self.stage)
        self.assertEqual(output.read_bytes(), previous)

    def test_repeated_calls_and_unsafe_document_inputs(self):
        stats, _ = self.render()
        self.doc['id'] = 'special-39-02'
        second, pdf = self.render()
        self.assertEqual(second['pdf_pages'], stats['pdf_pages'])
        self.assertTrue((self.stage / stats['pdf']).is_file())
        for change in ({'id': '../outside'}, {'kind': 'official'}, {'question_ids': ['missing']}, {'question_ids': []}):
            with self.subTest(change=change):
                invalid = dict(self.doc, **change)
                before = deepcopy(invalid)
                with self.assertRaises(Special39RenderError):
                    render_special39(invalid, self.lookup, self.stage)
                self.assertEqual(invalid, before)
        self.assert_bounds(pdf)


if __name__ == '__main__':
    unittest.main()
