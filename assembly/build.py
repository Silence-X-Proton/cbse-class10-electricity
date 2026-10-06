#!/opt/venv/bin/python
"""Evidence-preserving Class X Electricity assembly. Missing inputs exit 2; no polling."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import sys
import subprocess
import tempfile
from urllib.parse import urlparse
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = ROOT / 'assembly'
SITE = ROOT / 'site'
INPUTS = {'sqp': 'research/sqp/question_bank.json', 'pyq': 'research/pyq/question_bank.json',
          'originals': 'content/originals.json', 'notes': 'content/notes.json',
          'pyq_metadata': 'research/pyq/publication_metadata.json'}
SECTION_NAMES = {'A': 'Section A — MCQ', 'B': 'Section B — 2-mark questions',
                 'C': 'Section C — 3-mark questions', 'D': 'Section D — 5-mark / case-based questions'}
IMAGE_FIELDS = ('evidence_images', 'evidence_image', 'diagram_image')
ANSWER_IMAGE_FIELDS = ('answer_evidence_images', 'answer_evidence_image')
COPY_FIELDS = ('pdf_file', 'marking_scheme_pdf_file', 'marking_scheme_file', 'answer_pdf_file')
SLUG = re.compile(r'^[a-z0-9_-]+$')

class Blocked(Exception):
    pass

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)

def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def load_inputs():
    loaded, blockers = {}, []
    for name, relative in INPUTS.items():
        path = ROOT / relative
        if not path.exists():
            blockers.append(f'Missing final input: {relative}')
            continue
        try:
            value = json.loads(path.read_text())
        except (ValueError, OSError) as e:
            blockers.append(f'Unreadable input {relative}: {e}')
            continue
        if isinstance(value, dict) and value.get('status') not in (None, 'ready', 'complete', 'final'):
            blockers.append(f'{relative}: explicit status {value.get("status")!r} is not ready')
        else:
            loaded[name] = value
    if (ROOT / INPUTS['pyq']).exists() and not (ROOT/'research/pyq/READY.md').exists():
        blockers.append('PYQ bank exists but research/pyq/READY.md is absent; recovery still owns finalization')
    if 'pyq_metadata' in loaded:
        ready = ROOT/'research/pyq/PUBLICATION_READY.md'
        heading = ready.read_text().splitlines()[0] if ready.exists() else ''
        if 'READY' not in heading.upper() or 'IN PROGRESS' in heading.upper():
            blockers.append('Publication metadata handoff is not READY; fragments cannot be assembled')
    return loaded, blockers

def records(value, keys):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in keys:
            if isinstance(value.get(key), list):
                return value[key]
    raise Blocked(f'Expected an array or object with one of {keys}')

def images(question, fields=IMAGE_FIELDS):
    result = []
    for field in fields:
        value = question.get(field) or []
        if not isinstance(value, list):
            value = [value]
        for image in value:
            src = image.get('src') if isinstance(image, dict) else image
            if src and src not in result:
                result.append(src)
    return result

class Assets:
    def __init__(self, stage):
        self.stage = stage
        self.manifest = {}
    def copy(self, raw):
        if not raw:
            return None
        if isinstance(raw, dict):
            return {**raw, 'src': self.copy(raw['src'])}
        if isinstance(raw, list):
            return [self.copy(x) for x in raw]
        path = Path(raw)
        if not path.is_absolute():
            candidates = [ROOT / path, SITE / path, ROOT/'content'/path]
            if str(path).startswith('assets/research/originals/'):
                candidates.append(ROOT/'content/assets'/path.name)
            path = next((p for p in candidates if p.exists()), candidates[0])
        path = path.resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise Blocked(f'Asset outside project: {raw}')
        if not path.is_file() or path.suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg', '.webp', '.svg'):
            raise Blocked(f'Missing or unsupported asset (ZIPs are not copied): {raw}')
        sha = digest(path)
        suffix = path.suffix.lower()
        relative = f'assets/research/{sha[:20]}{suffix}'
        dest = self.stage / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copyfile(path, dest)
        if digest(dest) != sha:
            raise Blocked(f'Copy integrity failure: {raw}')
        self.manifest[relative] = {'source': str(path.relative_to(ROOT)), 'sha256': sha,
                                   'bytes': path.stat().st_size}
        return relative

def source_key(q):
    # No guessed branch pairing: at most one printed source slot per compilation.
    label = str(q.get('parent_question_number') or q.get('question_number') or '')
    match = re.search(r'\d+', label)
    return '|'.join(str(x or '') for x in (q.get('source_url'), q.get('session'),
                    q.get('paper_code') or q.get('source_title'), match.group() if match else label))

def fingerprint(q):
    text = re.sub(r'\W+', '', q.get('text', '').casefold())
    return text if len(text) > 35 else '|'.join(images(q)) or q['id']

def section(q):
    marks, kind = q.get('marks'), str(q.get('type', '')).lower()
    if marks == 1 and ('mcq' in kind or 'assertion' in kind): return 'A'
    if 'case' in kind: return 'D'
    return {2: 'B', 3: 'C', 5: 'D'}.get(marks)

def eligible(q, for_paper=True):
    issues = []
    for key in ('id', 'source_title', 'session', 'source_url', 'question_number', 'original_section'):
        if not q.get(key): issues.append(f'missing {key}')
    if not q.get('year') and not re.search(r'20\d{2}', str(q.get('session', ''))):
        issues.append('missing year/session year')
    url = urlparse(q.get('source_url', ''))
    if url.scheme != 'https' or not (url.hostname and (url.hostname.endswith('.cbse.gov.in') or
            url.hostname == 'cbse.gov.in' or url.hostname.endswith('.cbseacademic.nic.in') or
            url.hostname == 'cbseacademic.nic.in' or url.hostname.endswith('.cbse.nic.in') or
            url.hostname == 'cbse.nic.in')):
        issues.append('source URL is not a recognized official HTTPS CBSE host')
    pages = q.get('pages') or ([q['page']] if q.get('page') else [])
    if not pages or any(type(p) is not int or p < 1 for p in pages): issues.append('invalid PDF pages')
    if type(q.get('marks')) not in (int, float) or q['marks'] <= 0: issues.append('unresolved marks')
    if not images(q): issues.append('missing authoritative question evidence')
    if for_paper and not section(q): issues.append('outside supported A/B/C/D marks/type inventory; not relabelled MCQ')
    for key in ('requires_review', 'choice_unresolved', 'scope_uncertain', 'boundary_uncertain', 'quarantined'):
        if q.get(key): issues.append(f'{key} flagged')
    if q.get('audit_decision') in ('exclude', 'requires_review', 'quarantine'):
        issues.append('audit rejects or requires review')
    if q.get('include') is False: issues.append('source owner excludes record')
    for field in ('marks_status', 'scope_status', 'boundary_status'):
        status = str(q.get(field, '')).lower()
        if any(word in status for word in ('inferred', 'uncertain', 'unresolved', 'ambiguous')):
            issues.append(f'{field}: {status}')
    if (q.get('recovery_audit') or {}).get('decision') in ('exclude', 'requires_review'):
        issues.append('nested recovery audit rejects/requires review')
    hold_path = ASSEMBLY/'source_holds.json'
    for hold in json.loads(hold_path.read_text()) if hold_path.exists() else []:
        if hold['id'] == q.get('id'):
            for raw in images(q):
                path = Path(raw)
                if not path.is_absolute(): path = ROOT/path
                if path.is_file() and digest(path) == hold['evidence_sha256']:
                    issues.append('Assembly source hold: ' + hold['reason'])
    # Literal standalone OR inside question body needs explicit accounting by source owner.
    if re.search(r'(?m)^\s*(?:OR|Or|\(OR\))\s*$', q.get('text', '')) and not (
            q.get('selected_alternative') or q.get('choice_resolved') is True or q.get('marks_include_internal_choice') is True):
        issues.append('unresolved OR block in question text')
    return issues

def normalize_question(raw, origin, assets):
    q = deepcopy(raw)
    q['origin'] = origin
    q['verified'] = raw.get('verified') is True
    q['answer_verified'] = raw.get('answer_verified') is True
    q.setdefault('text', '')
    q.setdefault('topic', 'Electricity')
    q.setdefault('type', 'question')
    q.setdefault('marks', None)
    if isinstance(q.get('options'), dict):
        q['source_options'] = deepcopy(q['options'])
        q['options'] = [f'{label}. {value}' for label,value in q['options'].items()]
    if isinstance(q.get('options'), list) and any(isinstance(x, dict) for x in q['options']):
        q['source_options'] = deepcopy(q['options'])
        q['options'] = [f"{x['label']}. {x['text']}" if isinstance(x, dict) else x for x in q['options']]
    if origin == 'official':
        q['pages'] = q.get('pages') or [q['page']]
        q['page'] = q['pages'][0]
        # Session is authoritative. Do not turn its start/end year into an invented exam year.
        if not q.get('year'): q['year'] = q.get('session')
        q['compilation_section'] = section(q)
        q['assembly_source_slot'] = source_key(q)
    if origin == 'official' and not q['answer_verified']:
        reason = q.get('answer_verification_note') or ('No independently verified official answer supplied.' if not q.get('answer') else 'Answer material has not completed verification.')
        q['solution_status'] = 'Official answer unavailable/withheld: ' + reason
        q['notes'] = (q.get('notes') or '') + ' Official answer unavailable/withheld for an identified error, omission or incomplete verification: ' + reason + ' Consult the linked original marking scheme with this limitation in mind.'
        for key in ('answer', 'answer_transcription', 'answer_crop_regions', 'answer_provenance', 'answer_pdf_file') + ANSWER_IMAGE_FIELDS:
            q.pop(key, None)
        # Historical raw records are research audit data, not a second publishable answer channel.
        q.pop('provenance_records', None)
    for field in IMAGE_FIELDS + ANSWER_IMAGE_FIELDS + COPY_FIELDS:
        if q.get(field): q[field] = assets.copy(q[field])
    # Normalize common MS alias, without losing the original metadata value.
    if not q.get('marking_scheme_pdf_file'):
        q['marking_scheme_pdf_file'] = q.get('marking_scheme_file') or q.get('answer_pdf_file')
    if q.get('answer_source_pages'):
        q['answer_source_page'] = q['answer_source_pages']
    if not q['answer_verified'] and (q.get('answer') or images(q, ANSWER_IMAGE_FIELDS)):
        q['solution_status'] = 'Unverified source answer retained for audit; omitted from printable solution key.'
    return sanitize_coverage(q)

def compile_official(questions):
    if not questions: raise Blocked('No eligible official questions')
    buckets = {s: [q for q in questions if section(q) == s] for s in SECTION_NAMES}
    uses, used_sets, docs = Counter(), set(), []
    pyq_years = sorted({str(q.get('year')) for q in questions if q.get('exam_type') == 'PYQ'})
    for index in range(15):
        chosen = None
        for attempt in range(150):
            rng = random.Random(12000 + index * 150 + attempt)
            picked, slots, choices, texts = [], set(), set(), set()
            def add(q):
                group = q.get('choice_group')
                if source_key(q) in slots or (group and group in choices) or fingerprint(q) in texts: return False
                if sum(x['marks'] for x in picked) + q['marks'] > 40: return False
                picked.append(q); slots.add(source_key(q)); texts.add(fingerprint(q))
                if group: choices.add(group)
                return True
            # Seed up to three distinct board years, rotating the starting year across papers.
            # Never infer a missing year or manufacture a section to achieve diversity.
            if pyq_years:
                start = (index * 2 + attempt) % len(pyq_years)
                targets = [pyq_years[(start + offset) % len(pyq_years)] for offset in range(min(3, len(pyq_years)))]
                for year in targets:
                    pool = [q for q in questions if q.get('exam_type') == 'PYQ' and str(q.get('year')) == year]
                    rng.shuffle(pool); pool.sort(key=lambda q: uses[q['id']])
                    for q in pool:
                        if add(q): break
            for s, quota in [('A', 4), ('B', 4), ('C', 3), ('D', 2)]:
                pool = buckets[s][:]; rng.shuffle(pool)
                n = sum(section(q) == s for q in picked)
                while pool and n < quota:
                    sessions = Counter((q.get('exam_type'), q.get('year'), q.get('session')) for q in picked)
                    pool.sort(key=lambda q: (sessions[(q.get('exam_type'), q.get('year'), q.get('session'))], uses[q['id']]))
                    if add(pool.pop(0)): n += 1
            pool = questions[:]; rng.shuffle(pool); pool.sort(key=lambda q: uses[q['id']])
            for q in pool:
                if sum(x['marks'] for x in picked) >= 32: break
                add(q)
            ids = frozenset(q['id'] for q in picked)
            has_pyq = not pyq_years or any(q.get('exam_type') == 'PYQ' for q in picked)
            has_sections = all(not buckets[code] or any(section(q) == code for q in picked) for code in SECTION_NAMES)
            if sum(q['marks'] for q in picked) >= 20 and ids not in used_sets and has_pyq and has_sections:
                chosen = sorted(picked, key=lambda q: q['compilation_section']); break
        if chosen is None:
            raise Blocked(f'Inventory cannot produce 15 distinct meaningful (>=20 marks) compilations; stopped at {len(docs)}')
        used_sets.add(frozenset(q['id'] for q in chosen))
        uses.update(q['id'] for q in chosen)
        total = sum(q['marks'] for q in chosen)
        missing = [SECTION_NAMES[s] for s, qs in buckets.items() if not qs]
        paragraphs = ['Curated compilation of official CBSE source questions, not a CBSE-issued chapter paper. Original source labels and exact source images are retained.',
            'Answer every selected question. Only one selected source-slot alternative appears in this paper; do not answer or count excluded alternatives.',
            'Questions recur across this 15-paper collection. Reuse is disclosed per question in the source appendix; these are not 15 disjoint official papers.',
            'Sections use available source marks: A MCQ; B 2 marks; C 3 marks; D 5 marks or source-marked case questions. Case marks are not inflated to five.']
        if total < 30: paragraphs.append(f'Inventory-limited paper: {total} marks; the preferred 30–40-mark target could not be reached without duplication.')
        if missing: paragraphs.append('Unavailable eligible sections: ' + '; '.join(missing))
        section_blocks = []
        for code, heading in SECTION_NAMES.items():
            positions = [i for i,q in enumerate(chosen,1) if section(q) == code]
            if positions:
                marks = sum(q['marks'] for q in chosen if section(q) == code)
                section_blocks.append({'heading':heading, 'paragraphs':[f'Compilation questions {positions[0]}–{positions[-1]}; {marks} marks. Exact source labels remain attached to each question.']})
        docs.append({'id': f'official-{index+1:02d}', 'kind': 'official',
            'title': f'Official-source Electricity compilation {index+1:02d}',
            'subtitle': 'Mixed-source chapter worksheet • cross-paper reuse disclosed',
            'status': 'ready' if all(q.get('verified') is True for q in chosen) else 'draft',
            'marks': total, 'duration_minutes': math.ceil(total * 2),
            'question_ids': [q['id'] for q in chosen],
            'sections': [{'heading': 'Instructions and reuse disclosure', 'paragraphs': paragraphs}] + section_blocks})
    return docs, uses

def authored(value, kind, expected, assets):
    docs = records(value, ('documents', 'papers', 'notes'))
    rootqs = value.get('questions', []) if isinstance(value, dict) else []
    questions = {}
    for q in rootqs:
        normalized = normalize_question(q, 'original', assets); questions[q['id']] = normalized
    result = []
    for raw in docs:
        doc = deepcopy(raw)
        if not SLUG.fullmatch(str(doc.get('id', ''))): raise Blocked('Authored document needs stable lowercase slug ID')
        doc['kind'] = kind
        embedded = doc.pop('questions', [])
        for q in embedded:
            if q['id'] in questions and questions[q['id']] != normalize_question(q, 'original', assets):
                raise Blocked(f'Conflicting authored question: {q["id"]}')
            questions[q['id']] = normalize_question(q, 'original', assets)
        doc.setdefault('question_ids', [q['id'] for q in embedded])
        doc.setdefault('sections', [])
        for s in doc['sections']:
            if s.get('images'): s['images'] = assets.copy(s['images'])
        doc.pop('pdf', None)
        doc.setdefault('status', 'draft')
        if kind == 'practice':
            doc.setdefault('subtitle', 'Original prediction/practice — not official and not a guarantee')
            if not doc['question_ids']: raise Blocked(f'Original paper has no questions: {doc["id"]}')
            if any(qid not in questions for qid in doc['question_ids']): raise Blocked(f'Unresolved original question IDs in {doc["id"]}')
            total = sum(questions[qid].get('marks') or 0 for qid in doc['question_ids'])
            if doc.get('marks') is not None and doc['marks'] != total: raise Blocked(f'Authored marks mismatch: {doc["id"]}')
            doc['marks'] = total
        elif not any(s.get('paragraphs') or s.get('bullets') or s.get('images') for s in doc['sections']):
            raise Blocked(f'Notes document has no content: {doc["id"]}')
        result.append(doc)
    if len(result) != expected: raise Blocked(f'Expected {expected} {kind} documents, got {len(result)}')
    return result, list(questions.values())

def build_coverage(inputs, official, excluded):
    limitations = ['Fifteen mixed-source compilations are not fifteen distinct official CBSE chapter papers. Questions are reused across papers with per-question disclosure.',
        'Last-ten-year coverage is bounded by the source inventories below. Downloaded bundles do not imply every year, set, language, supplementary sitting or alternative was analysed.',
        'The cancelled 2021 Class X annual examination must not be represented as a normal annual PYQ sitting. Sample papers are a separate category.',
        'Unverified answers are excluded from printable solution keys. Source images are not automatically verified by rendering.',
        f'{len(excluded)} source records were excluded from paper selection by assembly checks; details are in the assembly validation report.']
    details = {}
    for name in ('sqp', 'pyq'):
        path = ROOT / ('research/sqp/coverage_manifest.json' if name == 'sqp' else 'research/pyq/coverage.json')
        if path.exists():
            details[name] = json.loads(path.read_text())
        elif isinstance(inputs[name], dict) and inputs[name].get('coverage'):
            details[name] = inputs[name]['coverage']
        else:
            limitations.append(f'{name.upper()}: final detailed coverage manifest was not supplied; no exhaustive coverage claim is made.')
    sqp = details.get('sqp', {})
    if sqp:
        limitations.append(f"SQP declared scope: {sqp.get('scope', 'See source inventory')} Reviewed {sqp.get('english_sqp_count', '?')} English SQPs and {sqp.get('english_ms_count', '?')} English marking schemes, {sqp.get('english_sqp_pages_reviewed', '?')} + {sqp.get('english_ms_pages_reviewed', '?')} PDF pages. Separate alternatives are not additive.")
        limitations.extend('SQP: ' + x for x in sqp.get('known_limits', []))
    for year, inventory in details.get('pyq', {}).items():
        if isinstance(inventory, dict) and str(year).isdigit():
            limitations.append(f"PYQ {year}: {inventory.get('inventoried_qp_sets', 'not recorded')} inventoried sets; accepted {inventory.get('represented_count', inventory.get('accepted_records', inventory.get('record_count', 'not recorded')))} records; verified {inventory.get('verified_count', 'not recorded')}; unprocessed/missing-set entries {len(inventory.get('missing_unprocessed_sets', []))}; exhaustive coverage: {inventory.get('exhaustive', False)}. Downloaded is not reviewed.")
    selected_pyq = Counter(str(q.get('year')) for q in official if q.get('exam_type') == 'PYQ')
    limitations.append('Actual searchable-bank PYQ records by year: ' + (', '.join(f'{year}: {count} verified questions' for year,count in sorted(selected_pyq.items())) or 'none') + '. All eligible verified records are searchable, including records not selected in papers and genuine one-mark short-answer questions. Other accepted PYQ records lacking original section provenance or resolved choice accounting were held out. The research-bank inventory is broader than this published selection.')
    years = sorted(set(str(q.get('year') or q.get('session')) for q in official))
    return {'summary': 'Evidence-led Electricity revision with a partial, explicitly bounded official-source archive. Represented sessions: ' + ', '.join(years),
            'limitations': limitations, 'topics': [{'name': 'Electricity', 'status': 'partial',
            'note': 'Source-selected question coverage, not a certified exhaustive syllabus or all-set archive.'}],
            'source_inventory': details}

def pdf_render(doc, lookup, stage, reuse):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
    for name, file in [('DejaVu','DejaVuSans.ttf'), ('DejaVuBold','DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, '/usr/share/fonts/truetype/dejavu/' + file))
    pdfmetrics.registerFontFamily('DejaVu', normal='DejaVu', bold='DejaVuBold', italic='DejaVu', boldItalic='DejaVuBold')
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = 'DejaVu'
        if hasattr(style, 'fontSize'): style.leading = max(style.fontSize * 1.35, 13)
    styles.add(ParagraphStyle('SmallSource', fontName='DejaVu', fontSize=8, leading=11, wordWrap='CJK', spaceAfter=7))
    styles['BodyText'].spaceAfter = 7
    for name in ('Heading1', 'Heading2', 'Heading3'): styles[name].keepWithNext = True
    story = []
    def p(text, style='BodyText'):
        if text is not None and str(text): story.append(Paragraph(escape(str(text)).replace('\n', '<br/>'), styles[style]))
    def img(src):
        if isinstance(src, dict): src = src['src']
        path = stage / src
        if path.suffix.lower() == '.svg':
            from svglib.svglib import svg2rlg
            drawing = svg2rlg(str(path))
            if drawing is None: raise Blocked(f'Cannot render original SVG: {src}')
            factor = min(475 / drawing.width, 590 / drawing.height)
            drawing.scale(factor, factor); drawing.width *= factor; drawing.height *= factor
            story.append(drawing); story.append(Spacer(1, 8)); return
        width, height = ImageReader(str(path)).getSize()
        factor = min(475 / width, 590 / height)
        story.append(Image(str(path), width=width*factor, height=height*factor, hAlign='LEFT'))
        story.append(Spacer(1, 8))
    p(doc['title'], 'Title'); p(doc.get('subtitle'), 'Heading3')
    if doc.get('marks'): p(f"Total: {doc['marks']} marks • Suggested time: {doc.get('duration_minutes', 'not specified')} minutes")
    if doc['status'] != 'ready': p('DRAFT — editorial/source verification is incomplete. See question-level warnings.')
    p(doc.get('description'))
    for s in doc.get('sections', []):
        p(s.get('heading'), 'Heading2')
        for text in s.get('paragraphs', []): p(text)
        for text in s.get('bullets', []): p('• ' + str(text))
        for src in s.get('images', []): img(src)
    last = None
    for i, qid in enumerate(doc.get('question_ids', []), 1):
        q = lookup[qid]
        block_start = len(story)
        sec = q.get('compilation_section') or q.get('section')
        if sec and sec != last:
            p((SECTION_NAMES.get(sec, sec) if q['origin'] == 'official' else {'A':'Section A — MCQ','B':'Section B — 2-mark questions','C':'Section C — 3-mark questions','D':'Section D — 5-mark questions','E':'Section E — Case-based questions'}.get(sec, sec)), 'Heading2'); last = sec
        label = f"{i}. [{q.get('marks', '?')} marks]"
        if q['origin'] == 'official': label += f" Source Q{q['question_number']} • {q.get('session', '')}"
        p(label, 'Heading3')
        if not q['verified']: p('Source/text verification not completed; do not treat this crop as audited.', 'SmallSource')
        evidence = images(q)
        if q['origin'] == 'original' or not evidence:
            p(q.get('text'))
            for option in q.get('options', []): p(option)
        for src in evidence: img(src)
        if q.get('notes'): p('Source/editorial note: ' + str(q['notes']), 'SmallSource')
        block = story[block_start:]
        story[block_start:] = [KeepTogether(block)]
    verified_answers = [lookup[qid] for qid in doc.get('question_ids', []) if lookup[qid].get('answer_verified') is True
                        and (lookup[qid].get('answer') or images(lookup[qid], ANSWER_IMAGE_FIELDS))]
    if doc.get('question_ids'):
        story.append(PageBreak()); p('Solutions and verification status', 'Heading1')
        p('Only explicitly verified solutions are printed. A missing solution is not a claim that the question is unsolvable.')
        for i, qid in enumerate(doc['question_ids'], 1):
            q = lookup[qid]
            p(f"Question {i} — {qid}", 'Heading3')
            if q in verified_answers:
                p(q.get('answer'))
                for src in images(q, ANSWER_IMAGE_FIELDS): img(src)
                if q.get('answer_source_page'): p('Marking-scheme PDF page(s): ' + str(q['answer_source_page']), 'SmallSource')
                if q.get('marking_scheme_url'): p(q['marking_scheme_url'], 'SmallSource')
            else:
                p(q.get('solution_status') or 'No explicitly verified solution supplied; unverified answer material is not printed.')
                if q.get('marking_scheme_url'): p('Original marking scheme (see limitation above): ' + q['marking_scheme_url'], 'SmallSource')
    if doc['kind'] == 'official':
        story.append(PageBreak()); p('Per-question source appendix', 'Heading1')
        p('Original CBSE questions/images remain attributed to their source. Compilation selection and numbering are editorial. The full Science source PDFs may include unrelated chapters; only selected Electricity crops form this worksheet.')
        for i, qid in enumerate(doc['question_ids'], 1):
            q = lookup[qid]
            p(f'{i}. {qid}', 'Heading3')
            p(f"{q['source_title']} | {q.get('exam_type', 'Not recorded')} | Year/session: {q.get('year', 'Not recorded')} / {q['session']} | Paper code: {q.get('paper_code', 'Not recorded')} | Source question: {q['question_number']} | Original section: {q['original_section']} | Selected marks: {q['marks']} | PDF pages (one-based): {', '.join(map(str, q['pages']))}", 'SmallSource')
            p(q['source_url'], 'SmallSource')
            p('Also used in: ' + ', '.join(x for x in reuse[qid] if x != doc['id']) if len(reuse[qid]) > 1 else 'No cross-paper reuse.', 'SmallSource')
    output = stage / 'downloads' / (doc['id'] + '.pdf'); output.parent.mkdir(parents=True, exist_ok=True)
    def footer(canvas, pdfdoc):
        canvas.setFont('DejaVu', 8); canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawString(45, 27, f'Electricity • Class X • {doc["id"]}')
        canvas.drawRightString(550, 27, str(pdfdoc.page))
    SimpleDocTemplate(str(output), pagesize=(595.28, 841.89), rightMargin=45, leftMargin=45,
                      topMargin=42, bottomMargin=45, title=doc['title'], author='Electricity study library').build(story, onFirstPage=footer, onLaterPages=footer)
    doc['pdf'] = 'downloads/' + output.name

def validate(data, stage, require_final=False):
    import pymupdf
    problems, details = [], []
    docs, qs = data['documents'], data['questions']; lookup = {q['id']: q for q in qs}
    if len(lookup) != len(qs): problems.append('duplicate question IDs')
    if len({d['id'] for d in docs}) != len(docs): problems.append('duplicate document IDs')
    if Counter(d['kind'] for d in docs) != {'official':15, 'practice':4, 'notes':2}: problems.append('wrong 15/4/2 inventory')
    for doc in docs:
        ids = doc.get('question_ids', [])
        if len(ids) != len(set(ids)): problems.append(f'{doc["id"]}: duplicate question')
        if any(qid not in lookup for qid in ids): problems.append(f'{doc["id"]}: broken question reference'); continue
        items = [lookup[qid] for qid in ids]
        if items and doc.get('marks') != sum(q.get('marks') or 0 for q in items): problems.append(f'{doc["id"]}: marks mismatch')
        if doc['kind'] == 'official':
            for key, vals in [('source slot', [source_key(q) for q in items]), ('content', [fingerprint(q) for q in items])]:
                if len(vals) != len(set(vals)): problems.append(f'{doc["id"]}: repeated {key}')
            groups = [q['choice_group'] for q in items if q.get('choice_group')]
            if len(groups) != len(set(groups)): problems.append(f'{doc["id"]}: double-counted internal choice')
            if require_final and any(not q['verified'] for q in items): problems.append(f'{doc["id"]}: unverified official source question')
        if require_final and doc['status'] != 'ready': problems.append(f'{doc["id"]}: status is not ready')
        path = stage / doc.get('pdf', 'missing')
        if not path.is_file(): problems.append(f'{doc["id"]}: missing downloadable PDF'); continue
        with pymupdf.open(path) as pdf:
            if pdf.page_count < 1: problems.append(f'{doc["id"]}: empty PDF')
            text = '\n'.join(page.get_text() for page in pdf)
            if '�' in text: problems.append(f'{doc["id"]}: replacement glyph in PDF extraction')
            if doc['kind'] == 'official' and 'Per-question source appendix' not in text: problems.append(f'{doc["id"]}: source appendix missing')
            details.append({'id':doc['id'], 'kind':doc['kind'], 'marks':doc.get('marks'),
                            'questions':len(ids), 'sections':dict(Counter(q.get('compilation_section') or q.get('section') for q in items)), 'pyq_years':sorted({str(q.get('year')) for q in items if q.get('exam_type')=='PYQ'}), 'sqp_sessions':sorted({str(q.get('session')) for q in items if q.get('exam_type')=='SQP'}), 'pdf_pages':pdf.page_count, 'pdf_bytes':path.stat().st_size, 'status':doc['status']})
    def walk(value):
        if isinstance(value, dict):
            for v in value.values(): walk(v)
        elif isinstance(value, list):
            for v in value: walk(v)
        elif isinstance(value, str):
            if '/a0/' in value: problems.append('published data contains a local absolute path')
            if value.startswith(('assets/research/', 'downloads/')):
                if '..' in Path(value).parts or not (stage / value).is_file(): problems.append(f'broken/unsafe asset link: {value}')
    walk(data)
    return problems, details

def sanitize_coverage(value):
    # Inventories can contain research-local paths. Publish only descriptive relative provenance.
    if isinstance(value, dict): return {k: sanitize_coverage(v) for k,v in value.items()}
    if isinstance(value, list): return [sanitize_coverage(v) for v in value]
    if isinstance(value, str): return value.replace(str(ROOT) + '/', '')
    return value

def apply_publication_metadata(bank, metadata):
    if not isinstance(metadata, dict):
        raise Blocked('Publication metadata must be an object keyed by canonical root question IDs')
    validation_path = ROOT/'research/pyq/publication_validation.json'
    if validation_path.exists():
        expected = json.loads(validation_path.read_text()).get('canonical_bank_sha256')
        if expected and digest(ROOT/INPUTS['pyq']) != expected:
            raise Blocked('Canonical PYQ bank hash differs from reviewed overlay base')
    result = deepcopy(bank)
    lookup = {q['id']: q for q in result}
    allowed = {'original_section', 'question_number', 'parent_question_number', 'pages', 'page',
               'marks', 'type', 'choice_group', 'choice_resolved', 'selected_alternative',
               'marks_include_internal_choice', 'evidence_image', 'evidence_images', 'diagram_image',
               'text', 'options', 'notes', 'paper_code', 'source_title', 'year', 'session',
               'scope_status', 'boundary_status', 'marks_status', 'metadata_review',
               'alternative_label', 'choice_instruction', 'choice_note', 'has_internal_choice',
               'branch', 'branch_marks', 'subpart_marks', 'original_question_marks', 'evidence_crop',
               'choice_unresolved', 'crop_bbox_pdf_points', 'diagram_images', 'evidence_crops',
               'exact_question_text', 'image', 'image_path', 'images', 'question_text'}
    seen = set()
    for identity, updates in metadata.items():
        item = {'id':identity, 'updates':updates}
        if identity not in lookup or identity in seen:
            raise Blocked(f'Unknown or duplicate overlay record ID: {identity}')
        seen.add(identity)
        if not isinstance(updates, dict) or not updates.get('metadata_review'):
            raise Blocked(f'Overlay {identity} needs explicit updates with metadata_review source evidence')
        unknown = set(item['updates']) - allowed
        if unknown: raise Blocked(f'Overlay {identity} uses unreviewed fields: {sorted(unknown)}')
        q = lookup[identity]
        q['publication_metadata'] = deepcopy(item)
        q.update(deepcopy(item['updates']))
    return result

def run(args):
    loaded, blockers = load_inputs()
    state = {'stage':'preparatory', 'inputs':INPUTS, 'available_inputs':sorted(loaded), 'blockers':blockers,
             'published':False}
    if blockers:
        write_json(ASSEMBLY/'status.json', state); print(json.dumps(state, indent=2)); return 2
    input_hashes = {name:digest(ROOT/path) for name,path in INPUTS.items()}
    excluded = []
    with tempfile.TemporaryDirectory(prefix='build-', dir=ASSEMBLY) as tmp:
        stage = Path(tmp); assets = Assets(stage); official = []
        raw_ids = set()
        for name in ('sqp','pyq'):
            bank = records(loaded[name], ('questions','question_bank','items'))
            if name == 'pyq': bank = apply_publication_metadata(bank, loaded['pyq_metadata'])
            for raw in bank:
                q = deepcopy(raw); q.setdefault('exam_type', name.upper())
                if q.get('id') in raw_ids: raise Blocked(f'Duplicate source-bank ID: {q.get("id")}')
                raw_ids.add(q.get('id'))
                issues = eligible(q, for_paper=False)
                if q.get('verified') is not True: issues.append('Source question is not verified; excluded from ready official selections')
                if issues: excluded.append({'id':q.get('id'),'reasons':issues}); continue
                official.append(q)
        # Every eligible verified record is searchable, even when not selected in a paper.
        for q in official: q['compilation_section'] = section(q)
        paper_pool = [q for q in official if section(q)]
        official_docs, uses = compile_official(paper_pool)
        official = [normalize_question(q, 'official', assets) for q in official]
        practice_docs, practice_questions = authored(loaded['originals'], 'practice', 4, assets)
        note_docs, note_questions = authored(loaded['notes'], 'notes', 2, assets)
        docs = official_docs + practice_docs + note_docs
        questions = official + practice_questions + note_questions
        lookup = {q['id']:q for q in questions}; reuse = defaultdict(list)
        for d in official_docs:
            for qid in d['question_ids']: reuse[qid].append(d['id'])
        for q in official:
            q['compilation_reuse'] = reuse[q['id']]
            q['bank_only'] = not bool(reuse[q['id']])
        sources = {}
        for q in official:
            sid = 'src-' + hashlib.sha256((q['source_url'] + str(q.get('pdf_file'))).encode()).hexdigest()[:12]
            q['source_id'] = sid
            sources[sid] = {'id':sid, 'title':q['source_title'], 'year':q.get('year'), 'session':q['session'],
                            'exam_type':q['exam_type'], 'url':q['source_url'], 'local_pdf':q.get('pdf_file'),
                            'marking_scheme_url':q.get('marking_scheme_url')}
        for name in ('originals', 'notes'):
            bundle = loaded[name]
            for raw in bundle.get('sources', []) if isinstance(bundle, dict) else []:
                src = deepcopy(raw)
                if src.get('local_pdf'): src['local_pdf'] = assets.copy(src['local_pdf'])
                if src['id'] in sources and sources[src['id']] != src:
                    raise Blocked(f'Conflicting source ID: {src["id"]}')
                sources[src['id']] = sanitize_coverage(src)
        data = {'schema_version':1, 'meta':{'title':'Electricity — Class 10 study library', 'chapter':'Electricity',
                 'updated':date.today().isoformat(), 'intro':'Official-source compilations and original revision material; provenance and limitations remain visible.'},
                'coverage':sanitize_coverage(build_coverage(loaded, official, excluded)),
                'documents':docs, 'questions':questions, 'sources':list(sources.values())}
        for doc in docs: pdf_render(doc, lookup, stage, reuse)
        problems, details = validate(data, stage, args.final)
        # Use the owner's exact validator against the staged root before publication.
        write_json(stage/'data/content.json', data)
        validator = SITE/'tools/validate.mjs'
        if validator.exists():
            script = "import fs from 'node:fs'; import {validate} from " + json.dumps(validator.as_uri()) + "; const result=validate(JSON.parse(fs.readFileSync(process.argv[1], 'utf8')), {root:process.argv[2], final:process.argv[3]==='true'}); console.log(JSON.stringify(result));"
            checked = subprocess.run(['node','--input-type=module','-e',script,str(stage/'data/content.json'),str(stage),str(args.final).lower()], capture_output=True, text=True, timeout=60)
            if checked.returncode:
                problems.append('Site validator execution failed: ' + checked.stderr[:1500])
            else:
                site_result = json.loads(checked.stdout)
                problems.extend('Site validator: ' + msg for msg in site_result['errors'])
        else:
            problems.append('Site validator unavailable; publication deferred')
        report = {'stage':'validated' if not problems else 'blocked', 'published':False, 'blockers':problems,
                  'documents':details, 'counts':dict(Counter(d['kind'] for d in docs)),
                  'unique_official_questions':len(official), 'official_question_appearances':sum(uses.values()),
                  'selected_unique_official_questions':len(uses),
                  'bank_only_official_questions':sum(q['bank_only'] for q in official),
                  'published_pyq_year_counts':dict(sorted(Counter(str(q['year']) for q in official if q['exam_type']=='PYQ').items())),
                  'selected_pyq_year_counts':dict(sorted(Counter(str(q['year']) for q in official if q['exam_type']=='PYQ' and not q['bank_only']).items())),
                  'published_sqp_session_counts':dict(sorted(Counter(str(q['session']) for q in official if q['exam_type']=='SQP').items())),
                  'excluded_records':excluded, 'asset_count':len(assets.manifest),
                  'asset_bytes':sum(x['bytes'] for x in assets.manifest.values()),
                  'ready_count':sum(d['status']=='ready' for d in docs),
                  'strict_final_requested':args.final}
        write_json(ASSEMBLY/'validation.json', report)
        write_json(ASSEMBLY/'asset_manifest.json', assets.manifest)
        if problems:
            write_json(ASSEMBLY/'status.json', report); print(json.dumps(report, indent=2)); return 2
        if any(digest(ROOT/path) != input_hashes[name] for name,path in INPUTS.items()):
            raise Blocked('Input files changed during build; rerun against the completed owner handoff')
        report['input_sha256'] = input_hashes
        # Content JSON switches last. Old working library stays intact on any earlier failure.
        for folder in ('assets/research','downloads'):
            for source in (stage/folder).glob('*'):
                dest=SITE/folder/source.name; dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source, dest.with_suffix(dest.suffix+'.tmp'))
                dest.with_suffix(dest.suffix+'.tmp').replace(dest)
        write_json(SITE/'data/content.json', data)
        report.update(stage='assembled', published=True)
        write_json(ASSEMBLY/'validation.json', report); write_json(ASSEMBLY/'status.json', report)
        print(json.dumps(report, indent=2)); return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true', help='Require 21 ready documents and verified official questions')
    args = parser.parse_args()
    try: return run(args)
    except (Blocked, KeyError, ValueError, TypeError, OSError) as e:
        state={'stage':'blocked','published':False,'blockers':[f'{type(e).__name__}: {e}']}
        write_json(ASSEMBLY/'status.json', state); print(json.dumps(state, indent=2)); return 2
if __name__ == '__main__': sys.exit(main())
