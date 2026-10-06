# Special39 staging integration

Priority: additive four original papers before expanded research assembly. No UI edits/publication. Author owns content/special39; assembler owns assembly and staged content.

## Final author input

`content/special39/originals.json`, `READY.md`, `audit.json`, `validate_bundle.mjs`, and referenced original SVGs under `content/special39/assets/`. READY first line must contain READY but not NOT READY/IN PROGRESS. Bundle root documents/questions/sources follows AUTHOR_SPEC.md, ready documents and true reviewed question/answer flags. Audit root `passed: true` or status `ready`/`passed`/`complete`, with no errors, indicates completed independent review; actual physics review belongs to author/reviewers. Final schema differences can be aligned once, never guessed or polled indefinitely.

Four document IDs special-39-01..04; question IDs special-39-NN-q01..q39. Each: 39 questions, 80 marks, 180 minutes; A20×1 (16 MCQ+4 assertion/reason), B6×2, C7×3, D3×5, E3×4. No OR choices. Every question has detailed answer and positive step/marks allocation summing exactly to question marks, competency boolean/marks/rationale, source-pattern references. >=48 competency marks per paper. Author structural validator independently checked as an imported pure function (no writes to author directories).

SVG aliases `assets/research/special39/<name>.svg` resolve only to author `assets/<name>.svg`, then copy to hash-named staged assets byte-identically. Original SVGs remain vector in PDFs, minimum rendered label 8.5pt; no raster/external references or unsupported clipping/effects. The requirement is at least five substantive diagram/graph-dependent questions per paper with correct readable original visuals; there is no global SVG quota. Assembly checks at least five diagram-linked questions per paper, vector validity/readability and actual per-paper distinct SVG counts. Independent author/reviewer audits establish substantive dependence and physical correctness. The existing 28 SVGs can satisfy this requirement; never add decorative figures to inflate counts. This follows content/special39/PARENT_CLARIFICATION.md.

## Output and modes

`/opt/venv/bin/python assembly/build_special39.py` => ready bundle + two current published-bank masters => `assembly/staging-special39/site/` and sibling `validation.json`. Does not depend on research/pyq_v2. Failures preserve public release and any previous complete stage.

`/opt/venv/bin/python assembly/build_special39.py --masters-only` => two archives from CURRENT published verified source questions only => `assembly/staging-current-masters/site/`. This is an interim independent artifact while author review continues, not a completed Special39 release. Pure PYQ and SQP masters only; no year/session document explosion. Existing legacy coverage/holds remain unchanged; new descriptions explicitly deny expanded audit/all-set coverage. Split volumes only if required by measured 90MB/750-page limits.

Preserve every preexisting document/question/source record and original PDF/image bytes. Add four distinguished practice documents with `practice_series: special39`, title prefix `Special39 / competency practice`, exact original title retained as `author_title`; no official/prediction label. Four legacy original practice papers remain. Existing official docs may receive only additive mixed/compilation metadata. New question/source ID conflicts block, never overwrite.

A4 exam PDFs: cover/instructions, sections A–E, Q1–39, readable vector circuits/graphs, all answers/mark allocations solely in rear solutions, then original source-pattern/competency rationale appendix, bookmarks/page totals. Audit arithmetic/count/mark splits, source links and PDF bounds; physics truth and competency semantic merit remain independently author-reviewed.

Run assembly tests and strict site validator against staged root. Report counts/hashes/vector/layout stats. Parent owns final visual review/publish; this script never copies anything back to public site. Avoid `build.py --final` for this additive release.
