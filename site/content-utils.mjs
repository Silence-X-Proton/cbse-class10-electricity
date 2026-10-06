export const TARGETS = { official: 15, practice: 4, notes: 2 };
export const LABELS = { official: 'Official source compilation', practice: 'Original prediction practice', notes: 'Notes & guidance' };
export const array = value => value == null ? [] : Array.isArray(value) ? value : [value];
export const display = value => value == null || value === '' || (Array.isArray(value) && !value.length) ? 'Not recorded' : array(value).join(', ');
export function safeURL(value) {
  if (typeof value !== 'string' || !value || value !== value.trim() || /[\u0000-\u0020\\]/.test(value)) return null;
  if (/^https?:\/\//i.test(value)) {
    try { const u = new URL(value); return u.username || u.password ? null : u.href; } catch { return null; }
  }
  if (/^[a-z][a-z\d+.-]*:/i.test(value) || value.startsWith('/') || value.startsWith('#') || value.startsWith('?')) return null;
  let decoded;
  try { decoded = decodeURIComponent(value.split(/[?#]/)[0]); } catch { return null; }
  if (decoded.startsWith('/') || /[\\\u0000-\u001f]/.test(decoded) || decoded.split('/').some(p => p === '..' || p === '.')) return null;
  return value;
}
export function images(...values) {
  const seen = new Set();
  return values.flatMap(array).filter(Boolean).map(v => typeof v === 'string' ? { src: v, alt: '' } : v).filter(v => {
    if (!v || typeof v.src !== 'string' || seen.has(v.src)) return false;
    seen.add(v.src); return true;
  });
}
export const questionImages = q => images(q.evidence_images, q.evidence_image, q.diagram_image);
export const answerImages = q => images(q.answer_evidence_images, q.answer_evidence_image);
export function matchesQuestion(q, { search = '', topic = '', origin = '', marks = '', exam_type = '', year = '', session = '', paper_code = '' } = {}) {
  const haystack = [q.id, q.source_id, q.exam_type, q.set, q.text, q.topic, q.type, q.session, q.year, q.question_number, q.source_title, q.paper_code, ...array(q.options)].join(' ').toLocaleLowerCase();
  const exact = (value, criterion) => value != null && String(value) === String(criterion);
  return (!topic || q.topic === topic) && (!origin || q.origin === origin) && (!marks || String(q.marks) === marks)
    && (!exam_type || q.exam_type === exam_type)
    && (!year || exact(q.year, year) || exact(q.session, year))
    && (!session || exact(q.session, session))
    && (!paper_code || exact(q.paper_code || q.set, paper_code))
    && search.trim().toLocaleLowerCase().split(/\s+/).every(word => haystack.includes(word));
}
export function documentCollectionType(doc, questionMap) {
  if (doc.kind !== 'official') return 'unknown';
  if (Object.hasOwn(doc, 'collection_type')) return ['pyq', 'sqp', 'mixed'].includes(doc.collection_type) ? doc.collection_type : 'unknown';
  if (!Array.isArray(doc.question_ids) || !doc.question_ids.length) return 'unknown';
  const types = new Set();
  for (const id of doc.question_ids) {
    const q = questionMap.get(id);
    // Every reference must have authoritative provenance, even after finding both types.
    if (!q || q.origin !== 'official' || !['PYQ', 'SQP'].includes(q.exam_type)) return 'unknown';
    types.add(q.exam_type);
  }
  return types.size === 2 ? 'mixed' : [...types][0].toLowerCase();
}
export function checkShape(data) {
  if (!data || data.schema_version !== 1) throw new Error('Unsupported content schema. Expected schema_version 1.');
  for (const key of ['documents', 'questions', 'sources']) if (!Array.isArray(data[key])) throw new Error(`Content field “${key}” must be an array.`);
  for (const key of ['documents', 'questions', 'sources']) {
    const ids = new Set();
    for (const item of data[key]) {
      if (!item || typeof item.id !== 'string' || !item.id || ids.has(item.id)) throw new Error(`Invalid or duplicate ID in ${key}.`);
      ids.add(item.id);
    }
  }
  const ids = new Set(data.questions.map(q => q.id));
  for (const doc of data.documents) {
    if (!(doc.kind in TARGETS) || !['pending', 'draft', 'ready'].includes(doc.status) || !Array.isArray(doc.question_ids)) throw new Error(`Invalid document structure: ${doc.id}`);
    if (doc.question_ids.some(id => !ids.has(id))) throw new Error(`Missing question reference in document: ${doc.id}`);
  }
  return data;
}

// Series labels organize supplied practice only; they never imply a question count.
export function isSpecial39(doc) {
  return doc.kind === 'practice' && (doc.practice_series === 'special39' || /^special-39-0[1-4]$/.test(doc.id) || /\bspecial\s*39\b/i.test(doc.title || ''));
}
