"""Run: /opt/venv/bin/python -m unittest discover -s assembly -p test_pdf_v2.py -v"""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import pymupdf

try:
    from .pdf_v2 import render_collection, CollectionRenderError
except ImportError:
    from pdf_v2 import render_collection, CollectionRenderError


class CollectionPDFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        # Deterministic high-frequency pattern exposes any resampling or lossy encoding.
        for name, size in [('short.png', (1001, 239)), ('tall.png', (301, 1901)),
                           ('answer.png', (901, 97)), ('source.jpg', (733, 133))]:
            w, h = size
            raw = bytes((x * 37 + y * 73 + c * 89) % 256
                        for y in range(h) for x in range(w) for c in range(3))
            Image.frombytes('RGB', size, raw).save(self.stage / name)
        self.q = {
            'id': 'q-main', 'origin': 'official', 'exam_type': 'PYQ', 'year': 2025,
            'session': '2025 main', 'paper_code': '31/4/2', 'question_number': '33(a)(ii)',
            'source_title': 'Official Science — exact <title> & Ω', 'source_id': 'src-exact-01',
            'source_url': 'https://www.cbse.gov.in/archive/' + 'long-path/' * 12 + 'Science.pdf?a=1&b=2',
            'marking_scheme_url': 'https://cbseacademic.nic.in/2025/Science_MS.pdf',
            'pages': [7, 8], 'original_section': 'SECTION D', 'marks': 3,
            'evidence_images': ['short.png'], 'evidence_image': {'src': 'short.png'},
            'text': 'TRANSCRIPTION_MUST_NOT_REPLACE_THE_SOURCE_RASTER',
            'verified': True, 'answer_verified': True,
            'answer': 'VERIFIED_SOLUTION Ω = 6', 'answer_evidence_images': ['answer.png'],
            'answer_source_pages': [9], 'choice_group': '2025-33', 'selected_alternative': 'A',
            'marks_include_internal_choice': True,
            'question_crop_regions': [{'page': 7, 'bbox': [10, 20, 300, 400]}],
        }
        self.alt = dict(self.q, id='q-or', question_number='33(b) OR',
                        evidence_images=['tall.png', 'source.jpg'], evidence_image='tall.png',
                        selected_alternative='B', verified=False, answer_verified=False,
                        answer='HELD_ANSWER_MUST_NEVER_PRINT',
                        answer_evidence_images=['absent-held-answer.png'],
                        solution_status='Withheld: official answer has an identified error.')
        self.lookup = {q['id']: q for q in (self.q, self.alt)}
        self.doc = {'id': 'pyq-master-v1', 'title': 'Electricity Ω archive',
                    'kind': 'official', 'collection_type': 'pyq', 'status': 'ready',
                    'question_ids': ['q-main', 'q-or'], 'marks': 999, 'duration_minutes': 999}

    def render(self):
        stats = render_collection(self.doc, self.lookup, self.stage)
        pdf = pymupdf.open(self.stage / self.doc['pdf'])
        self.addCleanup(pdf.close)
        return stats, pdf

    def test_png_pixels_jpeg_bytes_and_full_width_tall_page(self):
        originals = {p.name: p.read_bytes() for p in self.stage.iterdir()}
        stats, pdf = self.render()
        self.assertEqual(stats['crop_count'], 4)  # alias duplicates only removed within each question
        self.assertEqual(stats['custom_height_pages'], 1)
        found = {}
        for page in pdf:
            for info in page.get_images(full=True):
                xref, _, width, height = info[:4]
                found[(width, height)] = pdf.extract_image(xref)
                for rect in page.get_image_rects(xref):
                    self.assertAlmostEqual(rect.x0, 45, places=2)
                    self.assertAlmostEqual(rect.x1, 550.28, places=2)
                    self.assertAlmostEqual(rect.height / rect.width, height / width, places=4)
                    self.assertGreaterEqual(rect.y0, 42)
                    self.assertLessEqual(rect.y1, page.rect.height - 48 + 0.01)
                    if height == 1901:
                        self.assertGreater(page.rect.height, 3200)
                        self.assertAlmostEqual(rect.height, 505.28 * 1901 / 301, places=2)
        for filename, raw in originals.items():
            with Image.open(BytesIO(raw)) as source:
                embedded = found[source.size]
                if filename.endswith('.jpg'):
                    self.assertEqual(embedded['ext'], 'jpeg')
                    self.assertEqual(embedded['image'], raw, 'Original JPEG DCT bytes must be retained')
                else:
                    with Image.open(BytesIO(embedded['image'])) as extracted:
                        self.assertEqual(extracted.size, source.size)
                        self.assertEqual(extracted.convert('RGB').tobytes(), source.convert('RGB').tobytes())
            self.assertEqual((self.stage / filename).read_bytes(), raw)
        self.assertTrue(any(w['asset'] == 'tall.png' for w in stats['warnings']))

    def test_bookmarks_index_links_page_numbers_and_all_occurrences(self):
        self.doc['question_ids'] += ['q-main']
        original_doc, original_lookup = deepcopy(self.doc), deepcopy(self.lookup)
        stats, pdf = self.render()
        self.assertEqual(stats['question_count'], 3)
        self.assertEqual([x['question_id'] for x in stats['question_pages']], original_doc['question_ids'])
        self.assertEqual(stats['pdf_pages'], len(pdf))
        self.assertEqual(stats['pdf_bytes'], (self.stage / self.doc['pdf']).stat().st_size)
        self.assertEqual(self.lookup, original_lookup)
        self.assertEqual({k: v for k, v in self.doc.items() if k not in ('pdf', 'pdf_pages', 'pdf_bytes')}, original_doc)
        toc = pdf.get_toc()
        self.assertTrue(any(level == 1 and '2025 main' in title for level, title, page in toc))
        self.assertTrue(any(level == 2 and '31/4/2' in title and 'exact <title>' in title
                            for level, title, page in toc))
        questions = [(title, page) for level, title, page in toc if level == 3]
        self.assertEqual(len(questions), 3)
        for entry, (title, page) in zip(stats['question_pages'], questions):
            self.assertEqual(page, entry['page'])
            self.assertTrue(title.startswith(entry['question_id'] + ' |'))
            self.assertIn(entry['question_id'], pdf[page - 1].get_text())
            self.assertIn(entry['question_id'], pdf[entry['source_page'] - 1].get_text())
        links = [(page, link) for page in pdf for link in page.get_links()
                 if link['kind'] == pymupdf.LINK_GOTO]
        self.assertGreaterEqual(len(links), 7)
        for page, link in links:
            self.assertGreaterEqual(link['page'], 0)
            self.assertLess(link['page'], len(pdf))
            rect = pymupdf.Rect(link['from'])
            number = page.get_textbox(pymupdf.Rect(505, rect.y0 - 1, 551, rect.y1 + 1)).strip()
            self.assertEqual(number, str(link['page'] + 1))

    def test_exact_provenance_links_nonadditive_marks_and_answer_hold(self):
        stats, pdf = self.render()
        text = '\n'.join(p.get_text() for p in pdf)
        self.assertIn('Source ID: src-exact-01', text)
        self.assertIn('Original question label: 33(b) OR', text)
        self.assertIn('Source PDF page(s), one-based: [7, 8]', text)
        self.assertIn('Original section: SECTION D', text)
        self.assertIn('Choice group: 2025-33', text)
        self.assertIn('Alternative: B', text)
        self.assertIn('VERIFIED_SOLUTION', text)
        self.assertIn('Withheld: official answer has an identified error.', text)
        self.assertIn('Source verification: NOT verified', text)
        self.assertNotIn('HELD_ANSWER_MUST_NEVER_PRINT', text)
        self.assertNotIn('TRANSCRIPTION_MUST_NOT_REPLACE', text)
        self.assertNotIn('999', text)
        self.assertIn('Source marks (nonadditive): 3', text)
        self.assertNotIn('\ufffd', text)
        uris = [link['uri'] for p in pdf for link in p.get_links() if link['kind'] == pymupdf.LINK_URI]
        self.assertIn(self.q['source_url'], uris)
        self.assertIn(self.q['marking_scheme_url'], uris)
        for entry in stats['question_pages']:
            # The entry can span pages; prove both sources are independently printed.
            self.assertEqual(entry['source_id'], 'src-exact-01')
        self.assertEqual(text.count('Source ID: src-exact-01'), 2)

    def test_text_and_link_layout_bounds_with_long_prose(self):
        self.q['answer'] = ('verified prose Ω < & > ' * 1500) + 'END_VERIFIED_PROSE'
        _, pdf = self.render()
        self.assertIn('END_VERIFIED_PROSE', '\n'.join(p.get_text() for p in pdf))
        for page in pdf:
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    rect = pymupdf.Rect(line['bbox'])
                    self.assertGreaterEqual(rect.x0, 44.9)
                    self.assertLessEqual(rect.x1, 550.4)
                    self.assertGreaterEqual(rect.y0, 30)
                    self.assertLessEqual(rect.y1, page.rect.height - 20)
            for link in page.get_links():
                rect = pymupdf.Rect(link['from'])
                self.assertTrue(page.rect.contains(rect))

    def test_long_index_noncontiguous_groups_and_multiple_calls(self):
        self.lookup = {}
        for i in range(80):
            q = dict(self.q, id=f'q-{i:03}', year=2025 if i % 2 else 2024,
                     source_title='Exact source ' + ('A' if i % 3 else 'B'),
                     answer_verified=False, answer_evidence_images=[], answer=None)
            self.lookup[q['id']] = q
        self.doc['question_ids'] = list(self.lookup)
        stats, pdf = self.render()
        self.assertGreater(stats['index_pages'], 2)
        self.assertEqual(len([r for r in pdf.get_toc() if r[0] == 3]), 80)
        self.assertEqual([r['page'] for r in stats['question_pages']],
                         list(range(stats['question_pages'][0]['page'], stats['question_pages'][0]['page'] + 80)))
        for row in stats['question_pages']:
            self.assertIn(row['question_id'], pdf[row['page'] - 1].get_text())
        self.doc['id'] = 'volume-two'
        self.doc['question_ids'] = self.doc['question_ids'][:2]
        second = render_collection(self.doc, self.lookup, self.stage)
        self.assertLess(second['pdf_pages'], stats['pdf_pages'])
        self.assertEqual(second['question_count'], 2)
        self.assertTrue((self.stage / stats['pdf']).is_file())

    def test_fail_closed_without_publishing_or_mutating_doc(self):
        cases = [({'kind': 'practice'}, {}), ({'id': '../escape'}, {}),
                 ({'question_ids': []}, {}), ({'question_ids': ['missing']}, {}),
                 ({'collection_type': 'sqp'}, {}), ({}, {'origin': 'original'}),
                 ({}, {'source_url': 'https://cbse.gov.in.evil.test/source.pdf'}),
                 ({}, {'marking_scheme_url': 'javascript:alert(1)'}),
                 ({}, {'evidence_images': ['../outside.png'], 'evidence_image': None}),
                 ({}, {'evidence_images': [], 'evidence_image': None})]
        for doc_update, q_update in cases:
            with self.subTest(doc_update=doc_update, q_update=q_update):
                doc = dict(self.doc, **doc_update)
                lookup = {'q-main': dict(self.q, **q_update), 'q-or': self.alt}
                before = deepcopy(doc)
                with self.assertRaises(CollectionRenderError):
                    render_collection(doc, lookup, self.stage)
                self.assertEqual(doc, before)
                self.assertFalse((self.stage / 'downloads').exists())

    def test_missing_metadata_is_not_invented(self):
        for q in self.lookup.values():
            for key in ('source_id', 'paper_code', 'year', 'original_section', 'marks'):
                q.pop(key)
        _, pdf = self.render()
        text = '\n'.join(p.get_text() for p in pdf)
        self.assertIn('Source ID: Not recorded', text)
        self.assertIn('Paper code: Not recorded', text)
        self.assertIn('Year: Not recorded', text)
        self.assertIn('Source marks (nonadditive): Not recorded', text)
        self.assertNotIn('Source ID: src-', text)

    def test_rgba_color_and_alpha_samples_are_preserved(self):
        size = (89, 91)
        raw = bytes((i * 23) % 256 for i in range(size[0] * size[1] * 4))
        image = Image.frombytes('RGBA', size, raw)
        image.save(self.stage / 'alpha.png')
        self.q['evidence_images'] = ['alpha.png']
        self.q['evidence_image'] = None
        self.doc['question_ids'] = ['q-main']
        _, pdf = self.render()
        info = next(info for p in pdf for info in p.get_images(full=True) if info[2:4] == size)
        xref, mask = info[:2]
        self.assertGreater(mask, 0)
        rgb = Image.open(BytesIO(pdf.extract_image(xref)['image']))
        alpha = Image.open(BytesIO(pdf.extract_image(mask)['image']))
        self.assertEqual(rgb.convert('RGB').tobytes(), image.convert('RGB').tobytes())
        self.assertEqual(alpha.convert('L').tobytes(), image.getchannel('A').tobytes())


if __name__ == '__main__':
    unittest.main()
