#!/opt/venv/bin/python
"""Stage Special39 papers and/or current verified-bank masters; never publish."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import build
import build_v2 as archives
from pdf_special39 import render_special39

ROOT, ASSEMBLY, SITE = build.ROOT, build.ASSEMBLY, build.SITE
AUTHOR = ROOT / 'content/special39'
DOC_IDS = [f'special-39-{n:02}' for n in range(1, 5)]
PREFIX = 'assets/research/special39/'


def blueprint(number):
    if number <= 16: return 'A', 1, 'MCQ'
    if number <= 20: return 'A', 1, 'assertion_reason'
    if number <= 26: return 'B', 2, 'short2'
    if number <= 33: return 'C', 3, 'short3'
    if number <= 36: return 'D', 5, 'long5'
    return 'E', 4, 'case4'


def load_author():
    required = ['originals.json', 'READY.md', 'audit.json', 'validate_bundle.mjs']
    missing = [name for name in required if not (AUTHOR / name).is_file()]
    if missing:
        raise build.Blocked('Special39 author handoff missing: ' + ', '.join(missing))
    heading = (AUTHOR / 'READY.md').read_text().splitlines()[:1]
    heading = heading[0].upper() if heading else ''
    if not re.search(r'\bREADY\b', heading) or any(word in heading for word in ('NOT READY', 'IN PROGRESS', 'PENDING', 'DRAFT')):
        raise build.Blocked('Special39 author handoff is not READY')
    audit = json.loads((AUTHOR / 'audit.json').read_text())
    if not isinstance(audit, dict) or audit.get('errors') or not (
            audit.get('passed') is True or audit.get('status') in ('ready', 'passed', 'complete')):
        raise build.Blocked('Special39 independent author audit has not passed')
    bundle = json.loads((AUTHOR / 'originals.json').read_text())
    # Import the pure author validator: its CLI writes in author scope, which we do not own.
    script = 'import fs from "node:fs"; import {validateBundle} from ' + json.dumps((AUTHOR / 'validate_bundle.mjs').as_uri()) + '; console.log(JSON.stringify(validateBundle(JSON.parse(fs.readFileSync(process.argv[1],"utf8")))));'
    result = subprocess.run(['node', '--input-type=module', '-e', script, str(AUTHOR / 'originals.json')], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise build.Blocked('Author validator execution failed: ' + result.stderr[:1500])
    report = json.loads(result.stdout)
    if report.get('passed') is not True or report.get('errors'):
        raise build.Blocked('Author structural validation: ' + json.dumps(report.get('errors'), ensure_ascii=False))
    hashes = {str((AUTHOR / name).relative_to(ROOT)): build.digest(AUTHOR / name) for name in required}
    return bundle, audit, report, hashes


class SpecialAssets(build.Assets):
    def copy(self, raw):
        if isinstance(raw, str) and raw.startswith(PREFIX):
            name = raw[len(PREFIX):]
            if Path(name).name != name or not name.endswith('.svg'):
                raise build.Blocked('Unsafe Special39 SVG alias: ' + raw)
            path = AUTHOR / 'assets' / name
            if path.is_symlink() or not path.resolve().is_relative_to((AUTHOR / 'assets').resolve()):
                raise build.Blocked('Special39 SVG must remain in author assets')
            return super().copy(str(path))
        return super().copy(raw)


def validate_blueprint(bundle):
    """Independent arithmetic/structure gate; not a physics or competency-merit audit."""
    docs, questions = bundle.get('documents', []), bundle.get('questions', [])
    if Counter(d.get('id') for d in docs) != Counter(DOC_IDS) or len(questions) != 156:
        raise build.Blocked('Special39 requires exactly four fixed document IDs and 156 questions')
    lookup = {q['id']: q for q in questions}
    if len(lookup) != 156:
        raise build.Blocked('Duplicate Special39 question IDs')
    report, used = [], []
    numeric = lambda value: type(value) in (int, float) and math.isfinite(value)
    for doc in docs:
        identity = doc['id']
        expected = [f'{identity}-q{n:02}' for n in range(1, 40)]
        if doc.get('question_ids') != expected or doc.get('marks') != 80 or doc.get('status') != 'ready' or doc.get('kind') != 'practice':
            raise build.Blocked(f'{identity}: expected ready original practice, ordered Q1–39 and 80 marks')
        total = competency = diagram_questions = 0
        section_counts, section_marks = Counter(), Counter()
        paper_svgs = set()
        for n, qid in enumerate(expected, 1):
            if qid not in lookup:
                raise build.Blocked(f'Missing Special39 question {qid}')
            q = lookup[qid]
            section, marks, kind = blueprint(n)
            if (q.get('number'), q.get('section'), q.get('marks'), q.get('type')) != (n, section, marks, kind):
                raise build.Blocked(f'{qid}: wrong number/section/marks/type')
            if q.get('origin') != 'original' or q.get('verified') is not True or q.get('answer_verified') is not True:
                raise build.Blocked(f'{qid}: independently reviewed original question and solution required')
            if not q.get('text') or not q.get('answer'):
                raise build.Blocked(f'{qid}: complete question and detailed solution required')
            if q.get('choice_group') or q.get('has_internal_choice') or re.search(r'(?m)^\s*(?:OR|\(OR\))\s*$', q['text']):
                raise build.Blocked(f'{qid}: no internal OR choices in Special39')
            if n <= 20 and (len(q.get('options', [])) != 4 or q.get('correct_option') not in ('A', 'B', 'C', 'D')):
                raise build.Blocked(f'{qid}: four options and exact A–D key required')
            scheme = q.get('marking_scheme')
            if not isinstance(scheme, list) or not scheme or any(
                    not isinstance(step, dict) or not step.get('step') or not numeric(step.get('marks')) or step['marks'] <= 0 for step in scheme):
                raise build.Blocked(f'{qid}: invalid detailed marking allocation')
            if not math.isclose(sum(step['marks'] for step in scheme), marks, abs_tol=1e-8):
                raise build.Blocked(f'{qid}: solution step marks do not sum to question marks')
            cm = q.get('competency_marks')
            if not numeric(cm) or not 0 <= cm <= marks or type(q.get('competency')) is not bool or q['competency'] != (cm > 0) or not q.get('competency_rationale'):
                raise build.Blocked(f'{qid}: invalid competency allocation/rationale')
            if not q.get('source_pattern_ids'):
                raise build.Blocked(f'{qid}: missing original-design source-pattern references')
            figures = build.images(q)
            if figures:
                diagram_questions += 1
                for src in figures:
                    if not src.endswith('.svg'):
                        raise build.Blocked(f'{qid}: original supplied diagrams must remain SVG vectors')
                    paper_svgs.add(src)
            total += marks
            competency += cm
            section_counts[section] += 1
            section_marks[section] += marks
            used.append(qid)
        if total != 80 or competency < 48 or diagram_questions < 5:
            raise build.Blocked(f'{identity}: needs 80 marks, >=48 competency marks, >=5 diagram-linked questions')
        report.append({'id': identity, 'questions': 39, 'marks': total, 'competency_marks': competency,
                       'competency_percent': competency / 80 * 100, 'diagram_questions': diagram_questions, 'distinct_svg_assets': len(paper_svgs),
                       'sections': dict(section_counts), 'section_marks': dict(section_marks)})
    if set(used) != set(lookup) or len(set(used)) != 156:
        raise build.Blocked('Special39 contains orphaned or reused questions')
    return report


def merge_special(base, bundle, assets):
    validate_blueprint(bundle)
    data = deepcopy(base)
    old_docs = {d['id'] for d in base['documents']}
    old_questions = {q['id'] for q in base['questions']}
    if old_docs & set(DOC_IDS) or old_questions & {q['id'] for q in bundle['questions']}:
        raise build.Blocked('Special39 IDs already exist in public baseline; refusing overwrite')
    docs, questions = build.authored(bundle, 'practice', 4, assets)
    # No inferred prediction language; add a visible series label to authored titles.
    for doc in docs:
        doc['author_title'] = doc['title']
        doc['title'] = 'Special39 / competency practice — ' + doc['title']
        doc['practice_series'] = 'special39'
        doc['subtitle'] = 'Original Class 10 Electricity • 39 questions • 80 marks • competency practice'
    sources = {s['id']: deepcopy(s) for s in data['sources']}
    for raw in bundle.get('sources', []):
        source = deepcopy(raw)
        if source.get('local_pdf'):
            source['local_pdf'] = assets.copy(source['local_pdf'])
        if source['id'] in sources and sources[source['id']] != source:
            raise build.Blocked('Special39 source ID conflicts with preserved release: ' + source['id'])
        sources[source['id']] = source
    data['documents'].extend(docs)
    data['questions'].extend(questions)
    data['sources'] = list(sources.values())
    return data, docs


def add_masters(data, stage):
    lookup = {q['id']: q for q in data['questions']}
    official = [q for q in data['questions'] if q.get('origin') == 'official']
    if any(q.get('verified') is not True for q in official):
        raise build.Blocked('Current published official bank contains unverified records')
    existing = {d['id'] for d in data['documents']}
    docs, stats = [], []
    for doc in archives.collections(official):
        if doc['collection_scope'] != 'master':
            continue
        doc['id'] = doc['collection_type'] + '-master-current'
        doc['title'] += ' — current verified release'
        doc['subtitle'] = 'Current published verified bank only; no expanded v2 audit claimed'
        doc['description'] += ' Uses only the currently published verified source bank. Downloaded/unprocessed sets are not included, and this does not claim the expanded v2 audit is complete.'
        doc['coverage_basis'] = 'current-published-verified-bank'
        if doc['id'] in existing:
            raise build.Blocked('Current-bank master ID already exists; refusing overwrite')
        volumes, results = archives.render_volumes(doc, lookup, stage)
        docs.extend(volumes)
        stats.extend(results)
    data['documents'].extend(docs)
    return docs, stats


def validate_output(data, base, stage, special_docs, master_docs, stats):
    import pymupdf
    errors = []
    for key in ('documents', 'questions', 'sources'):
        current = {item['id']: item for item in data[key]}
        if len(current) != len(data[key]): errors.append(f'Duplicate {key} IDs')
        for old in base[key]:
            if current.get(old['id']) != old: errors.append(f'Changed legacy {key}: {old["id"]}')
    for exam in ('PYQ', 'SQP'):
        expected = Counter(q['id'] for q in base['questions'] if q.get('origin') == 'official' and q.get('exam_type') == exam)
        actual = Counter(qid for d in master_docs if d['collection_type'] == exam.lower() for qid in d['question_ids'])
        if actual != expected: errors.append(f'{exam}: current-master membership mismatch')
    stats_by_pdf = {entry['pdf']: entry for entry in stats}
    for doc in special_docs:
        entry = stats_by_pdf.get(doc['pdf'], {})
        pages = entry.get('question_pages', [])
        if ([p.get('number') for p in pages] != list(range(1, 40)) or
                [p.get('question_id') for p in pages] != doc['question_ids']):
            errors.append(doc['id'] + ': incomplete question/solution navigation')
        elif any(not (p['page'] < entry['solution_start_page'] <= p['solution_page'] < entry['appendix_start_page']) for p in pages):
            errors.append(doc['id'] + ': solutions not confined to separate rear section')
    for doc in special_docs + master_docs:
        path = stage / doc['pdf']
        with pymupdf.open(path) as pdf:
            if not pdf.get_toc(): errors.append(doc['id'] + ': missing bookmarks')
            if doc.get('pdf_pages') != len(pdf) or doc.get('pdf_bytes') != path.stat().st_size:
                errors.append(doc['id'] + ': wrong measured PDF metadata')
            if doc in special_docs:
                if any(abs(p.rect.width - 595.276) > 1 or abs(p.rect.height - 841.89) > 1 for p in pdf):
                    errors.append(doc['id'] + ': non-A4 page')
                if any(p.get_images() for p in pdf): errors.append(doc['id'] + ': raster found in vector-only special paper')
                for page in pdf:
                    outer = page.rect + (-1, -1, 1, 1)
                    if any(not outer.contains(pymupdf.Rect(word[:4])) for word in page.get_text('words')):
                        errors.append(f'{doc["id"]}: text outside A4 page {page.number + 1}')
                    if any(not outer.contains(drawing['rect']) for drawing in page.get_drawings()):
                        errors.append(f'{doc["id"]}: vector outside A4 page {page.number + 1}')
                text = '\n'.join(p.get_text() for p in pdf)
                if 'Detailed solutions and marking guidance' not in text or 'Source-pattern and rationale appendix' not in text:
                    errors.append(doc['id'] + ': missing rear matter')
    for path in stage.rglob('*'):
        if path.is_file() and path.stat().st_size >= archives.MAX_BYTES:
            errors.append('File reaches 90MB ceiling: ' + str(path.relative_to(stage)))
    script = 'import fs from "node:fs"; import {validate} from ' + json.dumps((SITE / 'tools/validate.mjs').as_uri()) + '; console.log(JSON.stringify(validate(JSON.parse(fs.readFileSync(process.argv[1],"utf8")),{root:process.argv[2],final:true})));'
    result = subprocess.run(['node', '--input-type=module', '-e', script, str(stage / 'data/content.json'), str(stage)], capture_output=True, text=True, timeout=120)
    if result.returncode:
        errors.append('Site validator execution: ' + result.stderr[:1500])
    else:
        errors.extend('Site validator: ' + error for error in json.loads(result.stdout)['errors'])
    return errors


def accept_stage(work, target):
    backup = target.with_name(target.name + '-previous')
    if backup.exists(): raise build.Blocked('Staging backup exists; inspect before replacing')
    if target.exists(): target.rename(backup)
    try:
        shutil.copytree(work, target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        if backup.exists(): backup.rename(target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def run(args):
    bundle = None
    audit = structural = None
    input_hashes = {}
    if not args.masters_only:
        bundle, audit, structural, input_hashes = load_author()
        blueprint_report = validate_blueprint(bundle)
    else:
        blueprint_report = []
    base = json.loads((SITE / 'data/content.json').read_text())
    with tempfile.TemporaryDirectory(prefix='special39-build-', dir=ASSEMBLY) as tmp:
        work = Path(tmp)
        stage = work / 'site'
        legacy_hashes = archives.snapshot_public(stage)
        assets = SpecialAssets(stage)
        data, special_docs = (deepcopy(base), []) if bundle is None else merge_special(base, bundle, assets)
        special_stats = []
        lookup = {q['id']: q for q in data['questions']}
        for doc in special_docs:
            render_doc = deepcopy(doc)
            refs = {ref for qid in doc['question_ids'] for ref in lookup[qid]['source_pattern_ids']}
            render_doc['sources'] = [source for source in data['sources'] if source['id'] in refs]
            special_stats.append(render_special39(render_doc, lookup, stage))
            for key in ('pdf', 'pdf_pages', 'pdf_bytes'): doc[key] = render_doc[key]
        master_docs, master_stats = add_masters(data, stage)
        data['meta']['updated'] = date.today().isoformat()
        data['coverage']['limitations'].append('Separate PYQ/SQP master PDFs use only the current published verified bank; no expanded audit or exhaustive all-set coverage is claimed. Special39, when present, is additional original competency practice, not official questions or a prediction.')
        build.write_json(stage / 'data/content.json', data)
        errors = validate_output(data, base, stage, special_docs, master_docs, special_stats)
        for relative, sha in legacy_hashes.items():
            if build.digest(SITE / relative) != sha: errors.append('Public baseline changed: ' + relative)
            if relative != 'data/content.json' and build.digest(stage / relative) != sha:
                errors.append('Staged legacy asset changed: ' + relative)
        for relative, sha in input_hashes.items():
            if build.digest(ROOT / relative) != sha: errors.append('Author input changed during render: ' + relative)
        for relative, info in assets.manifest.items():
            if build.digest(ROOT / info['source']) != info['sha256'] or build.digest(stage / relative) != info['sha256']:
                errors.append('Author asset changed during render: ' + relative)
        if errors: raise build.Blocked('; '.join(errors))
        target = ASSEMBLY / ('staging-current-masters' if args.masters_only else 'staging-special39')
        report = {'stage': 'validated-staging-only', 'published': False, 'mode': 'masters-only' if args.masters_only else 'special39-and-current-masters',
                  'stage_root': str(target / 'site'), 'documents': len(data['documents']), 'questions': len(data['questions']),
                  'special_documents': len(special_docs), 'master_documents': len(master_docs), 'special_blueprints': blueprint_report,
                  'new_documents': special_docs + master_docs, 'special_render_stats': special_stats, 'master_render_stats': master_stats,
                  'legacy_sha256': legacy_hashes, 'input_sha256': input_hashes, 'assets': assets.manifest,
                  'author_structural_validation': structural, 'author_audit': audit, 'errors': [],
                  'limitations': ['Assembly validates structure/mark arithmetic/layout, not physics truth or semantic competency merit.',
                                 'Current masters add no expanded source audit; existing gaps and answer holds retained.',
                                 'Public site unchanged; parent owns full visual review and publication.']}
        build.write_json(work / 'validation.json', report)
        accept_stage(work, target)
        summary = {k: report[k] for k in ('stage', 'published', 'mode', 'stage_root', 'documents', 'questions', 'special_documents', 'master_documents', 'errors')}
        build.write_json(ASSEMBLY / ('current-masters-status.json' if args.masters_only else 'special39-status.json'), summary)
        print(json.dumps(summary, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--masters-only', action='store_true', help='Stage two current-bank masters without reading unfinished author/research inputs')
    args = parser.parse_args()
    try:
        return run(args)
    except (build.Blocked, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
        status = {'stage': 'blocked', 'published': False, 'errors': [str(exc)]}
        build.write_json(ASSEMBLY / ('current-masters-status.json' if args.masters_only else 'special39-status.json'), status)
        print(json.dumps(status, indent=2))
        return 2


if __name__ == '__main__':
    sys.exit(main())
