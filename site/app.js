import { TARGETS, LABELS, array, display, safeURL, images, questionImages, answerImages, matchesQuestion, checkShape } from './content-utils.mjs';
const $ = selector => document.querySelector(selector);
let data, questionMap, selectedKind = 'official', currentDoc = null, visibleLimit = 20;
const text = (tag, value, className) => { const node = document.createElement(tag); node.textContent = value ?? ''; if (className) node.className = className; return node; };
const button = (label, action, className = 'button secondary') => { const node = text('button', label, className); node.type = 'button'; node.addEventListener('click', action); return node; };
const badge = (value, label = value) => text('span', label, `badge ${value}`);
function link(label, value, download = false) {
  const url = safeURL(value);
  if (!url) return text('span', `${label}: unavailable`, 'small');
  const node = text('a', label); node.href = url;
  if (/^https?:/i.test(url)) { node.target = '_blank'; node.rel = 'noopener noreferrer'; }
  if (download) node.setAttribute('download', '');
  return node;
}
function empty(title, message) {
  const node = text('div', '', 'empty'); node.append(text('div', '↗', 'empty-symbol'), text('h3', title), text('p', message)); return node;
}
function addImages(parent, items, label) {
  items.forEach((item, i) => {
    const figure = text('figure', '', 'evidence');
    const url = safeURL(item.src);
    if (url) {
      const img = document.createElement('img'); img.src = url; img.alt = item.alt || `${label}, image ${i + 1}. Source image; use the accompanying transcription when available.`; img.loading = 'lazy'; img.decoding = 'async';
      img.addEventListener('error', () => { img.hidden = true; figure.prepend(text('p', 'Source image could not be loaded. Consult the original linked paper; this evidence is not replaced with a reconstruction.', 'missing-image')); }, { once: true });
      figure.append(img);
      const caption = text('figcaption', ''); caption.append(link(`${label} · image ${i + 1} (open full size)`, item.src)); figure.append(caption);
    } else figure.append(text('p', 'Source image unavailable: invalid asset path.', 'missing-image'));
    parent.append(figure);
  });
}
function disclosure(title, body, className = '') {
  const node = text('details', '', className); node.append(text('summary', title), body); return node;
}
function provenance(q) {
  const node = text('div', '', 'source-entry');
  node.append(text('h4', `${q.exam_type || 'Official source'} · ${q.source_title || 'Source title not recorded'}`));
  const grid = text('dl', '', 'source-grid');
  for (const [label, value] of [['Year', q.year], ['Session', q.session], ['Question', q.question_number], ['Section', q.original_section], ['Marks', q.marks], ['PDF pages (1-based)', q.pages || q.page], ['Paper / set code', q.paper_code], ['Printed pages', q.printed_pages]]) {
    if (['Paper / set code', 'Printed pages'].includes(label) && !value) continue;
    const pair = document.createElement('div'); pair.append(text('dt', label), text('dd', display(value))); grid.append(pair);
  }
  node.append(grid);
  const links = text('div', '', 'source-links'); links.append(link('Official question source', q.source_url));
  if (q.pdf_file) links.append(link('Local original paper', q.pdf_file));
  if (q.marking_scheme_url) links.append(link('Official marking scheme', q.marking_scheme_url));
  if (q.marking_scheme_pdf_file || q.marking_scheme_file) links.append(link('Local marking scheme', q.marking_scheme_pdf_file || q.marking_scheme_file));
  node.append(links);
  if (q.answer_source_page) node.append(text('p', `Answer source PDF pages: ${display(q.answer_source_page)}`, 'small'));
  node.append(text('p', q.verified === true ? 'Question evidence: editorially verified.' : 'Question evidence: verification pending.', q.verified ? 'small' : 'warning'));
  if (q.notes) node.append(text('p', q.notes, 'prose'));
  return node;
}
function renderQuestion(q, number, { printing = false, answers = false } = {}) {
  const node = text('article', '', 'question');
  const top = text('div', '', 'question-top'); top.append(text('h3', number ? `Question ${number}` : `Question ${q.question_number || q.id}`), badge(q.origin === 'official' ? 'official' : 'original', q.origin === 'official' ? `Official ${q.exam_type || 'source'}` : 'Original practice'));
  if (q.topic) top.append(text('span', q.topic));
  top.append(text('span', q.marks == null ? 'Marks not recorded' : `${q.marks} mark${q.marks === 1 ? '' : 's'}`));
  if (q.type) top.append(text('span', q.type));
  node.append(top);
  if (q.verified !== true) node.append(text('p', 'Editorial verification pending — check the linked evidence before relying on this item.', 'warning'));
  if (q.text) node.append(text('p', q.text, 'prose'));
  if (array(q.options).length) { const list = text('ol', '', 'prose'); list.type = 'A'; for (const option of q.options) list.append(text('li', option)); node.append(list); }
  addImages(node, questionImages(q), q.origin === 'official' ? `Original question evidence · Q${q.question_number || q.id}` : 'Practice illustration');
  if (!q.text && !questionImages(q).length) node.append(text('p', 'Question content is pending.', 'warning'));
  if (q.answer || answerImages(q).length) {
    if (!printing || answers) {
      const body = document.createElement('div');
      if (q.answer_verified !== true) body.append(text('p', 'Answer verification pending. Treat this answer as provisional.', 'warning'));
      if (q.answer) body.append(text('p', q.answer, 'prose'));
      if (q.answer_transcription) body.append(text('p', q.answer_transcription, 'small'));
      if (q.answer_source_page) body.append(text('p', `Marking scheme PDF pages: ${display(q.answer_source_page)}`, 'small'));
      addImages(body, answerImages(q), 'Answer evidence');
      const details = disclosure(q.origin === 'official' ? 'Answer / marking-scheme evidence' : 'Original worked answer', body, 'answer'); details.open = printing; node.append(details);
    }
  }
  if (q.origin === 'official' && !printing) node.append(disclosure('Exact source & verification', provenance(q)));
  return node;
}
function renderDocument(doc, options = {}) {
  const node = text('article', '', options.printing ? 'print-document' : 'document');
  const header = text('header', '', 'doc-header'); header.append(text('p', LABELS[doc.kind], 'doc-label'), text(options.printing ? 'h1' : 'h2', doc.title), badge(doc.status));
  if (doc.subtitle) header.append(text('p', doc.subtitle));
  if (doc.description) header.append(text('p', doc.description, 'prose'));
  const stats = [`${doc.question_ids.length} questions`];
  if (doc.duration_minutes) stats.push(`${doc.duration_minutes} minutes`);
  if (doc.marks) stats.push(`${doc.marks} marks`);
  header.append(text('p', stats.join(' · '), 'small'));
  if (doc.status !== 'ready') header.append(text('p', 'This document is not yet ready for publication. Content may be incomplete or awaiting verification.', 'warning'));
  header.append(text('p', doc.kind === 'official' ? 'Independent Electricity-only compilation of official source questions. Not a full Science paper or a CBSE-issued compilation.' : doc.kind === 'practice' ? 'Original prediction-style practice. Not a CBSE paper; no guarantee of any future exam question.' : 'Independent Electricity-only revision guidance. Not an official CBSE publication.', 'small'));
  node.append(header);
  for (const section of array(doc.sections)) {
    const block = text('section', '', 'doc-section');
    if (section.heading) block.append(text('h3', section.heading));
    for (const paragraph of array(section.paragraphs)) block.append(text('p', paragraph, 'prose'));
    if (array(section.bullets).length) { const list = text('ul', '', 'prose'); section.bullets.forEach(item => list.append(text('li', item))); block.append(list); }
    addImages(block, images(section.images), 'Document evidence / illustration'); node.append(block);
  }
  doc.question_ids.forEach((id, index) => node.append(renderQuestion(questionMap.get(id), index + 1, options)));
  if (!doc.question_ids.length && !array(doc.sections).length) node.append(empty('Content not yet assembled', 'This placeholder does not contain invented questions or source claims.'));
  const official = doc.question_ids.map(id => questionMap.get(id)).filter(q => q.origin === 'official');
  if (official.length) {
    const appendix = text('section', '', 'source-appendix'); appendix.append(text('h3', 'Source appendix'), text('p', 'Compilation numbers below map to the exact original source labels. PDF pages are one-based; original printed page labels are shown separately when recorded.', 'small'));
    doc.question_ids.forEach((id, index) => { const q = questionMap.get(id); if (q.origin !== 'official') return; const item = provenance(q); item.prepend(text('p', `Compilation question ${index + 1} · ${q.id}`, 'small')); appendix.append(item); }); node.append(appendix);
  }
  node.append(text('p', 'CBSE Class 10 · Electricity only · Independent resource, not affiliated with CBSE. No exam guarantee.', 'small'));
  return node;
}
function openDocument(id, focus = true) {
  const doc = data.documents.find(item => item.id === id); if (!doc) return false;
  currentDoc = doc; $('#reader').hidden = false; $('#reader-title').textContent = doc.title;
  $('#reader-body').replaceChildren(renderDocument(doc));
  const actions = $('#reader-actions'); actions.replaceChildren();
  const label = text('label', ''); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.id = 'print-answers'; label.append(checkbox, document.createTextNode(' Include answers in print'));
  actions.append(button('Print this document', () => printDocuments([doc], checkbox.checked)), label);
  if (safeURL(doc.pdf)) { const download = link('Download PDF ↓', doc.pdf, true); download.className = 'button primary'; actions.append(download); }
  else actions.append(text('span', 'PDF not built yet · use Print → Save as PDF', 'small'));
  history.replaceState(null, '', `#doc-${encodeURIComponent(id)}`);
  if (focus) { $('#reader-title').focus({ preventScroll: true }); $('#reader').scrollIntoView({ behavior: 'smooth' }); }
  return true;
}
async function printDocuments(docs, answers = false) {
  if (!docs.length) return;
  const output = $('#print-output'); output.replaceChildren(...docs.map(doc => renderDocument(doc, { printing: true, answers })));
  output.querySelectorAll('img').forEach(img => { img.loading = 'eager'; });
  $('#load-status').hidden = false; $('#load-status').textContent = 'Preparing print images…';
  const waits = [...output.querySelectorAll('img')].map(img => img.decode().catch(() => false));
  let timedOut = false;
  let timer;
  await Promise.race([Promise.all(waits), new Promise(resolve => { timer = setTimeout(() => { timedOut = true; resolve(); }, 15000); })]);
  clearTimeout(timer);
  const missing = [...output.querySelectorAll('img')].some(img => !img.complete || !img.naturalWidth);
  if (timedOut || missing) {
    $('#load-status').textContent = 'Print stopped: one or more evidence images did not load. Check asset paths or connectivity, then retry. No incomplete PDF was generated.';
    return;
  }
  $('#load-status').textContent = `Print prepared: ${docs.length} document${docs.length === 1 ? '' : 's'}. Choose Save as PDF in your browser to create a file.`;
  window.print();
}
function renderSources() {
  const fragment = document.createDocumentFragment();
  fragment.append(text('p', 'Trace every official item back to its source. Original question labels, sections and one-based PDF pages are preserved; missing fields are never inferred.', 'category-note'));
  if (!data.sources.length && !data.questions.some(q => q.origin === 'official')) return empty('Sources will appear with the content', 'No official provenance has been invented. Each official question will carry its own source record and evidence images.');
  for (const source of data.sources) {
    const item = text('article', '', 'source-entry'); item.append(text('h3', source.title), text('p', [source.exam_type, source.year, source.session].filter(Boolean).join(' · ')));
    const links = text('div', '', 'source-links'); links.append(link('Official source', source.url)); if (source.local_pdf) links.append(link('Local paper', source.local_pdf)); if (source.marking_scheme_url) links.append(link('Marking scheme', source.marking_scheme_url)); item.append(links); if (source.notes) item.append(text('p', source.notes, 'prose')); fragment.append(item);
  }
  const official = data.questions.filter(q => q.origin === 'official');
  if (official.length) {
    fragment.append(text('h3', 'Question-level provenance'));
    for (const q of official) fragment.append(disclosure(`${q.session || 'Session not recorded'} · ${q.exam_type || 'Official'} · Q${q.question_number || 'Not recorded'} · ${q.id}`, provenance(q)));
  }
  return fragment;
}
function renderLibrary() {
  const panel = $('#library-panel'); panel.replaceChildren();
  if (selectedKind === 'sources') { panel.append(renderSources()); return; }
  panel.append(text('p', selectedKind === 'official' ? 'Chapter-only compilations from official PYQs and SQPs — not full Science papers. Each compilation includes its own question-by-question source appendix.' : selectedKind === 'practice' ? 'Original prediction-style papers designed for practice. They are not official papers and do not guarantee exam content.' : 'Detailed chapter notes and revision guidance, written independently.', 'category-note'));
  const docs = data.documents.filter(doc => doc.kind === selectedKind);
  if (!docs.length) { panel.append(empty('A careful collection, still in preparation.', `Planned: ${TARGETS[selectedKind]} ${selectedKind === 'official' ? 'official source compilations' : selectedKind === 'practice' ? 'original practice papers' : 'notes and guidance documents'}. Real content will appear here after assembly. Nothing has been filled with fabricated examples.`)); return; }
  const cards = text('div', '', 'cards');
  docs.forEach((doc, i) => {
    const card = text('article', '', 'card'); const top = text('div', '', 'card-number'); top.append(text('span', `${selectedKind.toUpperCase()} / ${String(i + 1).padStart(2, '0')}`), badge(doc.status));
    card.append(top, text('h3', doc.title)); if (doc.subtitle) card.append(text('p', doc.subtitle)); if (doc.description) card.append(text('p', doc.description));
    card.append(text('p', `${doc.question_ids.length} questions${doc.marks ? ` · ${doc.marks} marks` : ''}${doc.duration_minutes ? ` · ${doc.duration_minutes} min` : ''}`, 'small'));
    const actions = text('div', '', 'card-actions'); actions.append(button('Preview ↗', () => openDocument(doc.id), 'button primary'));
    if (safeURL(doc.pdf)) actions.append(link('PDF ↓', doc.pdf, true)); else actions.append(text('span', 'PDF pending', 'small'));
    card.append(actions); cards.append(card);
  }); panel.append(cards);
}
function selectTab(kind, focus = false) {
  selectedKind = kind;
  document.querySelectorAll('[role=tab]').forEach(tab => { const selected = tab.dataset.kind === kind; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; if (selected && focus) tab.focus(); });
  $('#library-panel').setAttribute('aria-labelledby', `tab-${kind}`); renderLibrary();
}
function renderBank() {
  const criteria = { search: $('#search').value, topic: $('#topic').value, origin: $('#origin').value, marks: $('#marks').value };
  const found = data.questions.filter(q => matchesQuestion(q, criteria));
  $('#results-status').textContent = `${found.length} question${found.length === 1 ? '' : 's'} found · showing ${Math.min(visibleLimit, found.length)}${data.questions.length ? '' : ' · content assembly pending'}`;
  const result = $('#question-results'); result.replaceChildren();
  if (!found.length) result.append(empty(data.questions.length ? 'No matching questions' : 'Your question bank is on its way', data.questions.length ? 'Try a shorter search or reset the topic, origin and marks filters.' : 'Search will become available as real official and original questions are assembled.'));
  for (const q of found.slice(0, visibleLimit)) {
    const heading = `${q.origin === 'official' ? `${q.exam_type || 'Official'} · ${q.session || 'Session pending'} · Q${q.question_number || '—'}` : 'Original practice'} · ${q.topic || 'Topic pending'} · ${q.marks ?? '—'} marks`;
    result.append(disclosure(heading, renderQuestion(q)));
  }
  $('#more-results').hidden = found.length <= visibleLimit;
}
function renderCoverage() {
  const ready = data.documents.filter(doc => doc.status === 'ready').length;
  const official = data.questions.filter(q => q.origin === 'official');
  const verified = official.filter(q => q.verified === true).length;
  $('#inventory-summary').textContent = `${ready} of 21 planned documents ready`;
  $('#coverage-summary').textContent = data.coverage?.summary || 'Coverage has not yet been audited.';
  $('#updated').textContent = data.meta?.updated ? `Content updated: ${data.meta.updated}` : 'Content update date: not yet recorded.';
  $('#coverage-counts').replaceChildren();
  for (const [value, label] of [[`${ready}/21`, 'documents ready'], [data.questions.length, 'bank questions'], [`${verified}/${official.length}`, 'official items verified']]) { const box = document.createElement('div'); box.append(text('strong', value), text('span', label)); $('#coverage-counts').append(box); }
  $('#topic-coverage').replaceChildren();
  for (const topic of array(data.coverage?.topics)) { const item = document.createElement('li'); const line = text('div', '', 'topic-line'); line.append(text('span', topic.name), badge(topic.status || 'pending')); item.append(line); if (topic.note) item.append(text('small', topic.note)); $('#topic-coverage').append(item); }
  if (!array(data.coverage?.topics).length) $('#topic-coverage').append(text('li', 'Topic coverage has not yet been recorded.'));
  $('#limitations').replaceChildren(...array(data.coverage?.limitations).map(item => text('li', item)));
  $('#print-all').disabled = !ready;
  for (const kind of Object.keys(TARGETS)) $('#count-' + kind).textContent = `${data.documents.filter(doc => doc.kind === kind && doc.status === 'ready').length}/${TARGETS[kind]}`;
}
function route() {
  if (location.hash.startsWith('#doc-')) {
    let id; try { id = decodeURIComponent(location.hash.slice(5)); } catch { return; }
    if (!openDocument(id)) { $('#load-status').hidden = false; $('#load-status').textContent = 'The requested document was not found in this edition of the library.'; }
  }
}
async function start() {
  try {
    const response = await fetch(new URL('data/content.json', import.meta.url));
    if (!response.ok) throw new Error(`Content request failed (HTTP ${response.status}).`);
    data = checkShape(await response.json()); questionMap = new Map(data.questions.map(q => [q.id, q]));
    if (data.meta?.title) document.title = data.meta.title;
    if (data.meta?.intro) $('#intro').textContent = data.meta.intro;
    const ready = data.documents.filter(doc => doc.status === 'ready').length;
    $('#load-status').hidden = ready === 21;
    $('#load-status').textContent = ready ? `${ready} of 21 planned documents are ready. Other items may still be drafts; see coverage and verification labels below.` : 'Assembly in progress · This site is ready for real content. No finished documents are published yet.';
    const topics = [...new Set(data.questions.map(q => q.topic).filter(Boolean))].sort();
    const marks = [...new Set(data.questions.map(q => q.marks).filter(v => v != null))].sort((a, b) => a - b);
    for (const topic of topics) { const option = text('option', topic); option.value = topic; $('#topic').append(option); }
    for (const mark of marks) { const option = text('option', `${mark} marks`); option.value = mark; $('#marks').append(option); }
    renderCoverage(); renderLibrary(); renderBank(); route();
    document.querySelectorAll('[role=tab]').forEach((tab, i, tabs) => {
      tab.addEventListener('click', () => selectTab(tab.dataset.kind));
      tab.addEventListener('keydown', event => { let next; if (event.key === 'ArrowRight') next = (i + 1) % tabs.length; if (event.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length; if (event.key === 'Home') next = 0; if (event.key === 'End') next = tabs.length - 1; if (next !== undefined) { event.preventDefault(); selectTab(tabs[next].dataset.kind, true); } });
    });
    $('#close-reader').addEventListener('click', () => { $('#reader').hidden = true; currentDoc = null; history.replaceState(null, '', '#library'); $(`[data-kind="${selectedKind}"]`).focus(); });
    $('#search-form').addEventListener('submit', event => event.preventDefault());
    $('#search-form').addEventListener('input', () => { visibleLimit = 20; renderBank(); });
    $('#search-form').addEventListener('change', () => { visibleLimit = 20; renderBank(); });
    $('#search-form').addEventListener('reset', () => { setTimeout(() => { visibleLimit = 20; renderBank(); }, 0); });
    $('#more-results').addEventListener('click', () => { visibleLimit += 20; renderBank(); });
    $('#print-all').addEventListener('click', () => { const answers = window.confirm('Include answers in the printed collection? Choose OK for questions + answers, or Cancel for questions only.'); printDocuments(data.documents.filter(doc => doc.status === 'ready'), answers); });
    window.addEventListener('hashchange', route);
    window.addEventListener('beforeprint', () => {
      if (!$('#print-output').childElementCount) { const docs = currentDoc ? [currentDoc] : data.documents.filter(doc => doc.status === 'ready'); $('#print-output').replaceChildren(...docs.map(doc => renderDocument(doc, { printing: true }))); if (!docs.length) $('#print-output').append(text('p', 'Electricity study library — no ready documents available. Content assembly is pending.')); $('#print-output').querySelectorAll('img').forEach(img => { img.loading = 'eager'; }); }
    });
    window.addEventListener('afterprint', () => $('#print-output').replaceChildren());
  } catch (error) {
    const status = $('#load-status'); status.hidden = false; status.classList.add('error'); status.setAttribute('role', 'alert'); status.replaceChildren(text('strong', 'The library could not be loaded. '), text('span', `${error.message} Serve this folder over HTTP, verify data/content.json, then reload. `), button('Retry', () => location.reload()));
    $('#inventory-summary').textContent = 'Content unavailable — not verified';
    $('#library-panel').replaceChildren(empty('Content unavailable', 'The planned collection is not evidence of published content. Please retry after checking the data file.'));
    console.error('Library initialization failed:', error);
  }
}
start();
