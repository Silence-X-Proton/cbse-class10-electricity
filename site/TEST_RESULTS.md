# Site verification report

## UI recovery acceptance — 6 October 2026 UTC

- Recovered and reviewed UI/tool/test diff; data, source assets, downloads and assembly code were not edited by this recovery. Existing localhost server PID 145388 on port 8766 was reused, not duplicated.
- Unit suite: **17/17 passed**. Both assembly and final validators pass the current **21 documents / 142 questions / 216 local asset references**, with zero errors/warnings. Final acceptance uses minimum 15 official / 4 practice / 2 notes, with every added document validated; historical exact counts below are not ceilings.
- Browser harness: **1,018 checks passed each** at desktop 1280×900 (iframe client width 1223) and mobile 375×812 (iframe client width 318), under `/electricity-project/`. Includes separate PYQ/SQP navigation; exact year/session/set and combined filters; derived legacy mixed classification; added master/year collections; eight-question pagination; unchanged IDs/evidence; answer holds; lazy bodies; safe text/URLs; optional/fallback coverage ledger; PDF opt-in/removal; full-document and all-ready print preparation; image-failure blocking; HTTP-error state; no uncaught errors; and no horizontal page overflow.
- Added Special39 grouping checks for metadata, titles and stable IDs `special-39-01..04`, including practice-only classification, preservation of legacy practice, and real reference counts rather than invented 39-question totals. Fixtures are explicitly test-only and never modify published data.
- Fixed a browser-reproduced regression: original editorial notes could expose answers before disclosure and in questions-only print. Notes now remain with answers; tests verify both excluded and included print paths. Official provenance/hold notes remain visible.
- Real published `official-01` mobile preview: trusted Escape closes the native image dialog, removes its source and restores focus to the invoking image button. No PDF iframe exists before opt-in. The existing PDF first page visibly rendered after opt-in; open/download fallback controls remain visible. One small screenshot inspected: `/a0/usr/workdir/electricity-ui-recovery-pdf.jpg`.
- Browser print dialog is mocked in automation. Full exported print pagination, every PDF page, Firefox/Safari, screen-reader/WCAG audit, and the anticipated actual **27-document / 298-question** stage were **not** verified in this recovery. Additive-schema fixtures establish UI compatibility, not author/editor correctness or final stage acceptance.
- No deployment, credentials, token use, or replacement of data/assets/downloads. Final integration must rerun validators and browser checks against the assembled stage. See V2_CONTRACT.md for additive metadata and Special39 rules.

---

## Historical initial-shell verification

The sections below retain the original shell-era results and limitations verbatim. They describe that earlier snapshot, not the populated release or the recovery checks appended below.

## Scope

UI/tooling verification only. The initial published data remains the pending shell, owned by the content assembler. No final question collection, generated PDFs, deployment, or editorial certification is claimed.

## Passed

- `node --check app.js`, `content-utils.mjs`, `tools/validate.mjs`, `tools/serve.mjs`, and `tests/browser-tests.mjs`.
- `node --test tests/content.test.mjs`: **9 tests passed**. Covers URL safety/subpaths, image scalar/array normalization, search combinations, empty pending vs final state, duplicate IDs/missing references, empty ready documents, origin mislabelling, missing provenance/evidence and missing PDF files.
- `node tools/validate.mjs`: initial shell passed assembly validation with an expected pending-content warning.
- `node tools/validate.mjs --final`: correctly fails the initial shell for missing 15/4/2 ready inventory and update date. This is an intentional publication gate, not a site regression.
- Local HTTP preview under `/electricity-project/`: index and JSON return HTTP 200; CSS and modules load with the project subpath.
- Rendered pending shell inspected at desktop width 1024 and mobile width 390. Desktop DOM has no horizontal page overflow. Screenshots at both sizes were explicitly loaded and visually reviewed: typography, responsive stacking, pending-state counts, filters and coverage panel display cleanly. Mobile tabs intentionally scroll horizontally inside their own strip.
- Isolated browser harness `tests/browser.html`: **27 checks passed at mobile (335-pixel iframe); a desktop rerun was initiated but its result was not collected**, no uncaught browser errors.

Browser checks cover computed counts; card rendering; keyboard tabs and focus; preview and requested stable fragment; safe literal content rendering; ordered image arrays; unverified answer warnings; suppression of unavailable PDF links; no-results/reset/marks filtering; image-ready print preparation; answers excluded/included; print-all ready selection; appended official citations with exact session, question, section, marks, page and URL; citation appendix in individual print; no horizontal overflow.

The browser fixtures live only in an isolated in-memory iframe. Original question text is unmistakably synthetic. Official citation testing uses real metadata inspected in `research/sqp/batch_early.json` (2017–18 SQP Q7), with official question text/images deliberately omitted and verification false. No invented official questions are supplied. The harness mocks `history.replaceState` because browsers restrict history replacement in `about:srcdoc`; the intended fragment value is asserted. It mocks the print dialog, not the document/appendix generation or image loading.

## Screenshot evidence (chat-scoped; not published)

- Desktop: `/a0/usr/chats/tpf6MjI2/screenshots/browser/browser-1-20261006-173539-7897e5b1.jpg`
- Mobile: `/a0/usr/chats/tpf6MjI2/screenshots/browser/browser-1-20261006-173559-e3347d6b.jpg`

## Not verified / parent release checklist

- Actual browser print-preview pagination and exported PDF appearance: not tested; print dialog was mocked. Review real multi-page evidence and long answers before release.
- Actual generated PDF download bytes: not tested because no compiled PDF exists in the initial shell. The UI exposes provided safe `pdf` paths; validation checks local file existence/nonzero size, not PDF correctness.
- Full assembled 21-document dataset, official source accuracy, answer correctness, coverage completeness, copyright/redistribution review and remote official link availability: assembler/editor responsibilities, not established by these UI tests.
- Formal WCAG audit, screen-reader sessions, Firefox/Safari and real mobile-device testing: not performed.
- Network failure/malformed JSON and image failure messages are implemented but were not exercised in the browser harness.
- No GitHub token used, no deployment or Pages settings changed by site work. Parent controls publication.

Before release: populate data/assets, run both validators, open representative documents, inspect every source appendix and diagram, generate and review PDFs, link existing downloads, repeat browser tests, and inspect the final artifact for private files. Repository history was not available to site tooling during the initial check; file inspection and targeted checks were used instead of claiming a reviewed Git diff.
