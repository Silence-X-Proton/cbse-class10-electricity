// Test-only srcdoc harness. Never writes content.json or invents official questions.
// Expected results intentionally do not import the production filtering/classification helpers.
const base = new URL('../', import.meta.url);
const contentURL = new URL('../data/content.json', import.meta.url);
const result = document.querySelector('#result');
const frame = document.querySelector('#site');
const messages = [];
const assert = (condition, label) => {
  if (!condition) throw new Error(label);
  messages.push(`PASS ${label}`);
  result.textContent = messages.slice(-8).join('\n');
};
const equal = (actual, expected, label) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(label + ': expected ' + JSON.stringify(expected).slice(0, 1200) + ', got ' + JSON.stringify(actual).slice(0, 1200));
  assert(true, label);
};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const copy = value => JSON.parse(JSON.stringify(value));
const list = value => value == null ? [] : Array.isArray(value) ? value : [value];
const ids = questions => questions.map(q => q.id);
const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim();
const imagePaths = q => [...new Set([q.evidence_images, q.evidence_image, q.diagram_image].flatMap(list).filter(Boolean).map(v => typeof v === 'string' ? v : v.src))];
let d, w, mountSequence = 0;
const $ = selector => {
  const node = d.querySelector(selector);
  if (!node) throw new Error(`Required selector missing: ${selector}`);
  return node;
};
const $$ = selector => [...d.querySelectorAll(selector)];
async function until(predicate, label, timeout = 10000) {
  const deadline = performance.now() + timeout;
  while (!predicate()) {
    if (performance.now() > deadline) throw new Error(`Timeout: ${label}; ${d?.querySelector('#load-status')?.textContent || ''}`);
    await sleep(40);
  }
}
function change(selector, value) {
  const node = $(selector);
  node.value = String(value);
  if (node.value !== String(value)) throw new Error(`Missing option ${value} in ${selector}`);
  node.dispatchEvent(new w.Event(node.tagName === 'INPUT' ? 'input' : 'change', { bubbles: true }));
}
async function resetBank(bank = 'all') {
  $('#search-form').reset();
  await sleep(20);
  $(`#bank-tab-${bank.toLowerCase()}`).click();
}
function collectionType(doc, questions) {
  if (doc.collection_type) return doc.collection_type;
  const types = [...new Set(doc.question_ids.map(id => questions.get(id)?.exam_type))];
  return types.length === 2 && types.includes('PYQ') && types.includes('SQP') ? 'mixed' : types.length === 1 ? String(types[0]).toLowerCase() : 'unknown';
}
function isCollection(doc) { return doc.kind === 'official' && ['master', 'year'].includes(doc.collection_scope); }
function cardIDs(panel) { return $$(`${panel} .card`).map(card => card.dataset.documentId).sort(); }
function preview(doc) {
  if (isCollection(doc)) change('#collection-type', 'all');
  else $(`#tab-${doc.kind}`).click();
  const panel = isCollection(doc) ? '#collections-panel' : '#library-panel';
  const card = $$(`${panel} .card`).find(node => node.dataset.documentId === doc.id);
  if (!card) throw new Error(`No card for ${doc.id} in ${panel}`);
  const button = [...card.querySelectorAll('button')].find(node => /preview/i.test(node.textContent));
  if (!button) throw new Error(`No Preview button for ${doc.id}`);
  button.click();
  assert(!$('#reader').hidden, `preview opens ${doc.id}`);
  equal(w.__hashes.at(-1), `#doc-${encodeURIComponent(doc.id)}`, `stable document fragment for ${doc.id}`);
}
async function checkBank(expected, label, { expand = true } = {}) {
  const count = Number($('#results-status').textContent.match(/^\s*(\d+)\s+question/i)?.[1]);
  equal(count, expected.length, `${label}: exact result count`);
  assert(!$('#question-results').querySelector('.question'), `${label}: bodies absent before disclosure`);
  assert(!$('#question-results').querySelector('img'), `${label}: no evidence image preloading`);
  if (!expand) return;
  for (let guard = 0; !$('#more-results').hidden; guard++) {
    if (guard > 100) throw new Error('Show more never terminates');
    const before = $$('#question-results .bank-item').length;
    $('#more-results').click();
    assert($$('#question-results .bank-item').length > before, `${label}: Show more advances`);
    assert(!$('#question-results').querySelector('.question, img'), `${label}: Show more remains lazy`);
  }
  const items = $$('#question-results .bank-item');
  equal(items.length, expected.length, `${label}: all matching summaries, no duplicates`);
  for (const item of items) {
    assert(item.tagName === 'DETAILS', `${label}: native question disclosure`);
    item.querySelector('summary').click();
  }
  await until(() => items.every(item => item.querySelector('.question')), `${label}: lazy bodies`);
  equal($$('#question-results .question').map(node => node.dataset.questionId).sort(), ids(expected).sort(), `${label}: exact question IDs`);
  for (const item of items) {
    const body = item.querySelector('.question');
    item.querySelector('summary').click();
    await sleep(0);
    item.querySelector('summary').click();
    await sleep(0);
    equal(item.querySelectorAll('.question').length, 1, `${label}: reopening does not duplicate body ${body.dataset.questionId}`);
  }
}
function pageCheck(doc, pageIndex, questionMap) {
  const expected = doc.question_ids.slice(pageIndex * 8, pageIndex * 8 + 8);
  equal($$('#reader-body .question').map(node => node.dataset.questionId), expected, `${doc.id}: page ${pageIndex + 1} has only current question bodies`);
  const official = expected.filter(id => questionMap.get(id).origin === 'official');
  const entries = $$('#reader-body .source-appendix .source-entry');
  equal(entries.length, official.length, `${doc.id}: appendix bounded to current page`);
  official.forEach((id, index) => {
    const q = questionMap.get(id), entry = entries[index];
    const number = doc.question_ids.indexOf(id) + 1;
    assert(entry.textContent.includes(`Compilation question ${number}`) && entry.textContent.includes(id), `${id}: global compilation number and stable ID in appendix`);
    const values = [...entry.querySelectorAll('dd')].map(node => normalize(node.textContent));
    for (const value of [q.year, q.session, q.question_number, q.original_section, q.marks, q.pages || q.page, q.paper_code]) {
      if (value != null && value !== '') assert(values.includes(normalize(list(value).join(', '))), `${id}: exact source field ${list(value).join(', ')}`);
    }
    assert(entry.textContent.includes('PDF pages (1-based)'), `${id}: one-based source pages labelled`);
    assert([...entry.querySelectorAll('a')].some(a => a.href === new URL(q.source_url, base).href), `${id}: exact official source URL`);
    const body = $$('#reader-body .question').find(node => node.dataset.questionId === id);
    if (q.text) assert([...body.querySelectorAll('.prose')].some(node => node.textContent === q.text), `${id}: unchanged real question text`);
    equal([...body.querySelectorAll('img')].filter(img => !img.closest('.answer')).map(img => img.getAttribute('src')), imagePaths(q), `${id}: original evidence paths and order`);
  });
}
function pageButton(direction) {
  const button = $$('#reader-pagination button').find(node => new RegExp(direction, 'i').test(`${node.textContent} ${node.getAttribute('aria-label') || ''}`));
  if (!button) throw new Error(`Missing ${direction} reader pagination button`);
  return button;
}
async function printClick(trigger) {
  const before = w.__prints.length;
  trigger.click();
  await until(() => w.__prints.length > before || /print stopped/i.test($('#load-status').textContent), 'print image preparation', 22000);
  equal(w.__prints.length, before + 1, 'mocked print invoked exactly once after image preparation');
  assert(w.__prints.at(-1).imagesReady, 'all actual print images complete before dialog');
}
function afterPrint() {
  w.dispatchEvent(new w.Event('afterprint'));
  equal($('#print-output').childElementCount, 0, 'afterprint clears the full print tree');
}
function safetyCheck() {
  assert(!d.querySelector('[onerror], [onload], #test-injected'), 'untrusted markup never becomes active HTML');
  assert(!$$('a[href], iframe[src], img[src]').some(node => /^\s*(javascript|data|vbscript):/i.test(node.getAttribute('href') || node.getAttribute('src'))), 'no executable URL reaches links or media');
  assert(!$$('#coverage a[href]').some(a => /(?:^|\/)research\//.test(a.getAttribute('href')) && !a.getAttribute('href').startsWith('assets/')), 'research-only inventory paths are not download links');
  assert(!w.__alerts.length, 'no injected alert executed');
  assert(!w.__errors.length, `no uncaught browser errors (${w.__errors.join(', ')})`);
}
async function mount(html, fixture, { httpError = false } = {}) {
  // Escape '<' before embedding JSON, including any literal closing-script attack text.
  const mountID = ++mountSequence;
  const payload = JSON.stringify(JSON.stringify(fixture)).replace(/</g, '\\u003c');
  const setup = `<base href="${base.href}"><script>
    window.__mountID=${mountID};
    window.__errors=[];window.__alerts=[];window.__hashes=[];window.__prints=[];
    window.addEventListener('error',e=>window.__errors.push(e.message));
    window.addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
    window.alert=value=>window.__alerts.push(value);
    const nativeFetch=window.fetch.bind(window);
    window.fetch=async(input,options)=>{
      const url=new URL(input instanceof Request?input.url:input,document.baseURI);
      if(url.href!==${JSON.stringify(contentURL.href)}) return nativeFetch(input,options);
      const response=new Response(${payload},{status:${httpError ? 503 : 200},headers:{'Content-Type':'application/json'}});
      const readJSON=response.json.bind(response);
      response.json=async()=>{window.__servedData=await readJSON();return window.__servedData;};
      return response;
    };
    window.history.replaceState=(_state,_title,url)=>window.__hashes.push(url);
    window.confirm=()=>false;
    window.print=()=>window.__prints.push({imagesReady:[...document.querySelectorAll('#print-output img')].every(img=>img.complete&&img.naturalWidth>0)});
  <\/script>`;
  frame.srcdoc = html.replace(/<head\b[^>]*>/i, match => match + setup);
  await until(() => frame.contentWindow?.__mountID === mountID && frame.contentDocument.querySelector('#load-status'), 'srcdoc setup');
  d = frame.contentDocument; w = frame.contentWindow;
  await until(() => /^\s*\d+\s+question/i.test(d.querySelector('#results-status')?.textContent || '') || d.querySelector('#load-status')?.classList.contains('error'), 'library initialization');
  if (!httpError) assert(!$('#load-status').classList.contains('error'), 'real-data fixture initializes successfully');
}

try {
  const response = await fetch(contentURL);
  assert(response.ok, 'fetch authoritative ../data/content.json');
  const real = await response.json();
  const originalQuestions = JSON.stringify(real.questions);
  const originalDocuments = JSON.stringify(real.documents);
  const fixture = copy(real);
  const pyq = fixture.questions.filter(q => q.origin === 'official' && q.exam_type === 'PYQ');
  const sqp = fixture.questions.filter(q => q.origin === 'official' && q.exam_type === 'SQP');
  assert(pyq.length >= 17 && sqp.length >= 17, 'real PYQ and SQP records cover three reader pages');
  const held = sqp.find(q => q.answer_verified === false && !q.answer && !list(q.answer_evidence_images).length && !q.answer_evidence_image && q.answer_verification_note);
  assert(!!held, 'real answer-hold record without answer available for regression');
  const makeCollection = (id, type, scope, questions, year) => ({
    id, kind: 'official', title: `TEST ONLY — ${id}`, status: 'draft',
    collection_type: type, collection_scope: scope, question_ids: ids(questions), sections: [],
    ...(year == null ? {} : { year })
    // Future/test collections intentionally have NO pdf, pdf_pages or pdf_bytes.
  });
  const master = makeCollection('test-pyq-master', 'pyq', 'master', pyq.slice(0, 17));
  const sqpMaster = makeCollection('test-sqp-master', 'sqp', 'master', [held, ...sqp.filter(q => q.id !== held.id).slice(0, 16)]);
  const pyqYear = pyq[0].year, sqpYear = sqp[0].session || sqp[0].year;
  const yearDocs = [
    makeCollection('test-pyq-year', 'pyq', 'year', pyq.filter(q => String(q.year) === String(pyqYear) || String(q.session) === String(pyqYear)), pyqYear),
    makeCollection('test-sqp-year', 'sqp', 'year', sqp.filter(q => String(q.year) === String(sqpYear) || String(q.session) === String(sqpYear)), sqpYear)
  ];
  const mixed = makeCollection('test-legacy-mixed', 'mixed', 'master', [pyq[0], sqp[0]]);
  delete mixed.collection_type; // Classification must be derived, not written into legacy records.
  fixture.documents.push(master, sqpMaster, ...yearDocs, mixed);
  // One explicitly original, non-study safety record preserves V1 escaping/provisional-answer checks.
  // No real question or official provenance is altered for this test.
  const safety = {
    id: 'test-original-safety', origin: 'original', topic: 'TEST ONLY safety', marks: 2, type: 'test', verified: true,
    text: 'TEST ONLY: resistance <img src=x onerror=alert(1)> </script><b id="test-injected">literal</b>',
    answer: 'TEST ONLY provisional answer', answer_verified: false, notes: 'TEST ONLY answer-bearing editorial note',
    evidence_image: ['favicon.svg', { src: 'favicon.svg?second', alt: 'TEST ONLY second illustration' }]
  };
  const safetyDoc = { id: 'test-original-preview', kind: 'practice', title: 'TEST ONLY original safety checks', status: 'ready', question_ids: [safety.id], sections: [] };
  const unsafeDoc = { id: 'test-unsafe-url', kind: 'notes', title: 'TEST ONLY unsafe URL', status: 'draft', question_ids: [], sections: [], pdf: 'javascript:alert(1)' };
  fixture.questions.push(safety);
  fixture.documents.push(safetyDoc, unsafeDoc);
  const specialDocs = Array.from({ length: 4 }, (_, i) => ({
    id: 'test-special-group-' + i, kind: 'practice', status: 'draft',
    title: i === 1 ? 'Special39 / competency practice — TEST ONLY' : 'TEST ONLY practice grouping',
    ...(i === 0 ? { practice_series: 'special39' } : {}),
    question_ids: [safety.id], sections: []
  }));
  specialDocs[2].id = 'special-39-03'; specialDocs[3].id = 'special-39-04';
  // Do not collide with a future real additive release.
  fixture.documents.push(...specialDocs.filter(doc => !fixture.documents.some(realDoc => realDoc.id === doc.id)));
  assert(fixture.documents.length > 21 && fixture.documents.filter(doc => doc.status === 'ready').length > 21, 'test inventory exceeds old 21-document ceiling including ready count');
  equal(JSON.stringify(fixture.questions.slice(0, real.questions.length)), originalQuestions, 'fixture preserves every real question byte-for-byte as JSON');
  equal(JSON.stringify(fixture.documents.slice(0, real.documents.length)), originalDocuments, 'fixture preserves all published documents and PDFs');
  assert([master, sqpMaster, ...yearDocs, mixed].every(doc => !Object.hasOwn(doc, 'pdf')), 'future collections omit PDF rather than point at a fake file');
  const questionMap = new Map(fixture.questions.map(q => [q.id, q]));
  const htmlResponse = await fetch(new URL('index.html', base));
  assert(htmlResponse.ok, 'fetch current production HTML');
  const html = await htmlResponse.text();
  await mount(html, fixture);

  $('#tab-practice').click();
  assert(!!d.querySelector('#special39-practice'), 'Special39 practice has a prominent dedicated grouping');
  const specialExpected = fixture.documents.filter(doc => doc.kind === 'practice' && (doc.practice_series === 'special39' || /^special-39-0[1-4]$/.test(doc.id) || /special\s*39/i.test(doc.title)));
  equal(cardIDs('#special39-practice'), specialExpected.map(doc => doc.id).sort(), 'Special39 metadata, titles and stable IDs group only supplied documents');
  for (const doc of specialExpected) {
    const card = $$('#special39-practice .card').find(card => card.dataset.documentId === doc.id);
    assert(card.textContent.includes(doc.question_ids.length + ' questions'), 'Special39 count comes from actual references, not series name');
  }
  assert(!d.querySelector('#special39-practice [data-document-id="original-practice-01"]'), 'legacy original practice stays separate');
  $('#tab-official').click();
  const ready = fixture.documents.filter(doc => doc.status === 'ready').length;
  const summaryNumbers = $('#inventory-summary').textContent.match(/\d+/g)?.map(Number) || [];
  assert(summaryNumbers.includes(ready) && summaryNumbers.includes(fixture.documents.length), 'inventory displays actual ready and total counts beyond 21');
  assert(!/of 21|\/21/.test($('#inventory-summary').textContent), 'inventory does not retain fixed 21 denominator');
  equal($('#bank-tab-pyq').dataset.bank, 'PYQ', 'PYQ bank authoritative data-bank');
  equal($('#bank-tab-sqp').dataset.bank, 'SQP', 'SQP bank authoritative data-bank');
  equal($('#bank-tab-original').dataset.bank, 'original', 'original bank data-bank');
  equal($('#bank-tab-all').dataset.bank, 'all', 'all bank data-bank');
  equal($('#bank-tab-pyq').getAttribute('aria-selected'), 'true', 'default question bank is PYQ');
  assert(!d.querySelector('#origin'), 'obsolete origin select removed');
  await checkBank(pyq, 'default PYQ', { expand: false });
  $('#bank-tab-pyq').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  equal($('#bank-tab-sqp').getAttribute('aria-selected'), 'true', 'bank arrow navigation selects SQP');
  equal(d.activeElement.id, 'bank-tab-sqp', 'bank arrow navigation moves focus');
  equal($('#tab-official').getAttribute('aria-selected'), 'true', 'bank tabs do not deselect library tabs');

  for (const [bank, expected] of [['PYQ', pyq], ['SQP', sqp], ['original', fixture.questions.filter(q => q.origin === 'original')], ['all', fixture.questions]]) {
    await resetBank(bank);
    await checkBank(expected, `${bank} bank`, { expand: false });
  }
  // Each select is checked independently against exact authoritative values, not title/filename inference.
  const filterCases = [
    ['#year', String(pyq[0].year), q => String(q.year) === String(pyq[0].year) || String(q.session) === String(pyq[0].year)],
    ['#year', String(sqp[0].session), q => String(q.year) === String(sqp[0].session) || String(q.session) === String(sqp[0].session)],
    ['#session', String(pyq[0].session), q => String(q.session) === String(pyq[0].session)],
    ['#paper-code', String(pyq.find(q => q.paper_code || q.set).paper_code || pyq.find(q => q.paper_code || q.set).set), null],
    ['#topic', safety.topic, q => q.topic === safety.topic],
    ['#marks', '2', q => String(q.marks) === '2']
  ];
  for (const [selector, value, predicate] of filterCases) {
    await resetBank();
    change(selector, value);
    const expected = fixture.questions.filter(predicate || (q => String(q.paper_code || q.set) === value));
    assert(expected.length > 0 && expected.length < fixture.questions.length, `${selector} fixture is discriminating`);
    await checkBank(expected, `${selector} exact ${value}`);
  }
  await resetBank('PYQ');
  const target = pyq.find(q => q.year && q.session && (q.paper_code || q.set) && q.topic && q.marks != null);
  assert(!!target, 'real question supports combined exact filters');
  for (const [selector, value] of [['#year', target.year], ['#session', target.session], ['#paper-code', target.paper_code || target.set], ['#topic', target.topic], ['#marks', target.marks]]) change(selector, value);
  const combined = pyq.filter(q => (String(q.year) === String(target.year) || String(q.session) === String(target.year)) && String(q.session) === String(target.session) && String(q.paper_code || q.set) === String(target.paper_code || target.set) && q.topic === target.topic && String(q.marks) === String(target.marks));
  await checkBank(combined, 'combined bank/year/session/code/topic/marks');
  change('#search', 'no-such-token-v2-harness');
  await checkBank([], 'no-results search');
  await resetBank();
  await checkBank(fixture.questions, 'reset restores all bank results', { expand: false });
  change('#search', `  ${target.id.toUpperCase()}   `);
  const searchIDs = fixture.questions.filter(q => [q.id, q.source_id, q.exam_type, q.set, q.text, q.topic, q.type, q.session, q.year, q.question_number, q.source_title, q.paper_code, ...list(q.options)].join(' ').toLowerCase().includes(target.id.toLowerCase()));
  await checkBank(searchIDs, 'case-insensitive trimmed stable-ID search');
  await resetBank('PYQ');

  equal($('#collection-type').value, 'pyq', 'default collection filter is pyq');
  equal([...$('#collection-type').options].map(option => option.value).sort(), ['all', 'mixed', 'pyq', 'sqp'], 'collection filter options');
  const collections = fixture.documents.filter(isCollection);
  equal(cardIDs('#collections-panel'), collections.filter(doc => collectionType(doc, questionMap) === 'pyq').map(doc => doc.id).sort(), 'default PYQ master/year cards only');
  for (const type of ['sqp', 'mixed', 'all', 'pyq']) {
    change('#collection-type', type);
    equal(cardIDs('#collections-panel'), collections.filter(doc => type === 'all' || collectionType(doc, questionMap) === type).map(doc => doc.id).sort(), `collection ${type} exact membership`);
  }
  $('#tab-official').click();
  equal(cardIDs('#library-panel'), fixture.documents.filter(doc => doc.kind === 'official' && !isCollection(doc)).map(doc => doc.id).sort(), 'library official tab excludes master/year collections');
  const legacyMixed = real.documents.find(doc => doc.kind === 'official' && !doc.collection_type && collectionType(doc, questionMap) === 'mixed');
  assert(!!legacyMixed, 'real legacy mixed compilation available');
  const legacyCard = $$('#library-panel .card').find(card => card.dataset.documentId === legacyMixed.id);
  assert(/mixed/i.test(legacyCard.textContent), 'legacy mixed compilation remains visibly mixed');
  $('#tab-practice').click();
  equal(cardIDs('#library-panel'), fixture.documents.filter(doc => doc.kind === 'practice').map(doc => doc.id).sort(), 'practice category exact cards');
  $('#tab-practice').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  equal($('#tab-notes').getAttribute('aria-selected'), 'true', 'library arrow navigation selects notes');
  equal(d.activeElement.id, 'tab-notes', 'library keyboard navigation moves focus');
  equal($('#bank-tab-pyq').getAttribute('aria-selected'), 'true', 'library tabs do not deselect question bank');
  equal(cardIDs('#library-panel'), fixture.documents.filter(doc => doc.kind === 'notes').map(doc => doc.id).sort(), 'notes category exact cards');
  $('#tab-sources').click();
  equal(cardIDs('#library-panel'), [], 'sources tab has provenance rather than document cards');

  preview(master);
  assert(!d.querySelector('#reader-actions a[download]'), 'future collection has no download link');
  assert(!d.querySelector('#pdf-preview iframe, iframe#pdf-preview'), 'PDF is not preloaded');
  assert(/print.*save as pdf/i.test($('#reader-actions').textContent), 'missing PDF retains Print / Save as PDF fallback');
  equal($('#reader-actions button').textContent.trim(), 'Print full document', 'explicit full-document print action');
  pageCheck(master, 0, questionMap);
  equal($('#reader-page').options.length, 3, '17 questions produce three reader pages');
  assert(pageButton('prev').disabled && !pageButton('next').disabled, 'first-page pagination boundaries');
  pageButton('next').click();
  pageCheck(master, 1, questionMap);
  const finalOption = [...$('#reader-page').options].at(-1).value;
  change('#reader-page', finalOption);
  pageCheck(master, 2, questionMap);
  assert(pageButton('next').disabled && !pageButton('prev').disabled, 'last-page pagination boundaries');
  pageButton('prev').click();
  pageCheck(master, 1, questionMap);
  await printClick($('#reader-actions button'));
  equal($$('#print-output .question').map(node => node.dataset.questionId), master.question_ids, 'print includes all 17 questions while reader is on page two');
  equal($$('#print-output .source-appendix .source-entry').length, 17, 'full source appendix included in individual print');
  assert(!d.querySelector('#print-output .answer'), 'questions-only print excludes answers');
  pageCheck(master, 1, questionMap);
  afterPrint();

  preview(sqpMaster);
  pageCheck(sqpMaster, 0, questionMap);
  const heldBody = $$('#reader-body .question').find(node => node.dataset.questionId === held.id);
  assert(heldBody.textContent.includes(held.answer_verification_note), 'answer hold reason visible even with no answer payload');
  assert(!heldBody.querySelector('.answer'), 'held real question does not acquire a fabricated answer');
  $('#print-answers').checked = true;
  await printClick($('#reader-actions button'));
  equal($$('#print-output .question').map(node => node.dataset.questionId), sqpMaster.question_ids, 'answer-inclusive print is still the full document');
  assert(!!d.querySelector('#print-output .answer[open]'), 'answer-inclusive print expands available answers');
  const heldPrint = $$('#print-output .question').find(node => node.dataset.questionId === held.id);
  assert(!heldPrint.querySelector('.answer') && heldPrint.textContent.includes(held.answer_verification_note), 'answer-inclusive print preserves hold reason without inventing answer');
  afterPrint();

  const zoomButton = $('#reader-body .image-zoom');
  assert(zoomButton.tagName === 'BUTTON' && !!zoomButton.querySelector('img'), 'image zoom is an accessible button wrapping original image');
  const originalImage = zoomButton.querySelector('img').src;
  zoomButton.click();
  const dialog = $('#image-dialog');
  assert(dialog.tagName === 'DIALOG' && dialog.open, 'original image opens native dialog');
  equal(dialog.querySelector('img').src, originalImage, 'zoom reuses the same original asset');
  await until(() => dialog.querySelector('img').complete && dialog.querySelector('img').naturalWidth > 0, 'zoom image decode');
  $('#zoom-actual').click();
  assert(/100\s*%/.test($('#zoom-status').textContent), 'actual-size zoom reports 100%');
  const actualStatus = $('#zoom-status').textContent;
  $('#zoom-in').click();
  assert($('#zoom-status').textContent !== actualStatus, 'zoom in updates scale status');
  $('#zoom-out').click();
  equal($('#zoom-status').textContent, actualStatus, 'zoom out reverses zoom in');
  $('#zoom-fit').click();
  assert(!!$('#zoom-status').textContent.trim(), 'fit reports zoom status');
  $('#zoom-close').click();
  assert(!dialog.open, 'zoom close button closes dialog');
  // Synthetic keydown/cancel does not trigger the browser's trusted Escape default.
  // The parent browser runner must reopen this native dialog and send real Escape.

  const pdfDoc = real.documents.find(doc => doc.pdf && !isCollection(doc));
  assert(!!pdfDoc, 'real built chapter PDF available for opt-in preview');
  preview(pdfDoc);
  assert(!d.querySelector('#pdf-preview iframe, iframe#pdf-preview'), 'existing PDF remains unloaded until opt-in');
  equal($('#pdf-open').target, '_blank', 'PDF open link uses new tab');
  equal($('#pdf-open').href, new URL(pdfDoc.pdf, base).href, 'PDF open fallback retains real chapter PDF');
  assert($('#pdf-open').rel.includes('noopener'), 'PDF new-tab link protects opener');
  assert($$('#reader-actions a[download]').some(a => a.href === new URL(pdfDoc.pdf, base).href), 'real PDF download fallback available');
  $('#pdf-toggle').click();
  const embedded = d.querySelector('#pdf-preview iframe, iframe#pdf-preview');
  assert(!!embedded, 'PDF iframe created only on opt-in');
  equal(embedded.src.split('#')[0], new URL(pdfDoc.pdf, base).href, 'embed uses real chapter PDF, not a full Science source');
  $('#pdf-toggle').click();
  assert(!d.querySelector('#pdf-preview iframe, iframe#pdf-preview'), 'PDF toggle removes iframe rather than hiding it');
  $('#pdf-toggle').click();
  preview(master);
  assert(!d.querySelector('#pdf-preview iframe, iframe#pdf-preview'), 'switching documents removes previous PDF iframe');
  pageCheck(master, 0, questionMap);
  preview(pdfDoc); $('#pdf-toggle').click(); $('#close-reader').click();
  assert($('#reader').hidden && !d.querySelector('#pdf-preview iframe, iframe#pdf-preview'), 'closing reader removes PDF iframe');

  preview(safetyDoc);
  assert(!$('#reader-body').textContent.includes(safety.notes), 'answer-bearing original notes absent before answer disclosure');
  assert($('#reader-body').textContent.includes(safety.text), 'untrusted original text remains literal including closing-script text');
  equal($$('#reader-body img').map(img => img.getAttribute('src')), ['favicon.svg', 'favicon.svg?second'], 'mixed string/object image arrays render in order without injected HTML');
  assert($('#reader-body').textContent.includes('Answer verification pending'), 'unverified original answer warning retained');
  assert(!d.querySelector('#reader-actions a[download]'), 'original document without PDF has no download link');
  await printClick($('#reader-actions button'));
  assert(!d.querySelector('#print-output .answer'), 'original questions-only print excludes provisional answer');
  assert(!$('#print-output').textContent.includes(safety.notes), 'questions-only print excludes answer-bearing original notes');
  afterPrint();
  $('#print-answers').checked = true;
  await printClick($('#reader-actions button'));
  assert(!!d.querySelector('#print-output .answer[open]'), 'original answer-inclusive print expands provisional answer');
  assert($('#print-output .answer').textContent.includes(safety.notes), 'answer-inclusive print retains original editorial notes');
  assert($('#print-output').textContent.includes('Answer verification pending'), 'provisional warning survives printing');
  afterPrint();
  preview(unsafeDoc);
  assert(!d.querySelector('#reader-actions a[download], #reader-actions #pdf-open, #reader-actions #pdf-toggle'), 'unsafe PDF URL is not offered as embed/open/download');
  safetyCheck();

  w.confirm = () => false;
  await printClick($('#print-all'));
  const readyDocs = fixture.documents.filter(doc => doc.status === 'ready');
  equal($$('#print-output .print-document').length, readyDocs.length, 'print all selects every ready document beyond 21 and excludes drafts');
  equal($$('#print-output .question').map(node => node.dataset.questionId), readyDocs.flatMap(doc => doc.question_ids), 'print all includes exact full question sequence for all ready documents');
  assert(!d.querySelector('#print-output .answer'), 'print-all Cancel means questions-only, not cancelled printing');
  afterPrint();

  // Failure injection is confined to the image API in this iframe, never the data or image files.
  preview(safetyDoc);
  const nativeDecode = w.HTMLImageElement.prototype.decode;
  w.HTMLImageElement.prototype.decode = function () {
    if (this.closest('#print-output')) {
      Object.defineProperty(this, 'naturalWidth', { configurable: true, get: () => 0 });
      return Promise.reject(new Error('TEST ONLY image decoding failure'));
    }
    return nativeDecode.call(this);
  };
  const printsBeforeFailure = w.__prints.length;
  $('#reader-actions button').click();
  await until(() => /print stopped/i.test($('#load-status').textContent), 'failed image stops print', 22000);
  equal(w.__prints.length, printsBeforeFailure, 'incomplete evidence prevents print dialog');
  w.HTMLImageElement.prototype.decode = nativeDecode;
  afterPrint();
  await printClick($('#reader-actions button'));
  afterPrint();
  assert(d.documentElement.scrollWidth <= w.innerWidth, 'no document horizontal overflow at iframe viewport');
  equal(JSON.stringify(w.__servedData.questions.slice(0, real.questions.length)), originalQuestions, 'UI filtering/reading/printing does not mutate real question data');
  equal(JSON.stringify(w.__servedData.documents.slice(0, real.documents.length)), originalDocuments, 'UI classification does not mutate legacy document data');
  assert(!Object.hasOwn(w.__servedData.documents.find(doc => doc.id === mixed.id), 'collection_type'), 'derived mixed collection classification is not written back');
  safetyCheck();

  // Optional ledger branch: test-only rows, real provenance values, explicit non-certification.
  const withLedger = copy(fixture);
  const ledgerRows = [
    { id: 'test-ledger-zero', exam_type: 'PYQ', year: pyq[0].year, session: pyq[0].session, set: pyq[0].paper_code || pyq[0].set,
      status: 'TEST ONLY downloaded, not reviewed', reviewed: false, exhaustive: false, published_questions: 0, verified_questions: 0, held_questions: 0,
      source_url: pyq[0].source_url, note: 'TEST ONLY counting rule: distinct records, not additive marks. <img src=x onerror=alert(1)>' },
    { id: 'test-ledger-positive', exam_type: 'SQP', year: sqp[0].year, session: sqp[0].session, set: 'TEST ONLY ledger set',
      status: 'TEST ONLY supplied claim, not UI certification', reviewed: true, exhaustive: true, published_questions: 7, verified_questions: 5, held_questions: 2,
      source_url: sqp[0].source_url, note: 'TEST ONLY positive-value rendering; no claim about the published archive.' }
  ];
  withLedger.coverage.source_ledger = ledgerRows;
  await mount(html, withLedger);
  for (const row of ledgerRows) {
    // Locate the smallest rendered container with both row identity and status, independent of table/card layout.
    const candidates = [...$('#coverage').querySelectorAll('*')].filter(node => node.textContent.includes(row.id) && node.textContent.includes(row.status));
    const rendered = candidates.sort((a, b) => a.textContent.length - b.textContent.length)[0];
    assert(!!rendered, `${row.id}: ledger row identity and status visible`);
    const rowText = normalize(rendered.textContent);
    for (const key of ['id', 'exam_type', 'year', 'session', 'set', 'status', 'note']) assert(rowText.includes(normalize(row[key])), `${row.id}: ledger ${key} preserved`);
    for (const key of ['reviewed', 'exhaustive', 'published_questions', 'verified_questions', 'held_questions']) {
      const label = key.replaceAll('_', '[\\s_-]*');
      // Accept plain boolean spelling or accessible yes/no, but require each field's own label/value.
      const value = typeof row[key] === 'boolean' ? (row[key] ? '(?:true|yes)' : '(?:false|no)') : String(row[key]);
      assert(new RegExp(`${label}\\s*[:=·–—-]?\\s*${value}(?![\\w])`, 'i').test(rowText), `${row.id}: explicit ${key}=${row[key]} (false/zero not dropped)`);
    }
    assert([...rendered.querySelectorAll('a')].some(a => a.href === row.source_url), `${row.id}: ledger source URL exact`);
  }
  for (const limitation of real.coverage.limitations) assert($('#limitations').textContent.includes(limitation), 'ledger does not replace existing coverage limitation');
  safetyCheck();

  const withoutLedger = copy(fixture);
  delete withoutLedger.coverage.source_ledger;
  await mount(html, withoutLedger);
  const coverageText = normalize($('#coverage').textContent);
  assert(/inventor/i.test(coverageText) && /publish/i.test(coverageText), 'without optional ledger, research inventory and publication are separately labelled');
  for (const year of Object.keys(real.coverage.source_inventory.pyq)) assert(coverageText.includes(year), `fallback coverage retains PYQ inventory year ${year}`);
  for (const source of real.coverage.source_inventory.sqp.documents) assert(coverageText.includes(source.session || source.document_key), `fallback coverage retains SQP session ${source.session || source.document_key}`);
  assert(/not.*(?:review|verif)|(?:review|verif).*not/i.test(coverageText), 'fallback inventory does not promote downloaded sources to verified coverage');
  safetyCheck();

  await mount(html, fixture, { httpError: true });
  assert($('#load-status').classList.contains('error') && $('#load-status').getAttribute('role') === 'alert', 'HTTP failure is an accessible load error');
  assert($('#load-status').textContent.includes('503') && /retry/i.test($('#load-status').textContent), 'HTTP failure exposes status and Retry recovery');
  assert(/unavailable.*not verified/i.test($('#inventory-summary').textContent), 'load failure never claims verified content');
  equal(JSON.stringify(real.questions), originalQuestions, 'authoritative source snapshot unchanged at end of harness');
  result.textContent = messages.slice(-8).join('\n') + `\n\n${messages.length} checks passed.\nPrint dialog mocked; real trusted Escape and PDF rendering remain parent browser checks.`;
  result.dataset.status = 'passed';
} catch (error) {
  result.textContent = messages.slice(-8).join('\n') + '\nFAIL ' + error.message;
  result.dataset.status = 'failed';
  console.error(error);
}
