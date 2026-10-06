# Electricity compilation assembly

Owner: assembly agent. Write scope is `assembly/`, `site/data/`, `site/assets/research/`, and `site/downloads/` only. UI/tools belong to the website developer; source research and authored material remain untouched.

## Input gate / coordination

The rerunnable builder requires the four completed bundles plus the READY PYQ publication metadata overlay:

- `research/sqp/question_bank.json`
- `research/pyq/question_bank.json`
- `content/originals.json`
- `content/notes.json`
- `research/pyq/publication_metadata.json` (with `PUBLICATION_READY.md`)

Current SQP batches and nested PYQ recovery files are inspected for schema compatibility only. Their presence does not mean the final bank is ready. No polling/wait loop: a missing or incomplete input produces `assembly/status.json`, exits without publishing a partial final library, and can be resumed by the parent. Prefer root `{ "status": "ready", "questions": [...] }` for banks and `{ "status": "ready", "documents": [...] }` for authored documents. Atomic final-file rename is recommended. A complete final bank without a status field will be accepted if it validates; an explicit non-ready status will block.

Source owners: preserve question IDs, individual PDF page numbers, exact printed identifier including selected subparts, original section, attributable marks, official source URL, original crop/diagram paths, verification booleans and uncertainty notes. Internal choice alternatives need a common `choice_group` plus distinct IDs; combined OR blocks need a clear selected alternative or explicit non-additive marks. Questions containing out-of-scope subparts need an electricity-only crop, exact selected-subpart label and attributable marks. Rendering is NOT source verification. No builder step will promote `verified` or `answer_verified` to true.

Author: provide exactly four original paper documents and two notes documents using the site contract. Questions may be embedded in each paper's `questions` or supplied in a root `questions` array with `question_ids`. Notes use document `sections`. Original solutions should have explicit verification flags. Author content is not automatically editorially verified.

Site developer: assembly will generate `site/data/content.json` to CONTRACT v1 and actual generated `site/downloads/<document-id>.pdf`; evidence and only referenced PDF sources go under `site/assets/research/`. Additional metadata is additive. The site final validator must retain visible uncertainty rather than treating a rendered crop as verified.

## Assembly plan

1. Inspect schemas, verification flags, exclusion notes, internal choices, source boundaries and available marks inventory.
2. Normalize provenance without inventing missing years/sections/marks/pages; copy referenced images and PDF sources only, never ZIP bundles. Original authoritative crops remain byte-identical.
3. Produce exactly 15 labelled official-source chapter compilations, four original prediction/practice papers and two detailed notes. Use A MCQ, B 2-mark, C 3-mark, D 5-mark/case sections only where available; disclose absent sections/shortfalls. Target 30–40 marks when the eligible inventory supports it. Do not double count alternatives or repeat a question within a paper. Disclose reuse across papers and avoid duplicate question-set papers.
4. Generate printable PDFs from the same normalized dataset, with Unicode fonts, authoritative evidence, source appendices and verified solutions only. Never reconstruct official diagrams.
5. Validate 21 documents, 15/4/2 split, source/evidence links, PDF files, marks, choices, coverage statements and uncertainty preservation. Run the website validator if available, reporting rather than concealing strict audit failures.

## Publication quality gate

Missing data is not fabricated. Sources with ambiguous marks, unresolved choice structure, missing evidence/provenance or explicit boundary/scope concerns will be reported and excluded from official paper selection until resolved. Evidence verification remains the source owner's responsibility. Publication of a `ready` document requires all selected questions to have source verification; no implicit image verification.

Coverage will explicitly separate downloaded, processed and verified sets; cancelled/missing years and partial last-ten-year coverage will remain visible. Fifteen compilations are curated mixed-source worksheets, NOT fifteen unique official CBSE chapter papers and NOT all-set coverage.

## Current stage

Preparatory: contracts read; final banks and authored content are not yet present. Python `/opt/venv/bin/python` has PyMuPDF but initially lacks ReportLab/WeasyPrint. System DejaVu fonts are available. Renderer dependencies and exact run command will be recorded as implementation completes.

## Final stage (supersedes preparatory status above)

Completed 21 ready documents/PDFs. See `HANDOFF.md` for final counts, exact exclusions and checks. Final-answer policy supersedes the original preparation note: genuinely withheld official answers are removed from public answer/evidence fields while their false answer-verification flag, limitation note and MS link remain. Only verified official questions are selected. PYQ READY is mandatory. SQP coverage is loaded from `coverage_manifest.json`. Run `/opt/venv/bin/python assembly/build.py --final`; all 21 PDFs and the website owner's strict validation are required before content publication.

## Current multi-year release

The READY source-backed overlay is integrated. Final counts: 21 PDFs, 142 searchable records, 48 SQPs + 30 PYQs + 64 originals. PYQs cover 2018 and 2022–2026; every official paper spans 4–6 board years. Three SQP short1 records are searchable bank-only items. `HANDOFF.md` and `final-summary.json` supersede all earlier preparatory-stage counts and policies. Parent may deploy after its own checks.
