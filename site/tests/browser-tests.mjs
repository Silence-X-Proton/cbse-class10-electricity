// In-memory synthetic original content plus real inspected source metadata; no invented official question.
const base = new URL('../', import.meta.url);
const fixture = {
  schema_version: 1, meta: { chapter: 'Electricity', title: 'TEST ONLY — original UI fixtures', updated: 'TEST', intro: 'Synthetic test content. Not a published paper.' },
  coverage: { summary: 'TEST coverage', topics: [{ name: 'Resistance', status: 'partial' }], limitations: ['TEST only'] }, sources: [],
  questions: [{ id: 'test-original', origin: 'original', text: 'TEST ONLY: resistance <img src=x onerror=alert(1)>', topic: 'Resistance', marks: 2, type: 'numerical', verified: true, answer: 'TEST ONLY provisional answer', answer_verified: false, evidence_image: ['favicon.svg', { src: 'favicon.svg?second', alt: 'TEST illustration two' }] }],
  documents: [{ id: 'test-practice', kind: 'practice', title: 'TEST ONLY original practice', status: 'ready', question_ids: ['test-original'], sections: [] }, { id: 'test-notes', kind: 'notes', title: 'TEST ONLY notes', status: 'ready', question_ids: [], sections: [{ heading: 'TEST heading', paragraphs: ['TEST note text'], bullets: ['TEST bullet'] }] }]
};
// Real metadata from research/sqp/batch_early.json; no invented source question or diagram.
fixture.questions.push({ id: 'test-real-source-metadata', origin: 'official', text: '', topic: 'Resistance', marks: 3, type: 'short3', verified: false, source_title: 'Sample Question Paper 2017-18 — Science — Class – X', session: '2017-18', year: '2017-18', exam_type: 'SQP', question_number: '7', original_section: 'SECTION – A', pages: [1], source_url: 'https://cbseacademic.nic.in/web_material/SQP/CLASS_X_2017_18/Science_SQP.pdf' });
fixture.documents.push({ id: 'test-citation', kind: 'official', title: 'TEST ONLY — real source metadata, content omitted', status: 'draft', question_ids: ['test-real-source-metadata'] });
const result = document.querySelector('#result');
const frame = document.querySelector('#site');
const messages = [];
const assert = (condition, label) => { if (!condition) throw new Error(label); messages.push(`PASS ${label}`); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  let html = await (await fetch(new URL('index.html', base))).text();
  const setup = `<base href="${base.href}"><script>window.__errors=[];window.addEventListener('error',e=>window.__errors.push(e.message));window.fetch=async()=>new Response(${JSON.stringify(JSON.stringify(fixture))},{status:200,headers:{'Content-Type':'application/json'}});window.__hashes=[];window.history.replaceState=(_state,_title,url)=>window.__hashes.push(url);window.__prints=0;window.print=()=>window.__prints++;<\/script>`;
  html = html.replace('<head>', '<head>' + setup);
  frame.srcdoc = html;
  for (let i = 0; i < 100 && !frame.contentDocument.querySelector('#inventory-summary')?.textContent.includes('2 of 21'); i++) await sleep(50);
  const d = frame.contentDocument, w = frame.contentWindow;
  assert(d.querySelector('#inventory-summary')?.textContent.includes('2 of 21'), 'actual ready counts derive from data');
  d.querySelector('#tab-practice').click();
  assert(d.querySelectorAll('.card').length === 1, 'practice category renders card');
  d.querySelector('#tab-practice').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  assert(d.querySelector('#tab-notes').getAttribute('aria-selected') === 'true', 'arrow-key tab navigation');
  assert(d.activeElement.id === 'tab-notes', 'keyboard navigation moves focus');
  d.querySelector('#tab-practice').click(); d.querySelector('.card button').click();
  assert(!d.querySelector('#reader').hidden, 'preview opens');
  assert(w.__hashes.at(-1) === '#doc-test-practice', 'stable document fragment requested');
  assert(d.querySelector('#reader-body').textContent.includes('<img src=x onerror=alert(1)>'), 'untrusted text stays literal');
  assert(d.querySelectorAll('#reader-body img').length === 2, 'image arrays render in order without injected HTML');
  assert(d.querySelector('#reader-body').textContent.includes('Answer verification pending'), 'unverified answer warning retained');
  assert(!d.querySelector('#reader-actions a[download]'), 'missing PDF produces no download link');
  d.querySelector('#search').value = 'no-such-token'; d.querySelector('#search').dispatchEvent(new w.Event('input', { bubbles: true }));
  assert(d.querySelector('#results-status').textContent.startsWith('0 questions'), 'no-results search');
  d.querySelector('#search-form').reset(); await sleep(10);
  assert(d.querySelector('#results-status').textContent.startsWith('2 questions'), 'reset restores results');
  d.querySelector('#marks').value = '2'; d.querySelector('#marks').dispatchEvent(new w.Event('change', { bubbles: true }));
  assert(d.querySelector('#results-status').textContent.startsWith('1 question'), 'marks filter');
  d.querySelector('#reader-actions button').click();
  for (let i = 0; i < 100 && !w.__prints; i++) await sleep(50);
  assert(w.__prints === 1, 'print waits for images then invokes dialog');
  assert(!d.querySelector('#print-output .answer'), 'questions-only print excludes answers');
  w.dispatchEvent(new w.Event('afterprint'));
  d.querySelector('#print-answers').checked = true; d.querySelector('#reader-actions button').click();
  for (let i = 0; i < 100 && w.__prints < 2; i++) await sleep(50);
  assert(!!d.querySelector('#print-output .answer[open]'), 'answer-inclusive print expands answer');
  w.dispatchEvent(new w.Event('afterprint'));
  w.confirm = () => false; d.querySelector('#print-all').click();
  for (let i = 0; i < 100 && w.__prints < 3; i++) await sleep(50);
  assert(d.querySelectorAll('#print-output .print-document').length === 2, 'print all selects every ready document');
  w.dispatchEvent(new w.Event('afterprint'));
  d.querySelector('#tab-official').click(); d.querySelector('.card button').click();
  const appendix = d.querySelector('#reader-body .source-appendix');
  assert(!!appendix, 'official preview has appended source citations');
  for (const value of ['2017-18', 'SECTION – A', 'Compilation question 1', 'PDF pages (1-based)']) assert(appendix.textContent.includes(value), 'appendix preserves ' + value);
  const fields = [...appendix.querySelectorAll('dd')].map(n => n.textContent);
  assert(fields.includes('7') && fields.includes('3') && fields.includes('1'), 'appendix preserves original question, marks and PDF page');
  assert(appendix.querySelector('a').href === fixture.questions[1].source_url, 'appendix preserves exact official source URL');
  d.querySelector('#reader-actions button').click();
  for (let i = 0; i < 100 && w.__prints < 4; i++) await sleep(50);
  assert(!!d.querySelector('#print-output .source-appendix'), 'source appendix included in individual print');
  w.dispatchEvent(new w.Event('afterprint'));
  assert(d.documentElement.scrollWidth <= w.innerWidth, 'no document horizontal overflow at iframe viewport');
  assert(!w.__errors.length, `no uncaught browser errors (${w.__errors.join(', ')})`);
  result.textContent = messages.join('\n') + `\n\n${messages.length} checks passed.`;
  result.dataset.status = 'passed';
} catch (error) { result.textContent = messages.join('\n') + '\nFAIL ' + error.message; result.dataset.status = 'failed'; console.error(error); }
