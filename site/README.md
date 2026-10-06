# Electricity · Class 10 study library

A responsive, accessible-first, static chapter library for GitHub Pages. **Electricity only.** Vanilla HTML/CSS/JavaScript; no package installation, external fonts, analytics, build step, authentication or runtime service. No GitHub token is needed by this site; no deployment has been performed.

## Current state

The recovered interface supports the existing **21-document / 142-question** release and additive collections under schema version 1. Final inventory requirements are **minimum 15 official + 4 original practice + 2 notes**, not a ceiling. The anticipated 27-document / 298-question Special39-and-masters stage is an assembler deliverable, not published or certified by this UI work. The initial pending shell is historical; see TEST_RESULTS.md and RELEASE.md.

UI readiness is separate from content readiness. Actual ready counts, question verification, source details and coverage limitations remain visible. “Official” describes the question source, not this independent compilation. There is no CBSE affiliation and no exam guarantee.

## Preview locally

With Node.js 18+ installed:

```sh
cd /a0/usr/workdir/electricity-project/site
node tools/serve.mjs
# http://127.0.0.1:8080/
```

Test a GitHub Pages project subpath:

```sh
PORT=8765 BASE_PATH=/electricity-project node tools/serve.mjs
# http://127.0.0.1:8765/electricity-project/
```

The server binds localhost, serves only this folder, and requires no dependencies. Stop with Ctrl+C. Do not use it as an internet-facing production server. Opening `index.html` directly as `file://` may block JSON loading; a clear error and retry button are provided.

## Content handoff

Read **[CONTRACT.md](CONTRACT.md)** before writing content. The assembler owns `data/content.json` and `assets/research/`; UI work must not overwrite populated data or source assets.

1. Copy reviewed original source crops/PDFs into `assets/research/` and convert filesystem paths to site-relative paths. Preserve arrays for multi-page evidence; no diagram reconstruction.
2. Create question records with explicit original/official origin, exact per-question provenance, editorial verification flags, optional transcription, and source/answer evidence. A question transcription can be empty when the evidence image is authoritative.
3. Assemble ordered `question_ids` into documents, or use plain-text `sections` for detailed notes. Use stable document slugs. Keep incomplete documents `draft`/`pending`.
4. Add source index, audited coverage, limitations and truthful update date. Official source provenance is rendered for every official question in each document's appendix, independently of the optional global source index.
5. Run validation and review the populated site. A `ready` label must be justified, never used to suppress warnings. `--final` is deliberately stricter than assembly checks.
6. Generate PDFs only from reviewed content. Add `documents[].pdf` only after the corresponding file exists.

## Features

- Separate keyboard-navigable PYQ, SQP, original and all-question banks; independent library tabs. Arrow keys/Home/End change tabs. Pure PYQ/SQP master and year collections are separate from legacy mixed compilations.
- Responsive document cards; eight-question reader pages with stable `#doc-ID` fragments. Featured Special39 practice grouping recognizes supplied practice_series metadata, Special39 titles and special-39-01..04 IDs; titles and actual counts remain data-driven. Legacy practice stays separate.
- Native accessible question/answer/source accordions; search by wording, topic, session, source title and question number; topic/year/session/set/marks filters; 20-result batches and lazy question bodies.
- Scalar or array evidence images, optional descriptive alt text, full-window zoom with Fit/100%/± controls, Escape and focus restoration, full-size source links, visible image-load errors and unverified-answer warnings.
- Dedicated document print styles, one-document or all-ready printing, optional answers, source appendices and explicit disclaimers.
- No PDF download links until `pdf` is present; local link validation detects missing assets.
- Text-only rendering (no content HTML execution), safe local/HTTP(S) links, no root-relative assumptions, reduced-motion support and visible focus indicators.

## Printing and PDFs

Use **Print full document** from a preview, or **Print all ready documents**. Choose whether answers are included; official answers print only when verified. Original editorial notes remain with answers, not in questions-only output. PDF embeds are opt-in and removed on hide, close or document switch; Open PDF and Download PDF remain available. The print helper eagerly loads every included evidence image and stops if images fail or do not finish within 15 seconds, instead of silently printing incomplete evidence. Browser printing itself is user-controlled.

Select **Save as PDF**, A4, normal scale. For cleaner output disable browser-added headers/footers. Each document starts a new page; source URLs are printed in appendices. Long question/evidence blocks may continue across pages to avoid clipping. Review page breaks and all diagrams before release. The browser's own Ctrl/Cmd+P has a fallback, but the dedicated print buttons are preferred because they await image loading.

Save individual files under `downloads/` (create it when needed), then set their exact relative paths in the corresponding `pdf` fields. Re-run validation. The site does not fabricate files, automatically update JSON after printing, or generate/deploy PDFs on visitors' devices without interaction. Existing PDF files are assembler-owned; this UI neither regenerates nor replaces them.

## Checks

```sh
node --check app.js
node --check content-utils.mjs
node --test tests/content.test.mjs
node tools/validate.mjs
node tools/validate.mjs --final
```

Assembly validation allows empty/pending content but rejects invalid references, mixed official/original paper origins, unsafe URLs, invalid question fields, empty ready documents, and missing local assets. Final validation also enforces minimum 15/4/2 ready inventory, readiness of every additional document, and official provenance, evidence, and answer verification where answers are provided. A final failure is expected for an empty pending shell, not the current populated release. The validator does **not** replace visual source auditing, assess scientific correctness, check remote URLs online or certify WCAG conformance.

Browser exercise: visit `tests/browser.html` while serving the site. Its isolated iframe deep-copies the actual published data, preserving real question/asset/hold records, and adds test-only collection metadata plus explicitly labelled original safety/grouping fixtures in memory. It does not modify `data/content.json` or publish fake official questions. It checks populated cards, filtering, safe text rendering, image arrays, preview, answer warnings and print preparation with a mocked print dialog. The fixture is only a test harness; it is not linked from the student-facing site.

Before publication, manually check mobile and desktop, keyboard-only navigation, representative official multi-page evidence, source appendix completeness, image readability, working PDF downloads and actual print previews. See `TEST_RESULTS.md` for performed checks and remaining limitations.

## GitHub Pages (publication remains user-controlled)

All local resources are site-relative and work beneath `/REPOSITORY/`; no `base` URL or domain hardcoding is needed. Publish **the contents of this `site/` folder** as the Pages artifact/root using the repository's chosen Pages workflow. If using branch-based Pages without a workflow, select a supported source location and arrange a reviewed copy of this folder there yourself. GitHub does not offer arbitrary `/site` as a branch Pages source directory. The site tools do not change repository Pages settings, create workflows, use credentials, or push commits.

Never publish private research scratch files or credentials. Check source attribution and licensing before public redistribution. Exclude tests and internal handoff documentation from the uploaded artifact if desired; the UI's footer links to README/CONTRACT should then be removed or retained with public-safe copies.

## Files

- `index.html`, `styles.css`: visual design, responsive and print layout.
- `app.js`: fetching, cards/tabs/search, reader, provenance, print preparation.
- `content-utils.mjs`: shared normalization, URL safety, shape checks, search and grouping.
- `ui-evidence.mjs`: native image viewer and bounded source coverage ledger.
- `V2_CONTRACT.md`: optional additive fields and assembler/UI boundaries.
- `data/content.json`: content entry point (assembler-owned).
- `CONTRACT.md`: exact schema and editorial rules.
- `tools/serve.mjs`, `tools/validate.mjs`: dependency-free local tooling.
- `tests/`: unit tests and isolated browser harness.
- `NEXT_CHAPTER.md`: safe, repeatable chapter expansion workflow.

No runtime dependencies or service-worker cache: updated published JSON is fetched normally on the next visit/reload.
