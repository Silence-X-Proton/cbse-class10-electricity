import { LABELS, documentCollectionType, isSpecial39, array, display, safeURL, images, questionImages, answerImages, matchesQuestion, checkShape } from './content-utils.mjs';
import { evidenceViewer, renderSourceCoverage } from './ui-evidence.mjs';
const $ = selector => document.querySelector(selector);
let data, questionMap, selectedKind = 'official', currentDoc = null, visibleLimit = 20;
const PAGE_SIZE = 8;
let selectedBank = 'PYQ', readerPage = 0, readerInvoker;
const zoomEvidence = evidenceViewer();
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
      const zoom = button('', () => zoomEvidence(item, `${label} · image ${i + 1}`, zoom), 'image-zoom');
      zoom.setAttribute('aria-label', `Zoom ${label} · image ${i + 1}`); zoom.append(img); figure.append(zoom);
      const caption = text('figcaption', ''); caption.append(link(`${label} · image ${i + 1} (open full size)`, item.src)); figure.append(caption);
    } else figure.append(text('p', 'Source image unavailable: invalid asset path.', 'missing-image'));
    parent.append(figure);
  });
}
function disclosure(title, body, className = '') {
  const node = text('details', '', className); node.append(text('summary', title));
  if (typeof body === 'function') {
    node.addEventListener('toggle', () => { if (node.open && node.childElementCount === 1) node.append(body()); });
  } else node.append(body);
  return node;
}
function provenance(q) {
  const node = text('div', '', 'source-entry');
  node.append(text('h4', `${q.exam_type || 'Official source'} · ${q.source_title || 'Source title not recorded'}`));
  const grid = text('dl', '', 'source-grid');
  for (const [label, value] of [['Question ID', q.id], ['Source ID', q.source_id], ['Year', q.year], ['Session', q.session], ['Question', q.question_number], ['Section', q.original_section], ['Marks', q.marks], ['PDF pages (1-based)', q.pages || q.page], ['Paper / set code', q.paper_code || q.set], ['Printed pages', q.printed_pages]]) {
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
  const node = text('article', '', 'question'); node.dataset.questionId = q.id;
  const top = text('div', '', 'question-top'); top.append(text('h3', number ? `Question ${number}` : `Question ${q.question_number || q.id}`), badge(q.origin === 'official' ? 'official' : 'original', q.origin === 'official' ? `Official ${q.exam_type || 'source'}` : 'Original practice'));
  if (q.topic) top.append(text('span', q.topic));
  top.append(text('span', q.marks == null ? 'Marks not recorded' : `${q.marks} mark${q.marks === 1 ? '' : 's'}`));
  if (q.type) top.append(text('span', q.type));
  node.append(top, text('p', [
    'ID: ' + q.id, 'Source: ' + display(q.source_id), 'Year: ' + display(q.year),
    'Session: ' + display(q.session), 'Set: ' + display(q.paper_code || q.set), 'Original Q: ' + display(q.question_number)
  ].join(' · '), 'question-identity small'));
  for (const [label, value] of [['Publication status', q.publication_status], ['Solution status', q.solution_status], ['Answer hold', q.answer_hold_reason], ['Hold reason', q.hold_reason], ['Answer verification note', q.answer_verification_note]]) {
    if (value != null && value !== '') node.append(text('p', label + ': ' + display(value), 'warning'));
  }
  if (q.notes && q.origin === 'official') node.append(text('p', q.notes, 'prose small'));
  if (q.verified !== true) node.append(text('p', 'Editorial verification pending — check the linked evidence before relying on this item.', 'warning'));
  if (q.text) node.append(text('p', q.text, 'prose'));
  if (array(q.options).length) { const list = text('ol', '', 'prose'); list.type = 'A'; for (const option of q.options) list.append(text('li', option)); node.append(list); }
  addImages(node, questionImages(q), q.origin === 'official' ? `Original question evidence · Q${q.question_number || q.id}` : 'Practice illustration');
  if (!q.text && !questionImages(q).length) node.append(text('p', 'Question content is pending.', 'warning'));
  if (q.answer || answerImages(q).length || (q.origin === 'original' && q.notes)) {
    if (q.answer_verified !== true) node.append(text('p', 'Answer verification pending. Treat this answer as provisional; check its verification label before use.', 'warning'));
    if (!printing || (answers && (q.origin === 'original' || q.answer_verified === true))) {
      const makeAnswer = () => {
      const body = document.createElement('div');
      if (q.answer_verified !== true) body.append(text('p', 'Answer verification pending. Treat this answer as provisional.', 'warning'));
      if (q.answer) body.append(text('p', q.answer, 'prose'));
      if (q.notes && q.origin === 'original') body.append(text('p', q.notes, 'prose small'));
      if (q.answer_transcription) body.append(text('p', q.answer_transcription, 'small'));
      if (q.answer_source_page) body.append(text('p', `Marking scheme PDF pages: ${display(q.answer_source_page)}`, 'small'));
      addImages(body, answerImages(q), 'Answer evidence');
      return body;
      };
      const details = disclosure(q.origin === 'official' ? 'Answer / marking-scheme evidence' : 'Original worked answer', printing ? makeAnswer() : makeAnswer, 'answer'); details.open = printing; node.append(details);
    }
  }
  if (q.origin === 'official' && !printing) node.append(disclosure('Exact source & verification', () => provenance(q)));
  return node;
}
function renderDocument(doc, options = {}) {
  const node = text('article', '', options.printing ? 'print-document' : 'document');
  const header = text('header', '', 'doc-header'); header.append(text('p', collectionLabel(doc), 'doc-label'), text(options.printing ? 'h1' : 'h2', doc.title), badge(doc.status));
  if (doc.subtitle) header.append(text('p', doc.subtitle));
  if (doc.description) header.append(text('p', doc.description, 'prose'));
  const stats = [`${doc.question_ids.length} questions`];
  if (doc.duration_minutes) stats.push(`${doc.duration_minutes} minutes`);
  if (doc.marks) stats.push(`${doc.marks} marks`);
  header.append(text('p', stats.join(' · '), 'small'));
  if (doc.status !== 'ready') header.append(text('p', 'This document is not yet ready for publication. Content may be incomplete or awaiting verification.', 'warning'));
  header.append(text('p', doc.kind === 'official' ? 'Independent Electricity-only compilation of official source questions. Not a full Science paper or a CBSE-issued compilation.' : doc.kind === 'practice' ? 'Original practice. Not a CBSE paper; no guarantee of any future exam question.' : 'Independent Electricity-only revision guidance. Not an official CBSE publication.', 'small'));
  node.append(header);
  const start = options.printing ? 0 : readerPage * PAGE_SIZE;
  const ids = options.printing ? doc.question_ids : doc.question_ids.slice(start, start + PAGE_SIZE);
  const sections = options.printing || readerPage === 0 ? array(doc.sections) : [];
  for (const section of sections) {
    const block = text('section', '', 'doc-section');
    if (section.heading) block.append(text('h3', section.heading));
    for (const paragraph of array(section.paragraphs)) block.append(text('p', paragraph, 'prose'));
    if (array(section.bullets).length) { const list = text('ul', '', 'prose'); section.bullets.forEach(item => list.append(text('li', item))); block.append(list); }
    addImages(block, images(section.images), 'Document evidence / illustration'); node.append(block);
  }
  ids.forEach((id, index) => node.append(renderQuestion(questionMap.get(id), start + index + 1, options)));
  if (!doc.question_ids.length && !array(doc.sections).length) node.append(empty('Content not yet assembled', 'This placeholder does not contain invented questions or source claims.'));
  const official = ids.map(id => questionMap.get(id)).filter(q => q.origin === 'official');
  if (official.length) {
    const appendix = text('section', '', 'source-appendix'); appendix.append(text('h3', 'Source appendix'), text('p', 'Compilation numbers below map to the exact original source labels. PDF pages are one-based; original printed page labels are shown separately when recorded.', 'small'));
    ids.forEach((id, index) => { const q = questionMap.get(id); if (q.origin !== 'official') return; const item = provenance(q); item.prepend(text('p', `Compilation question ${start + index + 1} · ${q.id}`, 'small')); appendix.append(item); }); node.append(appendix);
  }
  node.append(text('p', 'CBSE Class 10 · Electricity only · Independent resource, not affiliated with CBSE. No exam guarantee.', 'small'));
  return node;
}
function removePDF() {
  $('#pdf-preview').replaceChildren();
  const toggle = $('#pdf-toggle'); if (toggle) { toggle.textContent = 'Show PDF preview'; toggle.setAttribute('aria-expanded', 'false'); }
}
function renderReaderPage(focus = false) {
  const doc = currentDoc; if (!doc) return;
  const total = Math.max(1, Math.ceil(doc.question_ids.length / PAGE_SIZE));
  $('#reader-body').replaceChildren(renderDocument(doc));
  const controls = $('#reader-pagination'); controls.replaceChildren(); controls.className = 'pagination';
  if (total > 1) {
    const change = page => { readerPage = page; renderReaderPage(true); };
    const previous = button('Previous page', () => change(readerPage - 1)); previous.disabled = readerPage === 0;
    const next = button('Next page', () => change(readerPage + 1)); next.disabled = readerPage === total - 1;
    const label = text('label', 'Reader page '); const select = document.createElement('select'); select.id = 'reader-page';
    for (let page = 0; page < total; page++) { const option = text('option', String(page + 1)); option.value = page; select.append(option); }
    select.value = readerPage; select.addEventListener('change', () => change(Number(select.value))); label.append(select);
    const status = text('span', 'Page ' + (readerPage + 1) + ' of ' + total + ' · Questions ' + (readerPage * PAGE_SIZE + 1) + '–' + Math.min((readerPage + 1) * PAGE_SIZE, doc.question_ids.length) + ' of ' + doc.question_ids.length + '. Full print includes every page.', 'small'); status.setAttribute('role', 'status');
    controls.append(previous, label, next, status);
  }
  if (focus) { $('#reader-page')?.focus({ preventScroll: true }); controls.scrollIntoView({ behavior: 'instant', block: 'start' }); }
}
function openDocument(id, focus = true) {
  const doc = data.documents.find(item => item.id === id); if (!doc) return false;
  removePDF(); readerPage = 0; currentDoc = doc;
  $('#reader').hidden = false; $('#reader-title').textContent = doc.title; renderReaderPage();
  const actions = $('#reader-actions'); actions.replaceChildren();
  const label = text('label', ''); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.id = 'print-answers'; label.append(checkbox, document.createTextNode(' Include answers in print (official: verified only)'));
  actions.append(button('Print full document', () => printDocuments([doc], checkbox.checked)), label);
  if (safeURL(doc.pdf)) {
    const download = link('Download PDF ↓', doc.pdf, true); download.className = 'button primary';
    const open = link('Open PDF in new tab ↗', doc.pdf); open.id = 'pdf-open'; open.target = '_blank'; open.rel = 'noopener noreferrer';
    const toggle = button('Show PDF preview', () => {
      const showing = toggle.getAttribute('aria-expanded') === 'true'; removePDF();
      if (!showing) {
        const frame = document.createElement('iframe'); frame.title = doc.title + ' PDF preview'; frame.src = safeURL(doc.pdf);
        $('#pdf-preview').append(text('p', 'If the preview is blank or unsupported, use Open PDF in new tab or Download PDF above.', 'small'), frame);
        toggle.textContent = 'Hide PDF preview'; toggle.setAttribute('aria-expanded', 'true');
      }
    });
    toggle.id = 'pdf-toggle'; toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-controls', 'pdf-preview');
    actions.append(download, open, toggle, text('span', 'PDF preview is optional; no PDF loads until requested.', 'small'));
  } else actions.append(text('span', 'PDF not built yet · use Print → Save as PDF', 'small'));
  history.replaceState(null, '', '#doc-' + encodeURIComponent(id));
  if (focus) { $('#reader-title').focus({ preventScroll: true }); $('#reader').scrollIntoView({ behavior: 'instant' }); }
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
    output.replaceChildren();
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
function isLargeCollection(doc) { return doc.kind === 'official' && ['master', 'year'].includes(doc.collection_scope); }
function collectionLabel(doc) {
  if (isSpecial39(doc)) return 'Special39 · Original competency practice';
  if (doc.kind !== 'official') return LABELS[doc.kind];
  const type = documentCollectionType(doc, questionMap);
  const label = { pyq: 'PYQ only', sqp: 'SQP only', mixed: 'Mixed PYQ + SQP', unknown: 'Source type not recorded' }[type];
  return label + ' · ' + (doc.collection_scope || 'compilation') + (doc.collection_scope === 'year' ? ' · ' + display(doc.year) : '');
}
function documentCard(doc, i) {
  const card = text('article', '', 'card'); card.dataset.documentId = doc.id;
  const top = text('div', '', 'card-number'); top.append(text('span', doc.kind.toUpperCase() + ' / ' + String(i + 1).padStart(2, '0')), badge(doc.status));
  card.append(top, text('p', collectionLabel(doc), 'collection-label'), text('h3', doc.title));
  if (doc.subtitle) card.append(text('p', doc.subtitle)); if (doc.description) card.append(text('p', doc.description));
  card.append(text('p', doc.question_ids.length + ' questions' + (doc.marks ? ' · ' + doc.marks + ' marks' : '') + (doc.duration_minutes ? ' · ' + doc.duration_minutes + ' min' : ''), 'small'));
  if (doc.pdf_pages != null || doc.pdf_bytes != null) card.append(text('p', [doc.pdf_pages != null ? doc.pdf_pages + ' PDF pages' : '', doc.pdf_bytes != null ? doc.pdf_bytes.toLocaleString() + ' bytes' : ''].filter(Boolean).join(' · '), 'small'));
  const actions = text('div', '', 'card-actions');
  const preview = button('Preview ↗', () => { readerInvoker = preview; openDocument(doc.id); }, 'button primary'); actions.append(preview);
  if (safeURL(doc.pdf)) actions.append(link('PDF ↓', doc.pdf, true)); else actions.append(text('span', 'PDF pending', 'small'));
  card.append(actions); return card;
}
function renderCollections() {
  const panel = $('#collections-panel'); const type = $('#collection-type').value;
  const docs = data.documents.filter(doc => isLargeCollection(doc) && (type === 'all' || documentCollectionType(doc, questionMap) === type));
  panel.replaceChildren(text('p', docs.length + ' chapter collections in this category', 'small'));
  if (!docs.length) { panel.append(empty('No chapter collections published in this category yet', 'Master and year/session collections will appear when assembled. Browse the question banks now, or use the clearly labelled mixed compilations below. No full Science PDF is substituted for a chapter collection.')); return; }
  for (const scope of ['master', 'year']) {
    const group = docs.filter(doc => doc.collection_scope === scope); if (!group.length) continue;
    panel.append(text('h3', scope === 'master' ? 'Master banks' : 'Year / session volumes'));
    const cards = text('div', '', 'cards'); group.forEach((doc, i) => cards.append(documentCard(doc, i))); panel.append(cards);
  }
}
function renderLibrary() {
  const panel = $('#library-panel'); panel.replaceChildren();
  if (selectedKind === 'sources') { panel.append(renderSources()); return; }
  panel.append(text('p', selectedKind === 'official' ? 'Editorial chapter compilations. Mixed PYQ + SQP collections are labelled explicitly; these are not separate official CBSE chapter papers. Master and year banks are above.' : selectedKind === 'practice' ? 'Independently authored practice. Special39 competency papers and other original practice are separate; neither is official or guarantees exam content.' : 'Detailed chapter notes and revision guidance, written independently.', 'category-note'));
  const docs = data.documents.filter(doc => doc.kind === selectedKind && !isLargeCollection(doc));
  if (!docs.length) { panel.append(empty('No documents in this category yet', 'Real content will appear after assembly. No fabricated examples are published.')); return; }
  const special = docs.filter(isSpecial39);
  if (special.length) {
    const group = text('section', '', 'special39-group'); group.id = 'special39-practice'; group.setAttribute('aria-labelledby', 'special39-title');
    const heading = text('h3', 'Special39 / competency practice'); heading.id = 'special39-title';
    group.append(text('p', 'FEATURED ORIGINAL PRACTICE', 'eyebrow'), heading,
      text('p', special.length + ' supplied papers · Read each card for its actual question count and publication status. Independent original work, not official CBSE questions or a prediction guarantee.', 'small'));
    const cards = text('div', '', 'cards'); special.forEach((doc, i) => cards.append(documentCard(doc, i))); group.append(cards); panel.append(group);
    if (docs.length > special.length) panel.append(text('h3', 'Other original practice'));
  }
  const cards = text('div', '', 'cards'); docs.filter(doc => !isSpecial39(doc)).forEach((doc, i) => cards.append(documentCard(doc, i))); panel.append(cards);
}
function selectTab(kind, focus = false) {
  selectedKind = kind;
  document.querySelectorAll('[data-kind]').forEach(tab => { const selected = tab.dataset.kind === kind; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; if (selected && focus) tab.focus(); });
  $('#library-panel').setAttribute('aria-labelledby', `tab-${kind}`); renderLibrary();
}
function selectBank(bank, focus = false) {
  selectedBank = bank; visibleLimit = 20;
  document.querySelectorAll('[data-bank]').forEach(tab => {
    const selected = tab.dataset.bank === bank; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
    if (selected) { $('#bank-panel').setAttribute('aria-labelledby', tab.id); if (focus) tab.focus(); }
  });
  for (const id of ['year', 'session', 'paper-code']) $('#' + id).value = '';
  updateBankFilters(); renderBank();
}
function updateBankFilters() {
  const questions = data.questions.filter(q => selectedBank === 'all' || (selectedBank === 'original' ? q.origin === 'original' : q.origin === 'official' && q.exam_type === selectedBank));
  for (const [id, values, label] of [['year', questions.flatMap(q => [q.year, q.session]), 'All years / sessions'], ['session', questions.map(q => q.session), 'All sessions'], ['paper-code', questions.map(q => q.paper_code || q.set), 'All sets']]) {
    const select = $('#' + id); const old = select.value; const all = text('option', label); all.value = ''; select.replaceChildren(all);
    [...new Set(values.filter(v => v != null && v !== '').map(String))].sort((a,b) => a.localeCompare(b, undefined, { numeric: true })).forEach(value => { const option = text('option', value); option.value = value; select.append(option); });
    select.value = [...select.options].some(o => o.value === old) ? old : ''; select.disabled = selectedBank === 'original';
  }
}
function renderBank() {
  const criteria = { search: $('#search').value, topic: $('#topic').value, origin: selectedBank === 'original' ? 'original' : selectedBank === 'all' ? '' : 'official', exam_type: ['PYQ', 'SQP'].includes(selectedBank) ? selectedBank : '', marks: $('#marks').value, year: $('#year').value, session: $('#session').value, paper_code: $('#paper-code').value };
  const found = data.questions.filter(q => matchesQuestion(q, criteria));
  $('#results-status').textContent = `${found.length} question${found.length === 1 ? '' : 's'} found · showing ${Math.min(visibleLimit, found.length)}${data.questions.length ? '' : ' · content assembly pending'}`;
  const result = $('#question-results'); result.replaceChildren();
  if (!found.length) result.append(empty(data.questions.length ? 'No matching questions' : 'Your question bank is on its way', data.questions.length ? 'Try a shorter search or reset the year, session, set, topic and marks filters.' : 'Search will become available as real official and original questions are assembled.'));
  for (const q of found.slice(0, visibleLimit)) {
    const heading = `${q.origin === 'official' ? `${q.exam_type || 'Official'} · ${q.session || 'Session pending'} · Q${q.question_number || '—'}` : 'Original practice'} · ${q.topic || 'Topic pending'} · ${q.marks ?? '—'} marks`;
    const item = disclosure(`${heading} · Year ${display(q.year)} · Set ${display(q.paper_code || q.set)} · ID ${q.id}`, () => renderQuestion(q), 'bank-item'); item.dataset.questionId = q.id; result.append(item);
  }
  $('#more-results').hidden = found.length <= visibleLimit;
}
function renderCoverage() {
  const ready = data.documents.filter(doc => doc.status === 'ready').length;
  const official = data.questions.filter(q => q.origin === 'official');
  const verified = official.filter(q => q.verified === true).length;
  $('#inventory-summary').textContent = `${ready} of ${data.documents.length} documents ready`;
  $('#coverage-summary').textContent = data.coverage?.summary || 'Coverage has not yet been audited.';
  $('#updated').textContent = data.meta?.updated ? `Content updated: ${data.meta.updated}` : 'Content update date: not yet recorded.';
  $('#coverage-counts').replaceChildren();
  for (const [value, label] of [[`${ready}/${data.documents.length}`, 'documents ready'], [data.questions.length, 'bank questions'], [`${verified}/${official.length}`, 'official items verified']]) { const box = document.createElement('div'); box.append(text('strong', value), text('span', label)); $('#coverage-counts').append(box); }
  $('#topic-coverage').replaceChildren();
  for (const topic of array(data.coverage?.topics)) { const item = document.createElement('li'); const line = text('div', '', 'topic-line'); line.append(text('span', topic.name), badge(topic.status || 'pending')); item.append(line); if (topic.note) item.append(text('small', topic.note)); $('#topic-coverage').append(item); }
  if (!array(data.coverage?.topics).length) $('#topic-coverage').append(text('li', 'Topic coverage has not yet been recorded.'));
  $('#limitations').replaceChildren(...array(data.coverage?.limitations).map(item => text('li', item)));
  $('#print-all').disabled = !ready;
  for (const kind of ['official', 'practice', 'notes']) $('#count-' + kind).textContent = data.documents.filter(doc => doc.kind === kind && !isLargeCollection(doc)).length;
  renderSourceCoverage($('#source-coverage'), data);
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
    $('#load-status').hidden = ready > 0 && ready === data.documents.length;
    $('#load-status').textContent = ready ? `${ready} of ${data.documents.length} documents are ready. Other items may still be drafts; see coverage and verification labels below.` : 'Assembly in progress · This site is ready for real content. No finished documents are published yet.';
    const topics = [...new Set(data.questions.map(q => q.topic).filter(Boolean))].sort();
    const marks = [...new Set(data.questions.map(q => q.marks).filter(v => v != null))].sort((a, b) => a - b);
    for (const topic of topics) { const option = text('option', topic); option.value = topic; $('#topic').append(option); }
    for (const mark of marks) { const option = text('option', `${mark} marks`); option.value = mark; $('#marks').append(option); }
    updateBankFilters(); renderCoverage(); renderCollections(); renderLibrary(); renderBank(); route();
    $('#collection-type').addEventListener('change', renderCollections);
    document.querySelectorAll('[data-bank]').forEach((tab, i, tabs) => {
      tab.addEventListener('click', () => selectBank(tab.dataset.bank));
      tab.addEventListener('keydown', event => { const next = event.key === 'ArrowRight' ? (i + 1) % tabs.length : event.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : undefined; if (next !== undefined) { event.preventDefault(); selectBank(tabs[next].dataset.bank, true); } });
    });
    document.querySelectorAll('[data-kind]').forEach((tab, i, tabs) => {
      tab.addEventListener('click', () => selectTab(tab.dataset.kind));
      tab.addEventListener('keydown', event => { let next; if (event.key === 'ArrowRight') next = (i + 1) % tabs.length; if (event.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length; if (event.key === 'Home') next = 0; if (event.key === 'End') next = tabs.length - 1; if (next !== undefined) { event.preventDefault(); selectTab(tabs[next].dataset.kind, true); } });
    });
    $('#close-reader').addEventListener('click', () => { removePDF(); $('#reader-body').replaceChildren(); $('#reader').hidden = true; currentDoc = null; history.replaceState(null, '', '#library'); (readerInvoker?.isConnected ? readerInvoker : $(`[data-kind="${selectedKind}"]`)).focus(); });
    $('#search-form').addEventListener('submit', event => event.preventDefault());
    $('#search-form').addEventListener('input', () => { visibleLimit = 20; renderBank(); });
    $('#search-form').addEventListener('change', () => { visibleLimit = 20; renderBank(); });
    $('#search-form').addEventListener('reset', () => { setTimeout(() => { visibleLimit = 20; updateBankFilters(); renderBank(); }, 0); });
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
