import test from 'node:test';
import fs from 'node:fs';
import * as utils from '../content-utils.mjs';
import assert from 'node:assert/strict';
import { safeURL, images, questionImages, answerImages, matchesQuestion, checkShape } from '../content-utils.mjs';
import { validate } from '../tools/validate.mjs';
const shell = () => ({ schema_version: 1, meta: { chapter: 'Electricity' }, coverage: {}, documents: [], questions: [], sources: [] });
const original = () => ({ id: 'test-original', origin: 'original', text: 'TEST FIXTURE ONLY: resistance numerical', topic: 'Resistance', marks: 2, type: 'numerical', verified: true });
test('site-relative and HTTPS links survive Pages subpaths', () => {
  assert.equal(safeURL('assets/research/page.png'), 'assets/research/page.png');
  assert.equal(new URL(safeURL('downloads/paper.pdf'), 'https://example.org/project/').pathname, '/project/downloads/paper.pdf');
  assert.equal(safeURL('https://cbseacademic.nic.in/source.pdf'), 'https://cbseacademic.nic.in/source.pdf');
});
test('reject unsafe schemes, traversal, encoded traversal and host paths', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,hello', '//evil.test', '/a0/test.png', '../test.png', 'assets/../test.png', 'assets/%2e%2e/test.png', '%2Fetc/passwd', 'a\\b.png', 'https://user:pass@example.org/x', ' file.pdf', 'https://', 'asset%ZZ']) assert.equal(safeURL(value), null, value);
});
test('ordered scalar and array image normalization preserves evidence without duplicates', () => {
  assert.deepEqual(images('a.png', ['b.png', 'a.png'], null, { src: 'c.png', alt: 'page 3' }), [{ src: 'a.png', alt: '' }, { src: 'b.png', alt: '' }, { src: 'c.png', alt: 'page 3' }]);
  assert.equal(questionImages({ evidence_image: ['a.png', 'b.png'], diagram_image: 'b.png' }).length, 2);
  assert.equal(answerImages({ answer_evidence_image: ['x.png', 'y.png'] }).length, 2);
});
test('search combines tokens and topic/origin/marks filters', () => {
  const q = { ...original(), session: 'TEST SESSION', question_number: '9' };
  assert.ok(matchesQuestion(q, { search: 'RESISTANCE test', topic: 'Resistance', origin: 'original', marks: '2' }));
  assert.ok(matchesQuestion(q, { search: '9' }));
  assert.ok(!matchesQuestion(q, { origin: 'official' }));
  assert.ok(!matchesQuestion(q, { marks: '3' }));
  assert.ok(!matchesQuestion(q, { search: 'absent-token' }));
});
test('pending empty shell passes assembly and fails final readiness', () => {
  assert.equal(validate(shell()).errors.length, 0);
  assert.ok(validate(shell(), { final: true }).errors.some(e => e.includes('15 official')));
});
test('duplicate IDs, bad schema and missing references fail', () => {
  assert.throws(() => checkShape({ ...shell(), schema_version: 3 }), /schema/);
  assert.throws(() => checkShape({ ...shell(), questions: [original(), original()] }), /duplicate/);
  assert.throws(() => checkShape({ ...shell(), documents: [{ id: 'x', kind: 'practice', status: 'draft', question_ids: ['absent'] }] }), /Missing question/);
});
test('ready cannot mean empty; original questions cannot be labelled official', () => {
  let data = shell(); data.documents = [{ id: 'empty', title: 'Empty', kind: 'notes', status: 'ready', question_ids: [] }];
  assert.ok(validate(data).errors.some(e => e.includes('ready document is empty')));
  data = shell(); data.questions = [original()]; data.documents = [{ id: 'wrong', title: 'TEST invalid origin', kind: 'official', status: 'ready', question_ids: ['test-original'] }];
  assert.ok(validate(data).errors.some(e => e.includes('cannot be labelled official')));
});
test('official provenance, verified flags and evidence cannot be inferred', () => {
  const data = shell(); data.questions = [{ ...original(), origin: 'official', verified: false }];
  const result = validate(data, { final: true });
  assert.ok(result.errors.some(e => e.includes('missing exact provenance')));
  assert.ok(result.errors.some(e => e.includes('not verified')));
  assert.ok(result.errors.some(e => e.includes('evidence image required')));
});
test('missing PDF paths fail assembly', () => {
  const data = shell(); data.documents = [{ id: 'draft', title: 'TEST draft', kind: 'notes', status: 'draft', question_ids: [], pdf: 'downloads/nonexistent-test.pdf' }];
  assert.ok(validate(data).errors.some(e => e.includes('local asset missing')));
});

// Clone the published inventory: regressions never modify live JSON or assets.
const live = JSON.parse(fs.readFileSync(new URL('../data/content.json', import.meta.url), 'utf8'));
const liveCopy = () => structuredClone(live);
const officialQuestion = (data, type = 'PYQ') => data.questions.find(q => q.origin === 'official' && q.exam_type === type);
function addCollection(data, type = 'PYQ') {
  const q = officialQuestion(data, type);
  const doc = { id: 'regression-' + type.toLowerCase(), kind: 'official', status: 'ready', title: q.source_title,
    collection_type: type.toLowerCase(), collection_scope: 'year', year: q.year, question_ids: [q.id] };
  data.documents.push(doc);
  return doc;
}
function ledgerRow(data) {
  const q = officialQuestion(data);
  return { id: q.source_id, exam_type: q.exam_type, year: q.year, session: q.session,
    status: 'Not exhaustively reviewed', source_url: q.source_url, reviewed: false, exhaustive: false,
    published_questions: 0, verified_questions: 0, held_questions: 0 };
}
const finalErrors = data => validate(data, { final: true, checkFiles: false }).errors;
test('live inventory passes final validation without changing its audit or answer holds', () => {
  const data = liveCopy();
  assert.deepEqual(validate(data, { final: true }).errors, []);
  assert.deepEqual(data, live);
});
test('authoritative exam/year/session/paper filters combine and search identifiers', () => {
  const q = officialQuestion(live);
  for (const key of ['id', 'source_id', 'exam_type']) assert.ok(matchesQuestion(q, { search: q[key] }), key);
  assert.ok(matchesQuestion(q, { exam_type: q.exam_type, year: String(q.year), session: q.session, paper_code: q.paper_code || q.set || '' }));
  assert.ok(!matchesQuestion(q, { exam_type: 'SQP' }));
  for (const key of ['year', 'session', 'paper_code']) assert.ok(!matchesQuestion(q, { [key]: 'not-recorded' }), key);
  const sqp = officialQuestion(live, 'SQP');
  assert.ok(matchesQuestion(sqp, { year: String(sqp.session) }));
  assert.ok(!matchesQuestion(sqp, { year: String(sqp.session).slice(0, 3) }));
  const separateSession = { ...q, year: 2025, session: '2025-26' };
  assert.ok(matchesQuestion(separateSession, { year: '2025-26' }));
  assert.ok(matchesQuestion(separateSession, { year: '2025' }));
  assert.ok(!matchesQuestion(separateSession, { session: '2025' }));
  const setOnly = { ...q, paper_code: '', set: q.paper_code || q.set || q.id };
  assert.ok(matchesQuestion(setOnly, { paper_code: setOnly.set, search: setOnly.set }));
  assert.ok(!matchesQuestion({ ...setOnly, paper_code: 'authoritative-code' }, { paper_code: setOnly.set }));
  const missing = { ...q }; for (const key of ['year', 'session', 'exam_type', 'paper_code', 'set']) delete missing[key];
  assert.ok(!matchesQuestion(missing, { year: String(q.year) }));
  assert.ok(!matchesQuestion(missing, { exam_type: q.exam_type }));
});
test('collection classification derives from every reference and never guesses missing provenance', () => {
  assert.equal(typeof utils.documentCollectionType, 'function');
  const pyq = officialQuestion(live), sqp = officialQuestion(live, 'SQP');
  const map = new Map(live.questions.map(q => [q.id, q]));
  const doc = ids => ({ kind: 'official', question_ids: ids });
  assert.equal(utils.documentCollectionType(doc([pyq.id]), map), 'pyq');
  assert.equal(utils.documentCollectionType(doc([sqp.id]), map), 'sqp');
  assert.equal(utils.documentCollectionType(doc([pyq.id, sqp.id]), map), 'mixed');
  for (const ids of [[], ['absent'], [pyq.id, 'absent'], [pyq.id, sqp.id, 'absent']]) assert.equal(utils.documentCollectionType(doc(ids), map), 'unknown');
  for (const altered of [{ ...sqp, exam_type: undefined }, { ...sqp, origin: 'original' }]) {
    const changed = new Map(map); changed.set(sqp.id, altered);
    assert.equal(utils.documentCollectionType(doc([pyq.id, sqp.id]), changed), 'unknown');
  }
  assert.equal(utils.documentCollectionType({ ...doc([pyq.id]), kind: 'practice' }, map), 'unknown');
  assert.equal(utils.documentCollectionType({ ...doc([]), collection_type: 'mixed' }, map), 'mixed');
});
test('final inventory accepts additions of every kind and valid optional metadata', () => {
  const data = liveCopy();
  const doc = addCollection(data); doc.pdf_pages = 1; doc.pdf_bytes = 100;
  const sqp = addCollection(data, 'SQP'); sqp.year = officialQuestion(data, 'SQP').session;
  for (const kind of ['practice', 'notes']) data.documents.push({ ...structuredClone(data.documents.find(d => d.kind === kind)), id: 'regression-' + kind });
  data.coverage.source_ledger = [ledgerRow(data)];
  assert.deepEqual(finalErrors(data), []);
  delete doc.year; doc.collection_scope = 'master';
  assert.deepEqual(finalErrors(data), []);
  for (const kind of ['official', 'practice', 'notes']) {
    const tooFew = liveCopy(); tooFew.documents = tooFew.documents.filter(d => d.kind !== kind);
    assert.ok(finalErrors(tooFew).some(e => e.includes(kind)));
  }
  doc.status = 'draft';
  assert.ok(finalErrors(data).some(e => e.includes(doc.id) && e.includes('ready')));
});
test('collection metadata rejects invalid types, provenance, year mismatch and mixed purity', () => {
  for (const [key, values] of Object.entries({ collection_type: [null, '', 'PYQ', 'other', 1], collection_scope: [null, '', 'other', 1], year: [null, '', ' ', {}, [], true, Infinity], pdf_pages: [null, 0, -1, 1.5, '2'], pdf_bytes: [null, 0, -1, 1.5, '2'] })) {
    for (const value of values) {
      const data = liveCopy(), doc = addCollection(data); doc[key] = value;
      assert.ok(finalErrors(data).some(e => e.includes(key)), key + ': ' + value);
    }
  }
  for (const key of ['collection_type', 'collection_scope']) {
    const data = liveCopy(), doc = data.documents.find(d => d.kind === 'practice');
    doc[key] = key === 'collection_type' ? 'pyq' : 'master';
    assert.ok(finalErrors(data).some(e => e.includes(key) && e.includes('official')));
  }
  const data = liveCopy(), doc = addCollection(data);
  delete doc.year;
  assert.ok(finalErrors(data).some(e => e.includes('year')));
  doc.year = 'not-a-source-year';
  assert.ok(finalErrors(data).some(e => e.includes('year')));
  doc.year = officialQuestion(data).year; doc.collection_scope = 'master';
  assert.ok(finalErrors(data).some(e => e.includes('year')));
  delete doc.year;
  doc.question_ids.push(officialQuestion(data, 'SQP').id);
  assert.ok(finalErrors(data).some(e => e.includes('collection_type')));
  doc.collection_type = 'mixed';
  assert.deepEqual(finalErrors(data), []);
  delete officialQuestion(data, 'SQP').exam_type;
  assert.ok(validate(data, { checkFiles: false }).errors.some(e => e.includes('collection_type')));
});
test('coverage ledger preserves false/zero and rejects malformed rows and optional fields', () => {
  const data = liveCopy(); data.coverage.source_ledger = [ledgerRow(data)];
  assert.deepEqual(finalErrors(data), []);
  for (const ledger of [null, {}, 'invalid', [null], [[]], [1], [ledgerRow(data), ledgerRow(data)]]) {
    const changed = liveCopy(); changed.coverage.source_ledger = ledger;
    assert.ok(finalErrors(changed).some(e => e.includes('source_ledger')));
  }
  const bad = { id: ['', ' ', null, 1], exam_type: ['', 'pyq', null], year: ['', ' ', null, {}, true, Infinity], status: ['', ' ', null, {}], session: [null, 1], set: [null, {}], note: [null, []], source_url: ['', null, 'javascript:alert(1)', '../private.pdf'], reviewed: [null, 0, 'false'], exhaustive: [null, 1, 'true'], published_questions: [null, -1, 0.5, '0'], verified_questions: [null, -1, '0'], held_questions: [null, -1, false] };
  for (const [key, values] of Object.entries(bad)) for (const value of values) {
    const changed = liveCopy(); changed.coverage.source_ledger = [{ ...ledgerRow(changed), [key]: value }];
    assert.ok(finalErrors(changed).some(e => e.includes('source_ledger') && e.includes(key)), key + ': ' + value);
  }
  for (const key of ['id', 'exam_type', 'year', 'status']) {
    const changed = liveCopy(), row = ledgerRow(changed); delete row[key]; changed.coverage.source_ledger = [row];
    assert.ok(finalErrors(changed).some(e => e.includes(key)));
  }
});
test('additional official documents retain reference, asset, provenance, evidence and answer checks', () => {
  const data = liveCopy(), doc = addCollection(data);
  const source = officialQuestion(data);
  const q = { ...structuredClone(source), id: source.id + '-regression' };
  data.questions.push(q); doc.question_ids = [q.id];
  assert.deepEqual(finalErrors(data), []);
  for (const [field, value, message] of [
    ['verified', false, 'not verified'], ['original_section', null, 'missing exact provenance'],
    ['source_id', 'absent', 'unresolved source_id'], ['pages', [0], 'one-based PDF pages'],
    ['answer', 'Unverified answer must remain on hold', 'official answer not verified']
  ]) {
    const changed = structuredClone(data), added = changed.questions.at(-1); added[field] = value;
    if (field === 'answer') added.answer_verified = false;
    assert.ok(finalErrors(changed).some(e => e.includes(q.id) && e.includes(message)), field);
  }
  const noEvidence = structuredClone(data), added = noEvidence.questions.at(-1);
  for (const key of ['evidence_image', 'evidence_images', 'diagram_image']) delete added[key];
  assert.ok(finalErrors(noEvidence).some(e => e.includes(q.id) && e.includes('official evidence image required')));
  doc.pdf = 'downloads/nonexistent-regression.pdf';
  assert.ok(validate(data, { final: true }).errors.some(e => e.includes(doc.id) && e.includes('local asset missing')));
  doc.question_ids = ['absent'];
  assert.ok(finalErrors(data).some(e => e.includes('Missing question reference')));
});

test('Special39 grouping is practice-only and supports additive metadata, titles and all four stable IDs', () => {
  for (const id of ['special-39-01', 'special-39-02', 'special-39-03', 'special-39-04']) assert.equal(utils.isSpecial39({kind:'practice', id}), true);
  assert.equal(utils.isSpecial39({kind:'practice', practice_series:'special39'}), true);
  assert.equal(utils.isSpecial39({kind:'practice', title:'Special39 / competency practice — Original title'}), true);
  assert.equal(utils.isSpecial39({kind:'practice', title:'special 39 question originals'}), true);
  for (const doc of [{kind:'official', id:'special-39-01'}, {kind:'notes', practice_series:'special39'}, {kind:'practice', id:'original-practice-01'}, {kind:'practice', title:'Special390'}, {kind:'practice', id:'special-39-05'}]) assert.equal(utils.isSpecial39(doc), false);
});
