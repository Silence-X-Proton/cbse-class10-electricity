"""Official archive PDF renderer, independent of the legacy practice-paper layout.

render_collection(doc, lookup, stage) requires staged raster assets and normalized
question records (the same image aliases as build.images). It preserves input
question order, including alternatives and repeated IDs. Each source crop occupies
its own full-content-width page; unusually tall crops grow the page, never shrink
or split the figure. Paragraph-only sections paginate at a fixed readable size.

No source eligibility or verification is inferred here. The caller owns editorial
acceptance, collection membership, and volume splitting. Only answer_verified is
True authorizes solution material. Output is atomic and doc metadata changes only
after success. Returned page numbers are physical, one-based, including the index.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

PAGE_WIDTH, PAGE_HEIGHT = 595.28, 841.89
MARGIN, TOP, BOTTOM = 45.0, 42.0, 48.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
GAP = 9.0
QUESTION_IMAGES = ('evidence_images', 'evidence_image', 'diagram_image')
ANSWER_IMAGES = ('answer_evidence_images', 'answer_evidence_image')


class CollectionRenderError(ValueError):
    """Invalid or unsupported evidence must not silently produce a partial PDF."""


def _images(q, fields):
    result = []
    for key in fields:
        values = q.get(key) or []
        if not isinstance(values, list):
            values = [values]
        for value in values:
            src = value.get('src') if isinstance(value, dict) else value
            if src and src not in result:
                result.append(src)
    return result


def _text(value):
    if value is None or value == '':
        return 'Not recorded'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _official_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise CollectionRenderError(f'Invalid official URL: {value!r}')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ''
        valid = (parsed.scheme == 'https' and not parsed.username and not parsed.password
                 and parsed.port in (None, 443) and any(
                     host == domain or host.endswith('.' + domain)
                     for domain in ('cbse.gov.in', 'cbse.nic.in', 'cbseacademic.nic.in')))
    except ValueError as exc:
        raise CollectionRenderError('Invalid official URL') from exc
    if not valid:
        raise CollectionRenderError(f'Not an official CBSE HTTPS URL: {value!r}')
    return value


def _styles():
    for name, filename in [('ArchiveSans', 'DejaVuSans.ttf'),
                           ('ArchiveBold', 'DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, '/usr/share/fonts/truetype/dejavu/' + filename))
    return {
        'body': ParagraphStyle('archive-body', fontName='ArchiveSans', fontSize=10, leading=14),
        'small': ParagraphStyle('archive-small', fontName='ArchiveSans', fontSize=8.5, leading=12),
        'heading': ParagraphStyle('archive-heading', fontName='ArchiveBold', fontSize=12, leading=16),
        'title': ParagraphStyle('archive-title', fontName='ArchiveBold', fontSize=19, leading=25),
    }


@dataclass
class _Page:
    height: float = PAGE_HEIGHT
    # Items have positions measured from the top, avoiding hidden canvas clipping.
    items: list = field(default_factory=list)
    anchors: list = field(default_factory=list)


class _Planner:
    def __init__(self, styles):
        self.styles = styles
        self.pages = []
        self.page = None
        self.y = TOP
        self.anchors = {}

    def new_page(self, height=PAGE_HEIGHT):
        self.page = _Page(height)
        self.pages.append(self.page)
        self.y = TOP

    def paragraph(self, text, style='body', anchor=None, url=None):
        markup = escape(_text(text)).replace('\n', '<br/>')
        if url:
            markup = '<link href="' + escape(url, {'"': '&quot;'}) + '">' + markup + '</link>'
        todo = [Paragraph(markup, self.styles[style])]
        anchored = False
        while todo:
            if self.page is None:
                self.new_page()
            p = todo.pop(0)
            _, height = p.wrap(CONTENT_WIDTH, self.page.height)
            available = self.page.height - BOTTOM - self.y
            if height > available + 0.001:
                parts = p.split(CONTENT_WIDTH, available)
                if not parts:
                    if self.y == TOP:
                        raise CollectionRenderError('Text cannot fit at the configured readable font size')
                    self.new_page()
                    todo.insert(0, p)
                    continue
                p = parts[0]
                _, height = p.wrap(CONTENT_WIDTH, available)
                todo[0:0] = parts[1:]
            if anchor and not anchored:
                self.anchors[anchor] = len(self.pages)
                self.page.anchors.append((anchor, self.y))
                anchored = True
            self.page.items.append(('paragraph', p, self.y, height))
            self.y += height + GAP

    def crop(self, path, width, height, heading, detail, anchor):
        heading_p = Paragraph(escape(heading), self.styles['heading'])
        detail_p = Paragraph(escape(detail), self.styles['small'])
        _, heading_h = heading_p.wrap(CONTENT_WIDTH, PAGE_HEIGHT)
        _, detail_h = detail_p.wrap(CONTENT_WIDTH, PAGE_HEIGHT)
        crop_h = CONTENT_WIDTH * height / width
        image_top = TOP + heading_h + GAP + detail_h + GAP
        page_height = max(PAGE_HEIGHT, image_top + crop_h + BOTTOM)
        self.new_page(page_height)
        self.page.items.extend([
            ('paragraph', heading_p, TOP, heading_h),
            ('paragraph', detail_p, TOP + heading_h + GAP, detail_h),
            ('image', path, image_top, crop_h),
        ])
        self.anchors[anchor] = len(self.pages)
        self.page.anchors.append((anchor, TOP))
        # Never append prose underneath a crop: its custom height has a fixed budget.
        self.page = None
        return page_height


def _label(q):
    return (f"Source Q{_text(q.get('question_number'))} | Year: {_text(q.get('year'))} | "
            f"Session: {_text(q.get('session'))} | Code: {_text(q.get('paper_code'))} | "
            f"Marks: {_text(q.get('marks'))}")


def render_collection(doc, lookup, stage):
    """Write downloads/<id>.pdf; attach pdf/pdf_pages/pdf_bytes and return stats.

    Rasters are read without resizing or lossy encoding. JPEG filenames are passed
    directly to ReportLab so original DCT bytes survive. PNG/WebP pixels use PDF
    lossless streams (alpha is a separate soft mask). Palette images expand to RGB;
    unsupported high-bit-depth/animated sources fail instead of silently degrading.
    No per-collection total marks is computed or printed, even if doc has marks.
    """
    if doc.get('kind') != 'official':
        raise CollectionRenderError('render_collection accepts official archives, not practice papers')
    if not re.fullmatch(r'[a-z0-9_-]+', str(doc.get('id', ''))):
        raise CollectionRenderError('Unsafe or missing collection ID')
    ids = doc.get('question_ids')
    if not isinstance(ids, list) or not ids:
        raise CollectionRenderError('A collection must have a nonempty question_ids list')
    stage = Path(stage).resolve()
    questions, raster_info, warnings = [], {}, []
    expected_exam = {'pyq': 'PYQ', 'sqp': 'SQP'}.get(doc.get('collection_type'))
    for qid in ids:
        if qid not in lookup:
            raise CollectionRenderError(f'Missing question: {qid}')
        q = lookup[qid]
        if q.get('origin') not in (None, 'official') or q.get('exam_type') not in ('PYQ', 'SQP'):
            raise CollectionRenderError(f'Not an official question: {qid}')
        if expected_exam and q['exam_type'] != expected_exam:
            raise CollectionRenderError(f'Collection exam-type mismatch: {qid}')
        _official_url(q.get('source_url'))
        if q.get('marking_scheme_url'):
            _official_url(q['marking_scheme_url'])
        evidence = _images(q, QUESTION_IMAGES)
        if not evidence:
            raise CollectionRenderError(f'Missing source raster evidence: {qid}')
        sources = evidence + (_images(q, ANSWER_IMAGES) if q.get('answer_verified') is True else [])
        for src in sources:
            path = (stage / src).resolve()
            if not path.is_relative_to(stage) or not path.is_file():
                raise CollectionRenderError(f'Missing or out-of-stage asset: {src}')
            if path not in raster_info:
                with PILImage.open(path) as image:
                    if image.format not in ('PNG', 'JPEG', 'WEBP') or image.mode not in (
                            '1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'CMYK') or getattr(image, 'n_frames', 1) != 1:
                        raise CollectionRenderError(f'Unsupported raster format/mode: {src}')
                    image.load()
                    raster_info[path] = image.size
        questions.append(q)
    styles = _styles()
    body = _Planner(styles)
    entries, groups = [], OrderedDict()
    tall_pages, crop_count = 0, 0
    for index, (qid, q) in enumerate(zip(ids, questions), 1):
        anchor = f'question-{index}'
        label = _label(q)
        year_key = (_text(q.get('year')), _text(q.get('session')))
        paper_key = (_text(q.get('paper_code')), _text(q.get('source_title')))
        groups.setdefault(year_key, OrderedDict()).setdefault(paper_key, []).append((anchor, qid, label))
        entries.append({'occurrence': index, 'question_id': qid, 'anchor': anchor,
                        'label': label, 'source_id': q.get('source_id')})
        for crop_index, src in enumerate(_images(q, QUESTION_IMAGES), 1):
            path = (stage / src).resolve()
            width, height = raster_info[path]
            effective_dpi = width / (CONTENT_WIDTH / 72)
            if effective_dpi < 120:
                warnings.append({'question_id': qid, 'asset': src, 'kind': 'low_resolution',
                                 'effective_dpi': round(effective_dpi, 1)})
            detail = (f'{qid} | Crop {crop_index} | Source verification: '
                      + ('verified' if q.get('verified') is True else 'NOT verified')
                      + ' | Original pixels retained; low-quality sources may need zoom.')
            page_height = body.crop(path, width, height, label, detail,
                                    anchor if crop_index == 1 else f'{anchor}-crop-{crop_index}')
            tall_pages += page_height > PAGE_HEIGHT + 0.01
            crop_count += 1

    body.new_page()
    body.paragraph('Solutions and verification status', 'title', anchor='solutions')
    body.paragraph('Only explicitly verified solutions are printed. Missing solutions are not a claim '
                   'that a question is unsolvable. Official marking schemes may contain errors or omissions.')
    for index, (qid, q) in enumerate(zip(ids, questions), 1):
        body.paragraph(f'{index}. {qid} — {_label(q)}', 'heading', anchor=f'solution-{index}')
        if q.get('answer_verified') is True and (q.get('answer') or _images(q, ANSWER_IMAGES)):
            if q.get('answer'):
                body.paragraph(q['answer'])
            for crop_index, src in enumerate(_images(q, ANSWER_IMAGES), 1):
                path = (stage / src).resolve()
                width, height = raster_info[path]
                page_height = body.crop(path, width, height, f'Verified solution — {qid}',
                                        _label(q) + f' | Solution crop {crop_index}',
                                        f'answer-{index}-crop-{crop_index}')
                tall_pages += page_height > PAGE_HEIGHT + 0.01
                crop_count += 1
            body.paragraph('Marking-scheme PDF page(s), one-based: ' + _text(
                q.get('answer_source_pages') or q.get('answer_source_page')), 'small')
        else:
            body.paragraph(q.get('solution_status') or
                           'No explicitly verified solution supplied; answer material withheld.')
        if q.get('answer_verification_note'):
            body.paragraph('Answer verification note: ' + str(q['answer_verification_note']), 'small')
        if q.get('marking_scheme_url'):
            body.paragraph('Official marking scheme: ' + q['marking_scheme_url'], 'small',
                           url=q['marking_scheme_url'])

    body.new_page()
    body.paragraph('Per-question exact source appendix', 'title', anchor='sources')
    body.paragraph('Question labels and provenance below are source-record values, not inferred from '
                   'filenames. Physical source PDF page numbers are one-based. Missing metadata is '
                   'explicitly marked Not recorded; no source_id or paper code is synthesized.')
    provenance_fields = (
        ('source_id', 'Source ID'), ('source_title', 'Source title'), ('exam_type', 'Exam type'),
        ('year', 'Year'), ('session', 'Session'), ('paper_code', 'Paper code'), ('set', 'Set'),
        ('question_number', 'Original question label'), ('original_section', 'Original section'),
        ('marks', 'Source marks (nonadditive)'), ('parent_question_number', 'Parent question label'),
        ('selected_alternative', 'Alternative'), ('choice_group', 'Choice group'),
        ('exam_mark_group', 'Exam mark group'), ('marks_include_internal_choice', 'Marks include choice'),
        ('verified', 'Source verified'), ('answer_verified', 'Answer verified'),
    )
    optional_fields = ('question_crop_regions', 'choice_resolved', 'verification_scope', 'publication_status',
                       'audit_decision', 'requires_review', 'choice_unresolved', 'scope_uncertain',
                       'boundary_uncertain', 'quarantined', 'marks_status', 'scope_status', 'boundary_status',
                       'original_question_marks', 'included_subparts', 'excluded_subparts', 'subpart_marks',
                       'choice_limit', 'notes', 'source_sha256', 'pdf_file')
    for index, (qid, q) in enumerate(zip(ids, questions), 1):
        body.paragraph(f'{index}. {qid}', 'heading', anchor=f'source-{index}')
        for key, title in provenance_fields:
            body.paragraph(title + ': ' + _text(q.get(key)), 'small')
        body.paragraph('Source PDF page(s), one-based: ' + _text(q.get('pages') or q.get('page')), 'small')
        for key in optional_fields:
            if key in q:
                body.paragraph(key + ': ' + _text(q[key]), 'small')
        body.paragraph('Source raster asset(s): ' + _text(_images(q, QUESTION_IMAGES)), 'small')
        if q.get('answer_verified') is True:
            for key in ('answer_provenance', 'answer_transcription', 'answer_crop_regions',
                        'answer_complete_in_marking_scheme'):
                if key in q:
                    body.paragraph(key + ': ' + _text(q[key]), 'small')
        body.paragraph('Official source: ' + q['source_url'], 'small', url=q['source_url'])
        if q.get('marking_scheme_url'):
            body.paragraph('Official marking scheme: ' + q['marking_scheme_url'], 'small',
                           url=q['marking_scheme_url'])

    # Index columns reserve their number width in advance: pagination is independent
    # of final digit counts, avoiding a fragile repeated TOC rendering pass.
    front = _Planner(styles)
    front.paragraph(doc.get('title') or doc['id'], 'title', anchor='collection')
    if doc.get('subtitle'):
        front.paragraph(doc['subtitle'], 'heading')
    front.paragraph(f'Official-source question archive | {len(ids)} source occurrences')
    front.paragraph('This is an editorial chapter archive, not a CBSE-issued paper or practice test. '
                    'All supplied question occurrences and alternatives are retained. Source marks '
                    'are not additive; no total marks or suggested test duration is assigned.')
    front.paragraph('Crops use the full content width with original pixels retained. Tall crops have '
                    'custom-height pages rather than clipped or split figures. Use actual-size/zoom '
                    'viewing; fitting a tall page to a screen or printer can make text unreadable. '
                    'Low-resolution source material cannot be repaired by this layout.')
    if doc.get('status') != 'ready':
        front.paragraph('DRAFT — source/editorial verification is incomplete; see question-level status.')
    front.new_page()
    front.paragraph('Contents / source-question index', 'title', anchor='index')
    front.paragraph('Printed page numbers are physical PDF pages, including this index. '
                    'Question pages preserve supplied order; index and bookmarks group sources.')

    def index_row(text, target, heading=False):
        p = Paragraph(escape(text), styles['heading' if heading else 'small'])
        _, h = p.wrap(CONTENT_WIDTH - 52, PAGE_HEIGHT)
        if h > PAGE_HEIGHT - TOP - BOTTOM:
            raise CollectionRenderError('Index label exceeds a page')
        if front.y + h > PAGE_HEIGHT - BOTTOM:
            front.new_page()
        front.page.items.append(('index', (p, target), front.y, h))
        front.y += h + GAP

    for year, papers in groups.items():
        first = next(iter(papers.values()))[0][0]
        index_row(f'Year: {year[0]} | Session: {year[1]}', first, True)
        for paper, members in papers.items():
            index_row(f'Code: {paper[0]} | {paper[1]}', members[0][0], True)
            for target, qid, label in members:
                index_row(qid + ' | ' + label, target)
    index_row('Solutions and verification status', 'solutions', True)
    index_row('Per-question exact source appendix', 'sources', True)
    offset = len(front.pages)
    destinations = dict(front.anchors)
    destinations.update({key: value + offset for key, value in body.anchors.items()})
    all_pages = front.pages + body.pages
    for entry in entries:
        entry['page'] = destinations[entry['anchor']]
        entry['solution_page'] = destinations[f"solution-{entry['occurrence']}"]
        entry['source_page'] = destinations[f"source-{entry['occurrence']}"]

    output = stage / 'downloads' / (doc['id'] + '.pdf')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.pdf', delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        canvas = Canvas(str(temporary), pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=1)
        canvas.setTitle(str(doc.get('title') or doc['id']))
        canvas.setAuthor('Electricity study library')
        canvas.addOutlineEntry('Collection', 'collection', level=0)
        canvas.addOutlineEntry('Contents / source-question index', 'index', level=0)
        for year, papers in groups.items():
            first = next(iter(papers.values()))[0][0]
            canvas.addOutlineEntry(f'Year: {year[0]} | Session: {year[1]}', first + '-year', level=0)
            for paper, members in papers.items():
                canvas.addOutlineEntry(f'Code: {paper[0]} | {paper[1]}', members[0][0] + '-paper', level=1)
                for target, qid, label in members:
                    canvas.addOutlineEntry(qid + ' | ' + label, target, level=2)
        canvas.addOutlineEntry('Solutions and verification status', 'solutions', level=0)
        canvas.addOutlineEntry('Per-question exact source appendix', 'sources', level=0)
        for page_number, page in enumerate(all_pages, 1):
            canvas.setPageSize((PAGE_WIDTH, page.height))
            for anchor, top in page.anchors:
                canvas.bookmarkPage(anchor, fit='XYZ', left=MARGIN, top=page.height - top, zoom=0)
                # Alias destinations keep independent year/paper/question outlines.
                if anchor.startswith('question-') and '-crop-' not in anchor:
                    for suffix in ('-year', '-paper'):
                        canvas.bookmarkPage(anchor + suffix, fit='XYZ', left=MARGIN,
                                            top=page.height - top, zoom=0)
            for kind, value, top, height in page.items:
                bottom = page.height - top - height
                if kind == 'paragraph':
                    value.drawOn(canvas, MARGIN, bottom)
                elif kind == 'image':
                    canvas.drawImage(str(value), MARGIN, bottom, CONTENT_WIDTH, height, mask='auto')
                else:
                    p, target = value
                    p.drawOn(canvas, MARGIN, bottom)
                    canvas.setFont('ArchiveSans', 9)
                    canvas.drawRightString(PAGE_WIDTH - MARGIN, page.height - top - 11,
                                           str(destinations[target]))
                    canvas.linkRect('', target, (MARGIN, bottom, PAGE_WIDTH - MARGIN, page.height - top),
                                    relative=0, thickness=0)
            canvas.setFont('ArchiveSans', 8)
            canvas.drawString(MARGIN, 25, 'Electricity | Official-source archive')
            canvas.drawRightString(PAGE_WIDTH - MARGIN, 25, f'{page_number} / {len(all_pages)}')
            canvas.showPage()
        canvas.save()
        # Inspect actual output, not a page estimate, before publication/metadata.
        import pymupdf
        with pymupdf.open(temporary) as pdf:
            if len(pdf) != len(all_pages):
                raise CollectionRenderError('Generated PDF page count differs from the plan')
            page_count = len(pdf)
        byte_count = temporary.stat().st_size
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    relative = 'downloads/' + output.name
    doc.update(pdf=relative, pdf_pages=page_count, pdf_bytes=byte_count)
    return {'pdf': relative, 'pdf_pages': page_count, 'pdf_bytes': byte_count,
            'question_count': len(ids), 'question_pages': entries, 'crop_count': crop_count,
            'custom_height_pages': tall_pages, 'index_pages': offset - front.anchors['index'] + 1,
            'solutions_page': destinations['solutions'], 'sources_page': destinations['sources'],
            'warnings': warnings}
