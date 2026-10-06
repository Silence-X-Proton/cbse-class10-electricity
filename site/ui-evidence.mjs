import { array, display, safeURL } from './content-utils.mjs';

const text = (tag, value, className = '') => {
  const node = document.createElement(tag); node.textContent = value ?? ''; node.className = className; return node;
};

// Native modal semantics supply focus containment and Escape; retain the exact invoking control.
export function evidenceViewer() {
  const dialog = document.querySelector('#image-dialog');
  const img = dialog.querySelector('#zoom-image');
  const viewport = dialog.querySelector('#zoom-viewport');
  let invoker, scale = 1, fit = true;
  function resize() {
    if (!img.naturalWidth || !dialog.open) return;
    if (fit) scale = Math.min((viewport.clientWidth - 24) / img.naturalWidth, (viewport.clientHeight - 24) / img.naturalHeight, 1);
    img.style.width = `${img.naturalWidth * scale}px`;
    dialog.querySelector('#zoom-status').textContent = `${fit ? 'Fit · ' : ''}${Math.round(scale * 100)}%`;
  }
  img.addEventListener('load', resize);
  img.addEventListener('error', () => { dialog.querySelector('#zoom-status').textContent = 'Image unavailable. Try the original link.'; });
  window.addEventListener('resize', resize);
  dialog.querySelector('#zoom-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { img.removeAttribute('src'); document.body.classList.remove('zoom-open'); if (invoker?.isConnected) invoker.focus({ preventScroll: true }); });
  for (const [id, action] of [['zoom-fit', () => { fit = true; }], ['zoom-actual', () => { fit = false; scale = 1; }], ['zoom-in', () => { fit = false; scale = Math.min(4, scale * 1.25); }], ['zoom-out', () => { fit = false; scale = Math.max(0.1, scale / 1.25); }]]) {
    dialog.querySelector(`#${id}`).addEventListener('click', () => { action(); resize(); });
  }
  return (item, label, trigger) => {
    const url = safeURL(item.src); if (!url) return;
    invoker = trigger; fit = true; img.alt = item.alt || label;
    dialog.querySelector('#zoom-title').textContent = label;
    dialog.querySelector('#zoom-original').href = url;
    dialog.querySelector('#zoom-status').textContent = 'Loading original…';
    img.style.width = ''; img.src = url;
    document.body.classList.add('zoom-open'); dialog.showModal(); viewport.scrollTo(0, 0); resize();
  };
}

function fields(entries) {
  const grid = text('dl', '', 'source-grid');
  for (const [label, value] of entries) {
    if (value === undefined || value === null) continue;
    const pair = document.createElement('div'); pair.append(text('dt', label + ': '), text('dd', display(value) + ' ')); grid.append(pair);
  }
  return grid;
}
function citation(parent, url) {
  const safe = safeURL(url);
  if (safe && /^https?:/i.test(safe)) {
    const a = text('a', 'Official source ↗'); a.href = safe; a.target = '_blank'; a.rel = 'noopener noreferrer'; parent.append(a);
  }
}
function record(title, entries, note, url) {
  const node = text('article', '', 'coverage-record'); node.append(text('h4', title), fields(entries));
  if (note) node.append(text('p', note, 'small prose'));
  citation(node, url); return node;
}
function pagedRecords(parent, rows, render) {
  const body = document.createElement('div'); const controls = text('div', '', 'pagination'); let page = 0;
  const previous = text('button', 'Previous sources', 'button secondary'); previous.type = 'button';
  const next = text('button', 'Next sources', 'button secondary'); next.type = 'button';
  const status = text('span', '', 'small'); status.setAttribute('role', 'status');
  const update = () => {
    body.replaceChildren(...rows.slice(page * 12, (page + 1) * 12).map(render));
    previous.disabled = page === 0; next.disabled = (page + 1) * 12 >= rows.length;
    status.textContent = `${rows.length ? page * 12 + 1 : 0}–${Math.min((page + 1) * 12, rows.length)} of ${rows.length} source entries`;
  };
  previous.addEventListener('click', () => { page--; update(); }); next.addEventListener('click', () => { page++; update(); });
  controls.append(previous, status, next); parent.append(controls, body); update();
}
export function renderSourceCoverage(parent, data) {
  parent.replaceChildren(text('h3', 'Source coverage ledger'));
  parent.append(text('p', 'Research inventory is not the published bank. Downloaded ≠ reviewed ≠ publication-verified. Status and review fields below are supplied editorial claims, not UI certification. Counts describe records, not additive exam marks; alternatives may share a parent question.', 'small'));
  const coverage = data.coverage || {};
  const official = data.questions.filter(q => q.origin === 'official');
  if (Array.isArray(coverage.source_ledger)) {
    parent.append(text('p', 'Supplied source ledger · counts use the counting rule disclosed in its notes and coverage limitations.', 'small'));
    if (!coverage.source_ledger.length) parent.append(text('p', 'No source ledger entries supplied. No completeness claim is made.'));
    pagedRecords(parent, coverage.source_ledger, row => record(`${row.exam_type} · ${row.year} · ${row.id}`, [
      ['Session', row.session], ['Set', row.set], ['Status', row.status], ['Reviewed', row.reviewed], ['Exhaustive', row.exhaustive],
      ['Published questions', row.published_questions], ['Verified questions', row.verified_questions], ['Held questions', row.held_questions]
    ], row.note, row.source_url));
    return;
  }
  const inventory = coverage.source_inventory || {};
  parent.append(text('h4', 'PYQ years · research vs published'));
  const years = Object.entries(inventory.pyq || {});
  if (!years.length) parent.append(text('p', 'PYQ source inventory not supplied.'));
  pagedRecords(parent, years, ([year, row]) => {
    const published = official.filter(q => q.exam_type === 'PYQ' && String(q.year) === String(row.year ?? year));
    const statuses = [...new Set(array(row.qp_inventory).flatMap(r => array(r.inventory_statuses)))];
    const yearNotes = Object.values(row.source_coverage_notes || {}).flatMap(r => array(r.years)).filter(r => String(r.year) === String(row.year ?? year));
    return record(`PYQ · ${row.year ?? year}`, [
      ['Inventoried sets (research)', row.inventoried_qp_sets], ['Accepted records (research)', row.represented_count], ['Verified records (research)', row.verified_count],
      ['Published questions (distinct bank IDs)', published.length], ['Published verified questions', published.filter(q => q.verified === true).length],
      ['Published answer holds', published.filter(q => q.answer_verified === false).length], ['Exhaustive', row.exhaustive], ['Inventory gap', row.inventory_gap],
      ['Missing / unprocessed sets', Array.isArray(row.missing_unprocessed_sets) ? row.missing_unprocessed_sets.length : undefined],
      ['Unresolved quarantine (research)', row.unresolved_quarantine_count], ['Inventory status', statuses.length ? statuses.join('; ') : 'Not recorded'],
      ['Year status (research)', yearNotes.map(r => r.status).filter(Boolean).join('; ') || 'Not recorded']
    ], array(row.limitations).join(' '));
  });
  parent.append(text('h4', 'SQP documents · declared review scope'));
  const sqp = inventory.sqp || {};
  if (sqp.scope) parent.append(text('p', sqp.scope, 'small'));
  if (sqp.record_counting) parent.append(text('p', sqp.record_counting, 'small'));
  pagedRecords(parent, array(sqp.documents), row => {
    // Exact URLs identify documents; a shared session alone would double-count Term I/II.
    const published = official.filter(q => q.exam_type === 'SQP' && q.source_url === row.source_url);
    return record(`SQP · ${row.document_key || row.session || 'Not recorded'}`, [
      ['Session', row.session], ['Term', row.term], ['Research records', row.record_count], ['PDF pages', row.pages], ['Reviewed page range (supplied)', row.page_range_reviewed],
      ['Complete within declared scope', row.complete_within_declared_scope], ['Published questions (distinct bank IDs)', published.length],
      ['Published verified questions', published.filter(q => q.verified === true).length], ['Published answer holds', published.filter(q => q.answer_verified === false).length],
      ['Status', row.status], ['Reviewed', row.reviewed], ['Exhaustive', row.exhaustive]
    ], row.method, row.source_url);
  });
}
