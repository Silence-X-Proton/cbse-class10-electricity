import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TARGETS, array, safeURL, questionImages, answerImages, images, checkShape } from '../content-utils.mjs';
const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export function validate(data, { final = false, root = site, checkFiles = true } = {}) {
  const errors = [], warnings = [];
  const error = message => errors.push(message);
  const need = (value, message) => { if (!value) error(message); };
  const present = value => value !== null && value !== undefined && String(value).trim() !== '';
  const positive = value => typeof value === 'number' && Number.isFinite(value) && value > 0;
  try { checkShape(data); } catch (e) { return { errors: [e.message], warnings }; }
  const urls = [];
  function checkLink(value, context, { local = false } = {}) {
    if (!value) return;
    const url = safeURL(value);
    if (!url) { error(`${context}: unsafe or invalid URL: ${value}`); return; }
    const remote = /^https?:\/\//i.test(url);
    if (local && remote) error(`${context}: expected a site-relative local asset`);
    if (remote) return;
    urls.push(value);
    if (checkFiles) {
      const resolved = path.resolve(root, decodeURIComponent(value.split(/[?#]/)[0]));
      try {
        const real = fs.realpathSync(resolved);
        need(real.startsWith(fs.realpathSync(root) + path.sep), `${context}: asset escapes site root`);
        need(fs.statSync(real).isFile(), `${context}: asset is not a file`);
        need(fs.statSync(real).size > 0, `${context}: asset is empty`);
      } catch { error(`${context}: local asset missing: ${value}`); }
    }
  }
  need(data.meta?.chapter === 'Electricity', 'meta.chapter must be Electricity for this edition');
  const sourceIds = new Set(data.sources.map(s => s.id));
  const questions = new Map(data.questions.map(q => [q.id, q]));
  for (const q of data.questions) {
    const label = `Question ${q.id}`;
    need(['official', 'original'].includes(q.origin), `${label}: origin must be official or original`);
    need(typeof q.text === 'string', `${label}: text must be a string`);
    need(typeof q.topic === 'string' && !!q.topic, `${label}: topic is required`);
    need(typeof q.type === 'string' && !!q.type, `${label}: type is required`);
    need(q.marks === null || positive(q.marks), `${label}: marks must be positive or null`);
    need(typeof q.verified === 'boolean', `${label}: verified must be boolean`);
    if (q.answer_verified != null) need(typeof q.answer_verified === 'boolean', `${label}: answer_verified must be boolean`);
    if (q.options != null) need(Array.isArray(q.options) && q.options.every(v => typeof v === 'string'), `${label}: options must be string array`);
    if (q.answer != null) need(typeof q.answer === 'string', `${label}: answer must be plain text`);
    if (q.source_id) need(sourceIds.has(q.source_id), `${label}: unresolved source_id`);
    if (!q.text && !questionImages(q).length) (final ? errors : warnings).push(`${label}: neither text nor question evidence exists`);
    for (const key of ['pdf_file', 'marking_scheme_pdf_file', 'marking_scheme_file']) checkLink(q[key], `${label}.${key}`, { local: true });
    for (const key of ['source_url', 'marking_scheme_url']) checkLink(q[key], `${label}.${key}`);
    for (const image of [...questionImages(q), ...answerImages(q)]) checkLink(image.src, `${label} evidence`, { local: true });
    if (q.origin === 'official') {
      const missing = ['source_title', 'year', 'session', 'question_number', 'original_section', 'marks', 'source_url'].filter(key => !present(q[key]));
      if (missing.length) (final ? errors : warnings).push(`${label}: missing exact provenance: ${missing.join(', ')}`);
      if (!['PYQ', 'SQP'].includes(q.exam_type)) (final ? errors : warnings).push(`${label}: exam_type must be PYQ or SQP`);
      const pages = array(q.pages || q.page);
      if (!pages.length || !pages.every(n => Number.isInteger(n) && n > 0)) (final ? errors : warnings).push(`${label}: valid one-based PDF pages required`);
      if (final) {
        need(q.verified === true, `${label}: official question not verified`);
        need(questionImages(q).length > 0, `${label}: official evidence image required`);
        if (q.answer || answerImages(q).length) {
          need(q.answer_verified === true, `${label}: official answer not verified`);
          need(answerImages(q).length > 0, `${label}: official answer evidence required`);
          need(array(q.answer_source_page).length > 0 && array(q.answer_source_page).every(n => Number.isInteger(n) && n > 0), `${label}: answer source PDF pages required`);
          need(!!q.marking_scheme_url, `${label}: official marking scheme URL required for answer`);
        }
      }
    }
  }
  for (const doc of data.documents) {
    const label = `Document ${doc.id}`;
    need(/^[a-z0-9_-]+$/.test(doc.id), `${label}: ID must be a lowercase slug`);
    need(typeof doc.title === 'string' && !!doc.title.trim(), `${label}: title required`);
    need(new Set(doc.question_ids).size === doc.question_ids.length, `${label}: duplicate question references`);
    if (doc.sections != null) need(Array.isArray(doc.sections), `${label}: sections must be an array`);
    for (const section of array(doc.sections)) {
      if (!section || typeof section !== 'object') { error(`${label}: invalid section`); continue; }
      for (const key of ['paragraphs', 'bullets']) if (section[key] != null) need(Array.isArray(section[key]) && section[key].every(v => typeof v === 'string'), `${label}: section ${key} must be string array`);
      for (const image of images(section.images)) checkLink(image.src, `${label} section image`, { local: true });
    }
    if (doc.status === 'ready') {
      need(doc.question_ids.length > 0 || array(doc.sections).some(s => array(s.paragraphs).length || array(s.bullets).length || images(s.images).length), `${label}: ready document is empty`);
      if (doc.kind !== 'notes') need(doc.question_ids.length > 0, `${label}: ready paper has no questions`);
    }
    for (const id of doc.question_ids) {
      const q = questions.get(id);
      if (doc.kind === 'official') need(q.origin === 'official', `${label}: original content cannot be labelled official`);
      if (doc.kind === 'practice') need(q.origin === 'original', `${label}: practice papers must use original questions`);
    }
    for (const key of ['marks', 'duration_minutes']) if (doc[key] != null) need(positive(doc[key]), `${label}: ${key} must be positive`);
    checkLink(doc.pdf, `${label}.pdf`, { local: true });
    if (doc.pdf) need(/\.pdf$/i.test(doc.pdf), `${label}: pdf must end in .pdf`);
  }
  for (const source of data.sources) {
    need(typeof source.title === 'string' && !!source.title.trim(), `Source ${source.id}: title required`);
    checkLink(source.url, `Source ${source.id}.url`); checkLink(source.local_pdf, `Source ${source.id}.local_pdf`, { local: true }); checkLink(source.marking_scheme_url, `Source ${source.id}.marking_scheme_url`);
  }
  for (const topic of array(data.coverage?.topics)) need(['covered', 'partial', 'pending'].includes(topic.status), `Invalid coverage status: ${topic.status}`);
  if (final) {
    for (const [kind, target] of Object.entries(TARGETS)) {
      need(data.documents.filter(d => d.kind === kind).length === target, `Final inventory requires exactly ${target} ${kind} documents`);
      need(data.documents.filter(d => d.kind === kind && d.status === 'ready').length === target, `Final inventory requires ${target} ready ${kind} documents`);
    }
    need(!!data.coverage?.summary && array(data.coverage?.topics).length > 0, 'Final coverage summary and topics required');
    need(!!data.meta?.updated, 'Final content update date required');
  } else if (!data.documents.length) warnings.push('Pending shell: 0 of 21 planned documents assembled. This is not a finished content collection.');
  return { errors, warnings, localAssets: new Set(urls).size };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const final = process.argv.includes('--final');
  const flag = process.argv.indexOf('--file');
  const filename = flag >= 0 ? process.argv[flag + 1] : path.join(site, 'data/content.json');
  try {
    const data = JSON.parse(fs.readFileSync(filename, 'utf8'));
    const result = validate(data, { final });
    for (const message of result.warnings) console.warn(`WARN ${message}`);
    for (const message of result.errors) console.error(`ERROR ${message}`);
    console.log(`${result.errors.length ? 'FAIL' : 'PASS'} ${final ? 'publication' : 'assembly'} validation: ${data.documents?.length ?? 0} documents, ${data.questions?.length ?? 0} questions, ${result.localAssets ?? 0} local assets, ${result.errors.length} errors, ${result.warnings.length} warnings.`);
    process.exitCode = result.errors.length ? 1 : 0;
  } catch (e) { console.error(`FAIL ${e.message}`); process.exitCode = 1; }
}
