import test from 'node:test';
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
