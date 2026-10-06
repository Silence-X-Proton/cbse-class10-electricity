"""Fixed-A4, vector-only renderer for the original special39 practice papers.

The caller owns the 39-question/80-mark structure and editorial acceptance. Input
assets must already be staged, as with build.Assets. This module never substitutes
an official-source crop for original prose and never gates original solutions on
answer_verified. Answers, marking schemes and design rationale are rear matter.
Only pdf/pdf_pages/pdf_bytes are attached to doc, after atomic publication.

SVGs are converted by svglib, never rasterized. All transformed label sizes must
remain >= MIN_LABEL_SIZE points. Unsupported raster/external/clipped SVG content
fails closed; oversize artwork is rejected rather than clipped or made illegible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import math
from pathlib import Path
import re
import tempfile
from xml.sax.saxutils import escape

from lxml import etree
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Group, String, Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from svglib.svglib import svg2rlg

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN, TOP, BOTTOM = 45.0, 53.0, 49.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
CONTENT_HEIGHT = PAGE_HEIGHT - TOP - BOTTOM
MIN_LABEL_SIZE = 8.5
MIN_VECTOR_SCALE = 0.5
GAP = 8.0
INK, ACCENT = HexColor('#182d40'), HexColor('#176a78')
QUESTION_IMAGES = ('diagram_image', 'diagram_images', 'evidence_image', 'evidence_images',
                   'svg', 'svgs', 'diagram', 'diagrams', 'images')
ANSWER_IMAGES = ('answer_evidence_image', 'answer_evidence_images', 'answer_diagram',
                 'answer_diagrams', 'solution_image', 'solution_images', 'solution_svg')
SECTIONS = (('A', 1, 20, 1), ('B', 21, 26, 2), ('C', 27, 33, 3),
            ('D', 34, 36, 5), ('E', 37, 39, 4))


class Special39RenderError(ValueError):
    """An input cannot be rendered faithfully within readable A4 bounds."""


def _first(record, *keys):
    for key in keys:
        value = record.get(key)
        if value is not None and value != '' and value != []:
            return value
    return None


def _text(value):
    """Preserve supplied wording and structured optional metadata, not Python repr."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, list):
        return '\n'.join(_text(item) for item in value)
    if isinstance(value, dict):
        return '\n'.join(f'{key}: {_text(item)}' for key, item in value.items())
    return str(value)


def _items(value):
    return value if isinstance(value, list) else ([] if value is None else [value])


def _images(record, fields):
    result = []
    for key in fields:
        for item in _items(record.get(key)):
            src = _first(item, 'src', 'path', 'file') if isinstance(item, dict) else item
            if src and src not in result:
                result.append(src)
    return result


def _styles():
    for suffix, filename in (('', 'DejaVuSans.ttf'), ('Bold', 'DejaVuSans-Bold.ttf'),
                             ('Italic', 'DejaVuSans-Oblique.ttf'),
                             ('BoldItalic', 'DejaVuSans-BoldOblique.ttf')):
        name = 'Special39' + suffix
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, '/usr/share/fonts/truetype/dejavu/' + filename))
    return {
        'body': ParagraphStyle('special-body', fontName='Special39', fontSize=10.5,
                               leading=15, textColor=INK, splitLongWords=True),
        'small': ParagraphStyle('special-small', fontName='Special39', fontSize=9,
                                leading=13, textColor=INK, splitLongWords=True),
        'heading': ParagraphStyle('special-heading', fontName='Special39Bold', fontSize=13,
                                  leading=18, textColor=ACCENT),
        'question': ParagraphStyle('special-question', fontName='Special39Bold', fontSize=10.5,
                                   leading=15, textColor=ACCENT),
        'title': ParagraphStyle('special-title', fontName='Special39Bold', fontSize=25,
                                leading=32, textColor=INK),
    }


def _multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def _scales(matrix):
    # Singular values catch skewed/nonuniformly transformed text, not just scale().
    a, b, c, d = matrix[:4]
    total = a*a+b*b+c*c+d*d
    disc = math.sqrt(max(0, total*total-4*(a*d-b*c)**2))
    return math.sqrt(max(0, (total-disc)/2)), math.sqrt(max(0, (total+disc)/2))


def _svg(path):
    raw = path.read_bytes()
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I):
        raise Special39RenderError(f'DTD/entities are unsupported in SVG: {path.name}')
    try:
        root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as exc:
        raise Special39RenderError(f'Invalid SVG: {path.name}') from exc
    if etree.QName(root).localname != 'svg':
        raise Special39RenderError(f'Not an SVG: {path.name}')
    # These can be silently lost by svglib or introduce hidden raster/network data.
    forbidden = {'image', 'foreignObject', 'filter', 'mask', 'clipPath', 'script',
                 'textPath', 'pattern', 'linearGradient', 'radialGradient', 'symbol'}
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        tag = etree.QName(node).localname
        if tag in forbidden or tag.startswith('animate'):
            raise Special39RenderError(f'Unsupported SVG element {tag}: {path.name}')
        if tag == 'style' and re.search(r'@import|url\s*\(', node.text or '', re.I):
            raise Special39RenderError(f'External/paint CSS is unsupported: {path.name}')
        for key, value in node.attrib.items():
            attr = etree.QName(key).localname
            if attr == 'href' and not value.startswith('#'):
                raise Special39RenderError(f'External SVG reference: {path.name}')
            if attr in ('filter', 'mask', 'clip-path') and value != 'none':
                raise Special39RenderError(f'Unsupported SVG clipping/effect: {path.name}')
    try:
        drawing = svg2rlg(BytesIO(raw))
    except Exception as exc:
        raise Special39RenderError(f'Cannot convert SVG: {path.name}') from exc
    if drawing is None or not all(math.isfinite(v) and v > 0
                                  for v in (drawing.width, drawing.height)):
        raise Special39RenderError(f'Invalid SVG dimensions: {path.name}')
    labels, stroke_padding = [], [1.0]

    def visit(node, transform=(1, 0, 0, 1, 0, 0)):
        if isinstance(node, Image):
            raise Special39RenderError(f'Raster in converted SVG: {path.name}')
        if isinstance(node, Group):
            transform = _multiply(transform, node.transform)
            for child in node.contents:
                visit(child, transform)
        else:
            low, high = _scales(transform)
            if isinstance(node, String) and node.text.strip():
                font = node.fontName.lower()
                suffix = ('Bold' if 'bold' in font else '')
                suffix += 'Italic' if 'italic' in font or 'oblique' in font else ''
                node.fontName = 'Special39' + suffix
                labels.append(node.fontSize * low)
            stroke_padding[0] = max(stroke_padding[0],
                                    (getattr(node, 'strokeWidth', 0) or 0) * high)
    visit(drawing)
    bounds = drawing.getBounds()
    if not bounds or not all(math.isfinite(x) for x in bounds):
        raise Special39RenderError(f'Empty/invalid SVG artwork: {path.name}')
    # Include overflow beyond the SVG viewport rather than losing source labels.
    pad = stroke_padding[0] + 2
    x0, y0 = min(0, bounds[0])-pad, min(0, bounds[1])-pad
    x1, y1 = max(drawing.width, bounds[2])+pad, max(drawing.height, bounds[3])+pad
    width, height = x1-x0, y1-y0
    fit = min(CONTENT_WIDTH/width, CONTENT_HEIGHT/height)
    minimum = max(MIN_VECTOR_SCALE, MIN_LABEL_SIZE/min(labels)) if labels and min(labels) > 0 else MIN_VECTOR_SCALE
    if (labels and min(labels) <= 0) or fit + 1e-8 < minimum:
        raise Special39RenderError(f'SVG too large at readable minimum ({MIN_LABEL_SIZE} pt labels): {path.name}')
    scale = max(minimum, min(1, fit))
    return drawing, (x0, y0), width*scale, height*scale, scale, min(labels)*scale if labels else None


@dataclass
class _Page:
    items: list = field(default_factory=list)
    anchors: list = field(default_factory=list)
    label: str = ''


class _Layout:
    def __init__(self, styles, stage):
        self.styles, self.stage = styles, stage
        self.pages, self.outline, self.anchors, self.figures = [], [], {}, []
        self.page, self.y, self.label = None, TOP, ''
        self.svg_cache = {}

    def new_page(self, label=None):
        if label is not None:
            self.label = label
        self.page = _Page(label=self.label)
        self.pages.append(self.page)
        self.y = TOP

    def paragraph(self, text, style='body', anchor=None, level=0, bookmark=None, keep=0):
        if text is None or text == '':
            return
        todo = [Paragraph(escape(_text(text)).replace('\n', '<br/>'), self.styles[style])]
        while todo:
            if self.page is None:
                self.new_page()
            paragraph = todo.pop(0)
            _, height = paragraph.wrap(CONTENT_WIDTH, CONTENT_HEIGHT)
            if keep and height + keep > PAGE_HEIGHT - BOTTOM - self.y and self.y > TOP:
                self.new_page()
            available = PAGE_HEIGHT - BOTTOM - self.y
            if height > available + 1e-6:
                parts = paragraph.split(CONTENT_WIDTH, max(0, available))
                if not parts:
                    if self.y == TOP:
                        raise Special39RenderError('Text cannot fit the A4 readable text frame')
                    self.new_page()
                    todo.insert(0, paragraph)
                    continue
                paragraph = parts[0]
                _, height = paragraph.wrap(CONTENT_WIDTH, available)
                todo[0:0] = parts[1:]
            if anchor:
                self.page.anchors.append((anchor, self.y))
                self.anchors[anchor] = len(self.pages)
                self.outline.append((bookmark or _text(text), anchor, level))
                anchor = None
            self.page.items.append(('text', paragraph, self.y, height))
            self.y += height + GAP

    def heading(self, text, anchor=None, level=0, style='heading'):
        self.paragraph(text, style, anchor, level, keep=45)

    def image(self, src):
        if not isinstance(src, str):
            raise Special39RenderError('SVG asset path must be a string')
        path = (self.stage / src).resolve()
        if not path.is_relative_to(self.stage) or not path.is_file() or path.suffix.lower() != '.svg':
            raise Special39RenderError(f'Missing, non-SVG or out-of-stage asset: {src}')
        if path not in self.svg_cache:
            self.svg_cache[path] = _svg(path)
        figure = self.svg_cache[path]
        height = figure[3]
        if self.page is None or self.y + height > PAGE_HEIGHT - BOTTOM + 1e-6:
            self.new_page()
        self.page.items.append(('svg', figure, self.y, height))
        self.figures.append({'asset': src, 'page': len(self.pages), 'width': figure[2],
                             'height': height, 'minimum_label_pt': figure[5]})
        self.y += height + GAP

    def section_content(self, section):
        self.heading(_first(section, 'heading', 'title'))
        for text in _items(_first(section, 'paragraphs', 'text', 'content')):
            self.paragraph(text)
        for text in _items(section.get('bullets')):
            self.paragraph('• ' + _text(text))
        for src in _images(section, QUESTION_IMAGES):
            self.image(src)


def _section_destination(section):
    key = ' '.join(str(section.get(k, '')) for k in ('role', 'type', 'heading', 'title')).lower()
    if re.search(r'source|pattern|rationale|competency|appendix|blueprint', key):
        return 'appendix'
    if re.search(r'solution|answer|marking', key):
        return 'solutions'
    return 'cover'


def _options(value):
    if isinstance(value, dict):
        return [f'{label}. {_text(text)}' for label, text in value.items()]
    result = []
    for i, item in enumerate(_items(value)):
        if isinstance(item, dict):
            label = _first(item, 'label', 'key') or chr(65+i)
            result.append(f'{label}. {_text(_first(item, "text", "value", "option"))}')
        else:
            text = _text(item)
            result.append(text if re.match(r'^\s*\(?[A-Da-d][.)]\s', text)
                          else f'{chr(65+i)}. {text}')
    return result


def render_special39(doc, lookup, stage):
    """Write downloads/<id>.pdf, update doc metadata, return layout statistics.

    Numbering follows question_ids, never source-bank numbering. Structural/mark
    validation is deliberately the parent's responsibility. Aliases choose the
    first supplied prose field; diagram aliases are combined and deduplicated.
    """
    if not re.fullmatch(r'[a-z0-9_-]+', str(doc.get('id', ''))):
        raise Special39RenderError('Unsafe or missing document ID')
    if doc.get('kind') == 'official':
        raise Special39RenderError('Special39 papers must be original, not official')
    ids = doc.get('question_ids')
    if not isinstance(ids, list) or not ids:
        raise Special39RenderError('A nonempty ordered question_ids list is required')
    questions = []
    for qid in ids:
        if qid not in lookup:
            raise Special39RenderError(f'Missing question: {qid}')
        q = lookup[qid]
        if q.get('origin') not in (None, 'original'):
            raise Special39RenderError(f'Not an original question: {qid}')
        if not _first(q, 'text', 'question_text', 'stem'):
            raise Special39RenderError(f'Missing original question text: {qid}')
        questions.append(q)
    stage = Path(stage).resolve()
    layout = _Layout(_styles(), stage)
    layout.new_page('Original practice • Instructions')
    layout.heading(doc.get('title') or doc['id'], 'cover', style='title')
    layout.paragraph('CLASS 10 • ELECTRICITY • ORIGINAL PRACTICE', 'small')
    layout.paragraph(doc.get('subtitle'), 'heading')
    layout.paragraph('Original chapter practice — not an official examination paper, a prediction, or an official chapter weightage.')
    if doc.get('status') not in (None, 'ready', 'complete', 'final'):
        layout.paragraph('DRAFT — editorial review is not complete.', 'heading')
    details = [f'{len(ids)} questions']
    if doc.get('marks') is not None:
        details.append(f'{doc["marks"]} marks')
    if doc.get('duration_minutes') is not None:
        details.append(f'{doc["duration_minutes"]} minutes')
    layout.paragraph(' • '.join(details), 'heading')
    layout.paragraph(doc.get('description'))
    layout.heading('Paper structure')
    for code, start, end, marks in SECTIONS:
        layout.paragraph(f'Section {code}  |  Questions {start}–{end}  |  {end-start+1} × {marks} = {(end-start+1)*marks} marks', 'small')
    layout.heading('Instructions')
    layout.paragraph('Attempt all questions. There are no internal OR choices. Sections A–E form the question paper. Detailed solutions and marking guidance begin only after Question 39; source-pattern and competency rationale follow in a separate appendix.')
    layout.paragraph(doc.get('instructions'))
    sections = doc.get('sections') or []
    for section in sections:
        if _section_destination(section) == 'cover':
            layout.section_content(section)

    question_entries = []
    last_section = None
    for number, (qid, q) in enumerate(zip(ids, questions), 1):
        default_section = next((code for code, start, end, _ in SECTIONS if start <= number <= end), '')
        section = _first(q, 'section', 'compilation_section') or default_section
        if section != last_section:
            layout.new_page(f'Question paper • Section {section}')
            layout.heading(f'Section {section}', f'section-{number}')
            last_section = section
        anchor = f'question-{number}'
        marks = f'  |  {q["marks"]} mark' + ('' if q['marks'] == 1 else 's') if q.get('marks') is not None else ''
        layout.heading(f'Question {number}{marks}', anchor, 1, 'question')
        layout.paragraph(qid, 'small')
        layout.paragraph(_first(q, 'text', 'question_text', 'stem'))
        for src in _images(q, QUESTION_IMAGES):
            layout.image(src)
        for option in _options(q.get('options')):
            layout.paragraph(option)
        question_entries.append({'number': number, 'question_id': qid,
                                 'page': layout.anchors[anchor]})

    layout.new_page('Detailed solutions')
    layout.heading('Detailed solutions and marking guidance', 'solutions')
    layout.paragraph('Original model answers, numbered to match the question paper. These are not an official marking scheme.')
    for section in sections:
        if _section_destination(section) == 'solutions':
            layout.section_content(section)
    for number, (qid, q) in enumerate(zip(ids, questions), 1):
        anchor = f'solution-{number}'
        layout.heading(f'Solution {number} — {qid}', anchor, 1, 'question')
        answer = _first(q, 'answer', 'solution', 'detailed_answer', 'answer_text')
        if q.get('correct_option') is not None:
            layout.paragraph('Correct option: ' + _text(q['correct_option']))
        if answer is not None:
            layout.paragraph(answer)
        elif q.get('solution_status'):
            layout.paragraph(q['solution_status'])
        else:
            layout.paragraph('No model answer supplied.', 'small')
        for key in ('explanation', 'solution_steps'):
            if q.get(key) and q[key] != answer:
                layout.paragraph(q[key])
        scheme = _first(q, 'marking_scheme', 'mark_scheme', 'marking_steps')
        if scheme:
            layout.heading('Mark allocation', style='question')
            for item in _items(scheme):
                if isinstance(item, dict):
                    prose = {k: v for k, v in item.items() if k != 'marks'}
                    text = _text(next(iter(prose.values()))) if len(prose) == 1 else _text(prose)
                    if item.get('marks') is not None:
                        text += f' [{item["marks"]} marks]'
                    layout.paragraph(text)
                else:
                    layout.paragraph(item)
        for src in _images(q, ANSWER_IMAGES):
            layout.image(src)
        question_entries[number-1]['solution_page'] = layout.anchors[anchor]

    layout.new_page('Source-pattern and rationale appendix')
    layout.heading('Source-pattern and rationale appendix', 'appendix')
    layout.paragraph('These questions are original. References identify supplied source patterns and curriculum connections, not official provenance for these questions or predictions of future examinations. No missing references or rationale have been inferred.')
    for section in sections:
        if _section_destination(section) == 'appendix':
            layout.section_content(section)
    for number, (qid, q) in enumerate(zip(ids, questions), 1):
        layout.heading(f'Question {number} — {qid}', f'rationale-{number}', 1, 'question')
        supplied = False
        for label, keys in (
                ('Source patterns', ('source_pattern_refs', 'source_patterns', 'source_pattern_ids')),
                ('NCERT references', ('ncert_refs', 'curriculum_refs')),
                ('Competency classification', ('competency', 'competency_classification', 'classification')),
                ('Competency marks', ('competency_marks',)),
                ('Competency rationale', ('competency_rationale',)),
                ('Design rationale', ('source_pattern_rationale', 'rationale')),
                ('Rationale tags', ('rationale_tags',))):
            value = _first(q, *keys)
            if value is not None:
                layout.paragraph(label + ': ' + _text(value), 'small')
                supplied = True
        if not supplied:
            layout.paragraph('No source-pattern or rationale metadata supplied.', 'small')
    for label, key in (('Source reference details', 'sources'), ('Design rationale', 'source_pattern_rationale')):
        if doc.get(key):
            layout.heading(label)
            layout.paragraph(doc[key], 'small')

    output = stage / 'downloads' / (doc['id'] + '.pdf')
    if not output.resolve().is_relative_to(stage):
        raise Special39RenderError('Output path escapes stage')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.special39-', suffix='.pdf', dir=output.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
        canvas = Canvas(str(temporary), pagesize=A4, pageCompression=1)
        canvas.setTitle(_text(doc.get('title') or doc['id']))
        canvas.setAuthor('Electricity study library — original practice')
        for page_number, page in enumerate(layout.pages, 1):
            canvas.setPageSize(A4)
            canvas.setFillColor(ACCENT)
            canvas.setFont('Special39', 8)
            canvas.drawString(MARGIN, PAGE_HEIGHT-29, page.label)
            canvas.setStrokeColor(ACCENT)
            canvas.setLineWidth(0.6)
            canvas.line(MARGIN, PAGE_HEIGHT-38, PAGE_WIDTH-MARGIN, PAGE_HEIGHT-38)
            for anchor, y in page.anchors:
                canvas.bookmarkHorizontalAbsolute(anchor, PAGE_HEIGHT-y)
            for kind, item, y, height in page.items:
                if kind == 'text':
                    item.drawOn(canvas, MARGIN, PAGE_HEIGHT-y-height)
                else:
                    drawing, (x0, y0), width, _, scale, _ = item
                    canvas.saveState()
                    canvas.translate(MARGIN+(CONTENT_WIDTH-width)/2, PAGE_HEIGHT-y-height)
                    canvas.scale(scale, scale)
                    renderPDF.draw(drawing, canvas, -x0, -y0)
                    canvas.restoreState()
            canvas.setFillColor(INK)
            canvas.setFont('Special39', 8)
            canvas.drawString(MARGIN, 27, 'Electricity • Original practice')
            canvas.drawRightString(PAGE_WIDTH-MARGIN, 27, f'Page {page_number} of {len(layout.pages)}')
            canvas.showPage()
        for title, anchor, level in layout.outline:
            canvas.addOutlineEntry(title, anchor, level=level, closed=level == 0)
        canvas.save()
        pdf_bytes = temporary.stat().st_size
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    result = {'pdf': 'downloads/' + output.name, 'pdf_pages': len(layout.pages),
              'pdf_bytes': pdf_bytes, 'question_count': len(ids),
              'question_pages': question_entries, 'solution_start_page': layout.anchors['solutions'],
              'appendix_start_page': layout.anchors['appendix'], 'svg_count': len(layout.figures),
              'figures': layout.figures}
    doc.update({key: result[key] for key in ('pdf', 'pdf_pages', 'pdf_bytes')})
    return result
