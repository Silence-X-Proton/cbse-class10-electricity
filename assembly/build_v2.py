#!/opt/venv/bin/python
"""Stage additive v2 archives; never writes to the public site or polls research."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import build
from pdf_v2 import render_collection

ROOT, ASSEMBLY, SITE = build.ROOT, build.ASSEMBLY, build.SITE
MAX_BYTES = 90_000_000
FILES = ('question_bank.json', 'publication_metadata.json', 'ledger.json',
         'quarantine.json', 'coverage.json', 'validation.json')


def load_handoff(root=ROOT):
    directory = root / 'research/pyq_v2'
    loaded, blockers = {}, []
    marker = directory / 'READY.md'
    if not marker.is_file() or marker.read_text().splitlines()[:1] != ['# READY']:
        blockers.append('research/pyq_v2/READY.md must start with # READY; year fragments are not final input')
    for name in FILES:
        path = directory / name
        if not path.is_file():
            blockers.append(f'Missing final v2 input: {name}')
            continue
        try:
            loaded[name] = json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            blockers.append(f'{name}: {exc}')
    bank = loaded.get('question_bank.json', {})
    if isinstance(bank, dict) and bank.get('status') not in ('ready', 'complete', 'final'):
        blockers.append('v2 bank explicit ready status required')
    validation = loaded.get('validation.json', {})
    if not isinstance(validation, dict) or validation.get('errors') or not (
            validation.get('status') in ('ready', 'complete', 'final') or
            validation.get('valid') is True or validation.get('passed') is True):
        blockers.append('Research validation has not passed')
    return loaded, blockers


def natural(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r'(\d+)', str(value or '')) if part)


def order(q):
    return tuple(natural(q.get(k)) for k in ('year', 'session', 'paper_code',
                 'source_id', 'source_title', 'question_number', 'alternative_label', 'id'))


def slug(value):
    result = re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')
    if not result:
        raise build.Blocked('Collection year/session cannot become an empty slug')
    return result


def collections(questions):
    """No cap, fingerprint deduplication, branch dropping, or additive marks."""
    result = []
    for exam in ('PYQ', 'SQP'):
        items = sorted((q for q in questions if q.get('origin') == 'official' and q.get('exam_type') == exam), key=order)
        if not items:
            raise build.Blocked(f'No verified {exam} records for master archive')
        grouped = defaultdict(list)
        for q in items:
            key = str(q['year'] if exam == 'PYQ' else q['session'])
            grouped[key].append(q)
        groups = [(f'{exam.lower()}-master', None, items)]
        groups += [(f'{exam.lower()}-year-{slug(year)}', year, qs) for year, qs in sorted(grouped.items(), key=lambda x: natural(x[0]))]
        for identity, year, qs in groups:
            title = f'{exam} Electricity — ' + ('master question bank' if year is None else year + ' collection')
            doc = {'id': identity, 'kind': 'official', 'status': 'ready', 'title': title,
                   'collection_type': exam.lower(), 'collection_scope': 'master' if year is None else 'year',
                   'question_ids': [q['id'] for q in qs], 'sections': [],
                   'description': f'{len(qs)} verified source occurrences in year/set/source-number order. '
                   'Distinct sets and resolved alternatives are retained independently; marks are nonadditive. '
                   'This editorial archive is not a CBSE-produced chapter paper or an exhaustive all-set claim.'}
            if year is not None:
                doc['year'] = year
            result.append(doc)
    if len({d['id'] for d in result}) != len(result):
        raise build.Blocked('Year/session labels collide after slug normalization')
    return result


def render_volumes(doc, lookup, stage, *, max_bytes=MAX_BYTES, max_pages=750, renderer=render_collection):
    """Split only on measured PDF size/page count; preserve contiguous membership."""
    if not 0 < max_bytes <= MAX_BYTES or max_pages < 1:
        raise build.Blocked('Invalid volume limits')
    chunks = [doc['question_ids']]
    while True:
        rendered, stats, retry = [], [], False
        next_chunks = []
        for number, ids in enumerate(chunks, 1):
            volume = deepcopy(doc)
            volume['question_ids'] = ids
            if len(chunks) > 1:
                volume.update(id=f'{doc["id"]}-vol-{number:02}', collection_id=doc['id'],
                              volume_number=number, volume_count=len(chunks),
                              title=f'{doc["title"]} — Volume {number} of {len(chunks)}')
            stat = renderer(volume, lookup, stage)
            path = stage / volume['pdf']
            import pymupdf
            with pymupdf.open(path) as pdf:
                pages = pdf.page_count
            size = path.stat().st_size
            volume.update(pdf_pages=pages, pdf_bytes=size)
            if size >= max_bytes or pages > max_pages:
                path.unlink()
                if len(ids) < 2:
                    raise build.Blocked(f'{doc["id"]}: single record cannot meet PDF byte/page ceiling; never downsampled')
                midpoint = len(ids) // 2
                next_chunks.extend((ids[:midpoint], ids[midpoint:]))
                retry = True
            else:
                next_chunks.append(ids)
                rendered.append(volume)
                stats.append(stat)
        if not retry:
            return rendered, stats
        for volume in rendered:
            (stage / volume['pdf']).unlink()
        chunks = next_chunks


def snapshot_public(stage):
    """Copy legacy asset bytes; hashes checked again before staged acceptance."""
    hashes = {}
    for folder in ('data', 'downloads', 'assets/research'):
        source = SITE / folder
        shutil.copytree(source, stage / folder)
        for path in source.rglob('*'):
            if path.is_file():
                relative = path.relative_to(SITE).as_posix()
                hashes[relative] = build.digest(path)
                if build.digest(stage / relative) != hashes[relative]:
                    raise build.Blocked(f'Legacy copy mismatch: {relative}')
    return hashes


def source_index(q, sources):
    supplied = q.get('source_id')
    if not supplied:
        identity = '|'.join(str(q.get(k) or '') for k in ('source_url', 'paper_code', 'source_title', 'year', 'session', 'pdf_file'))
        q['source_id'] = 'assembly-src-' + hashlib.sha256(identity.encode()).hexdigest()[:20]
    sid = q['source_id']
    entry = {'id': sid, 'title': q['source_title'], 'year': q['year'], 'session': q['session'],
             'exam_type': q['exam_type'], 'url': q['source_url'], 'local_pdf': q.get('pdf_file'),
             'marking_scheme_url': q.get('marking_scheme_url')}
    if not supplied:
        entry['notes'] = 'Assembly-generated index ID; not a printed official identifier.'
    if sid in sources:
        for key in ('title', 'year', 'session', 'exam_type', 'url', 'local_pdf'):
            if str(sources[sid].get(key) or '') != str(entry.get(key) or ''):
                raise build.Blocked(f'Conflicting source_id {sid}: {key}')
    else:
        sources[sid] = entry


def merge_records(base, bank, metadata, quarantine, assets):
    data = deepcopy(base)
    lookup = {q['id']: q for q in data['questions']}
    sources = {s['id']: s for s in data['sources']}
    if len(lookup) != len(data['questions']) or len(sources) != len(data['sources']):
        raise build.Blocked('Duplicate IDs in legacy release')
    held = deepcopy(quarantine)
    held_ids = {q.get('id') or q.get('question_id') for q in held}
    conflict = set(lookup) & held_ids
    if conflict:
        raise build.Blocked('New quarantine conflicts with preserved v1 IDs: ' + ', '.join(sorted(conflict)))
    seen = set()
    for raw in build.apply_publication_metadata(bank, metadata, validate_legacy_base=False):
        qid = raw.get('id')
        if not isinstance(qid, str) or not qid or qid in seen:
            raise build.Blocked(f'Missing/duplicate v2 question ID: {qid}')
        seen.add(qid)
        issues = build.eligible(raw, for_paper=False)
        if raw.get('verified') is not True:
            issues.append('Source question is not verified')
        if raw.get('exam_type') != 'PYQ':
            issues.append('v2 PYQ handoff record exam_type must be PYQ')
        if not raw.get('year'):
            issues.append('Missing exact year; not inferred from session')
        if qid in held_ids:
            issues.append('Explicit research quarantine')
        if issues:
            if qid in lookup:
                raise build.Blocked(f'{qid}: new audit invalidates a preserved v1 record: {issues}')
            held.append({'id': qid, 'exam_type': raw.get('exam_type'), 'year': raw.get('year'), 'reasons': issues})
            continue
        q = build.normalize_question(raw, 'official', assets)
        if qid in lookup:
            old = lookup[qid]
            # Compare every supplied normalized field except additive processing metadata.
            ignored = {'publication_metadata', 'metadata_review', 'compilation_section', 'assembly_source_slot',
                       'compilation_reuse', 'bank_only', 'notes', 'solution_status'}
            differences = [k for k, v in q.items() if k not in ignored and old.get(k) != v]
            if differences:
                raise build.Blocked(f'Preserved v1 ID {qid} differs in {differences}; provide a distinct v2 ID')
            continue
        source_index(q, sources)
        lookup[qid] = q
        data['questions'].append(q)
    data['sources'] = list(sources.values())
    return data, held


def compact_ledger(rows):
    result, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise build.Blocked('Ledger rows must be objects')
        identity = row.get('id') or row.get('source_id')
        if not identity or identity in ids or not row.get('status') or row.get('year') is None:
            raise build.Blocked('Ledger needs unique id, exact year and explicit status per row')
        ids.add(identity)
        compact = {k: deepcopy(row[k]) for k in ('id', 'exam_type', 'year', 'session', 'set', 'note',
                   'source_url', 'reviewed', 'exhaustive', 'published_questions', 'verified_questions', 'held_questions') if k in row}
        compact.update(id=identity, status=row['status'])
        compact.setdefault('exam_type', 'PYQ')
        result.append(compact)
    return result


def validate_stage(data, base, stage, docs, max_bytes=MAX_BYTES):
    problems = []
    import pymupdf
    lookup = {q['id']: q for q in data['questions']}
    if len(lookup) != len(data['questions']):
        problems.append('Duplicate question IDs')
    published = {d['id']: d for d in data['documents']}
    for old in base['documents']:
        new = published.get(old['id'], {})
        if any(new.get(k) != v for k, v in old.items()):
            problems.append('Legacy document changed: ' + old['id'])
    for old in base['questions']:
        if lookup.get(old['id']) != old:
            problems.append('Legacy question changed: ' + old['id'])
    for doc in docs:
        expected = doc['collection_type'].upper()
        if doc.get('marks') is not None or doc.get('duration_minutes') is not None:
            problems.append(doc['id'] + ': archive marks/duration must be nonadditive')
        items = [lookup[qid] for qid in doc['question_ids']]
        if not items or any(q.get('exam_type') != expected or q.get('verified') is not True for q in items):
            problems.append(doc['id'] + ': impure/unverified/empty collection')
        if items != sorted(items, key=order):
            problems.append(doc['id'] + ': wrong source order')
        with pymupdf.open(stage / doc['pdf']) as pdf:
            if not pdf.get_toc() or not any(p.get_links() for p in pdf):
                problems.append(doc['id'] + ': missing PDF navigation')
    for exam in ('PYQ', 'SQP'):
        expected = Counter(q['id'] for q in data['questions'] if q.get('origin') == 'official' and q.get('exam_type') == exam)
        for scope in ('master', 'year'):
            actual = Counter(qid for d in docs if d['collection_type'] == exam.lower() and d['collection_scope'] == scope for qid in d['question_ids'])
            if expected != actual:
                problems.append(f'{exam} {scope}: missing or duplicate bank membership')
    for path in stage.rglob('*'):
        if path.is_file() and path.stat().st_size >= max_bytes:
            problems.append('File exceeds GitHub size ceiling: ' + str(path.relative_to(stage)))
    validator = SITE / 'tools/validate.mjs'
    script = "import fs from 'node:fs'; import {validate} from " + json.dumps(validator.as_uri()) + "; console.log(JSON.stringify(validate(JSON.parse(fs.readFileSync(process.argv[1])), {root:process.argv[2],final:true})));"
    checked = subprocess.run(['node', '--input-type=module', '-e', script, str(stage / 'data/content.json'), str(stage)], capture_output=True, text=True, timeout=120)
    if checked.returncode:
        problems.append('Site validator failed: ' + checked.stderr[:1500])
    else:
        problems.extend('Site validator: ' + error for error in json.loads(checked.stdout)['errors'])
    return problems


def run(args):
    inputs, blockers = load_handoff(ROOT)
    if blockers:
        raise build.Blocked('; '.join(blockers))
    paths = [ROOT / 'research/pyq_v2' / f for f in (*FILES, 'READY.md')]
    hashes = {str(p.relative_to(ROOT)): build.digest(p) for p in paths}
    base = json.loads((SITE / 'data/content.json').read_text())
    with tempfile.TemporaryDirectory(prefix='v2-build-', dir=ASSEMBLY) as tmp:
        work = Path(tmp)
        stage = work / 'site'
        legacy_hashes = snapshot_public(stage)
        assets = build.Assets(stage)
        bank = build.records(inputs['question_bank.json'], ('questions',))
        held = build.records(inputs['quarantine.json'], ('records', 'questions'))
        ledger = build.records(inputs['ledger.json'], ('rows', 'sources', 'ledger'))
        data, held = merge_records(base, bank, inputs['publication_metadata.json'], held, assets)
        # Existing original/notes documents and PDFs remain byte-for-byte unchanged.
        for doc in data['documents']:
            if doc['kind'] == 'official':
                doc.setdefault('collection_type', 'mixed')
                doc.setdefault('collection_scope', 'compilation')
        docs, render_stats = [], []
        for collection in collections(data['questions']):
            volumes, stats = render_volumes(collection, {q['id']: q for q in data['questions']}, stage, max_pages=args.max_pages)
            docs.extend(volumes)
            render_stats.extend(stats)
        data['documents'].extend(docs)
        data['meta']['updated'] = date.today().isoformat()
        data['coverage']['source_ledger'] = compact_ledger(ledger)
        data['coverage']['source_inventory']['pyq_v2'] = build.sanitize_coverage(inputs['coverage.json'])
        data['coverage']['limitations'].append(f'V2 retains all eligible verified records and independent alternatives in pure PYQ/SQP archives; {len(held)} quarantine entries remain outside the verified bank. Counts are source occurrences, not additive marks. Existing v1 limitations above describe its legacy selection; the v2 ledger records expanded review.')
        data['coverage']['v2_quarantine'] = build.sanitize_coverage([
            {k: row[k] for k in ('id', 'question_id', 'year', 'exam_type', 'status', 'reasons', 'reason') if k in row}
            for row in held])
        build.write_json(stage / 'data/content.json', data)
        blockers = validate_stage(data, base, stage, docs)
        for relative, sha in legacy_hashes.items():
            if build.digest(SITE / relative) != sha:
                blockers.append('Public v1 changed during staging: ' + relative)
            if relative != 'data/content.json' and build.digest(stage / relative) != sha:
                blockers.append('Preserved v1 asset changed in stage: ' + relative)
        for relative, sha in hashes.items():
            if build.digest(ROOT / relative) != sha:
                blockers.append('Research input changed during staging: ' + relative)
        if blockers:
            raise build.Blocked('; '.join(blockers))
        report = {'stage': 'validated-staging-only', 'published': False, 'blockers': [],
                  'documents': len(data['documents']), 'questions': len(data['questions']),
                  'new_documents': len(docs), 'quarantine_entries': len(held),
                  'input_sha256': hashes, 'legacy_sha256': legacy_hashes,
                  'assets': assets.manifest, 'render_stats': render_stats, 'research_ledger': ledger}
        build.write_json(work / 'validation.json', report)
        target = ASSEMBLY / 'staging-v2'
        backup = ASSEMBLY / 'staging-v2-previous'
        if backup.exists():
            raise build.Blocked('Previous staging backup exists; inspect before replacing')
        if target.exists():
            target.rename(backup)
        try:
            shutil.copytree(work, target)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            if backup.exists():
                backup.rename(target)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        build.write_json(ASSEMBLY / 'v2-status.json', {k: report[k] for k in ('stage', 'published', 'blockers', 'documents', 'questions', 'new_documents', 'quarantine_entries')})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-pages', type=int, default=750, help='Measured per-volume page ceiling; default 750')
    args = parser.parse_args()
    try:
        return run(args)
    except (build.Blocked, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
        status = {'stage': 'blocked', 'published': False, 'blockers': [str(exc)]}
        build.write_json(ASSEMBLY / 'v2-status.json', status)
        print(json.dumps(status, indent=2))
        return 2


if __name__ == '__main__':
    sys.exit(main())
