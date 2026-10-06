# Special39 final staging handoff

## Completed, not published

Full authoritative READY bundle assembled successfully by `assembly/build_special39.py`. No schema adapter relaxation was needed. Only `content/special39/originals.json` supplied final questions/readiness; paperNN working drafts were not assembled. No UI changes, public content changes, commits or deployment.

**Stage root:** `/a0/usr/workdir/electricity-project/assembly/staging-special39/site/`

**Build report:** `assembly/staging-special39/validation.json`

**Independent checks:** `assembly/special39-final-checks.json`

**Strict staged site validation:** `assembly/special39-staged-site-validation.json`

The stage contains content JSON, assets and downloads, not a duplicate UI. Parent should combine it with the existing completed UI when previewing/publishing.

## Exact inventory

**27 documents / 298 searchable questions / 27 PDFs / 702 total PDF pages.**

- 15 preserved mixed official compilations + two current-bank pure masters = 17 official documents.
- Four preserved legacy original papers + four new Special39 papers = eight practice documents.
- Two preserved notes documents.
- 142 preserved question records + 156 Special39 originals = 298.

| Added PDF filename | Questions | Marks | Competency marks | Pages | Bytes |
|---|---:|---:|---:|---:|---:|
| special-39-01.pdf | 39 | 80 | 48 | 45 | 147503 |
| special-39-02.pdf | 39 | 80 | 50 | 43 | 142627 |
| special-39-03.pdf | 39 | 80 | 49.5 | 45 | 146605 |
| special-39-04.pdf | 39 | 80 | 48 | 46 | 151794 |
| pyq-master-current.pdf | 30 | nonadditive | — | 63 | 1835643 |
| sqp-master-current.pdf | 48 | nonadditive | — | 206 | 6316729 |

Files are under stage `downloads/`. Every PDF is below 90,000,000 bytes. No volumes needed. Current masters use only the published verified bank, explicitly not the unfinished expanded all-set audit. No new year/session PDF proliferation.

Each Special39 has A20×1, B6×2, C7×3, D3×5, E3×4, exactly 39 ordered questions, 80 marks, >=48 competency marks, detailed solution step marks reconciled, and seven original SVG figures. **28 supplied SVG assets total**, copied byte-identically and rendered as vectors; no global diagram quota. Per-paper classification/physics merit is independently author-reviewed, not inferred by assembly.

## Verified checks

- Full staging build succeeded: `special39-build.log`, `special39-status.json`.
- Strict staged UI validator: **zero errors, zero warnings, 250 linked local assets**.
- Assembly tests: **47/47 passed**. Site content tests: **17/17 passed**.
- Public validator still passes **21 documents / 142 questions / 216 linked assets**. No diff under public data/downloads/assets.
- **217 legacy files** hash-verified; all preexisting document/question/source objects unchanged in stage. Legacy PDF/image bytes preserved.
- All 156 authoritative original question texts, answers, number/section/marks, step allocations, keys, competency allocations/rationales, source-pattern IDs and verification flags compared against final originals.json and preserved.
- All four BUNDLE_SHA256 entries matched. All **32 audit-bound inputs** and **five independent review-report hashes** matched; independent passes retained.
- Every added master has exact membership equal to the current verified source bank for its own PYQ/SQP category; no cross-category contamination.
- Every Special39 PDF contains Q1–39 in order before the rear solutions, and Solutions1–39 in order after the separate solutions page. Correct-option/mark-allocation/appendix markers absent from question portion. Figure assets are vector-only, all pages A4, extracted text/vector bounds checked, bookmarks present.
- Solutions begin on pages **19 / 18 / 19 / 20**; source-pattern/competency appendices begin **32 / 30 / 32 / 33**, respectively.
- Actual rendered minimum figure-label sizes range approximately 11.8–13.7 pt, above the renderer floor. Exact figure stats are in build report.
- All 27 PDFs reopened successfully. `git diff --check` passed.

## Final visual spotchecks

Small images loaded individually, each below 207 KB:
- Paper02 p10: dense two-circuit drawing, labels and question text readable; complete within A4.
- Paper04 p19–20: last case and separate first-solutions page; clean answer boundary and readable detailed marking guidance.
- Paper03 p16–17: long Q36 text and its intact graph continuation; full axes/ticks/plot readable.
- Paper01 p4: current–voltage graph and choices readable; no solution text.

Evidence retained in `assembly/special39-visual/`. These are representative checks, not a full visual review of all 702 pages. Long figures and some question/options flow to the following page rather than shrinking or clipping; original text and graphics are retained. No claim of independent physics re-audit by assembly. Browser E2E was not rerun by this assembler; UI owner retains its completed checks.

## Hashes and parent next action

Public content SHA256 (unchanged):
`6976bf0e51ffbb2e3b532aa4770a4506796e512d7df22608596aedcbeb6402a1`

Staged content SHA256:
`8a32fb45205630b96b1de3f93a8ddead1c51f39cbc279950ebc594970f238ce1`

Author originals SHA256:
`cc9864b367d0698fb119ba38fc48616fad99bd8bbf714264c7c66928e6241dc2`

Parent may perform final browser/visual review and explicitly publish this validated stage. Do not use legacy `build.py --final` for this additive release. `build_special39.py` remains staging-only. The earlier `staging-current-masters` interim output is superseded by the complete `staging-special39` stage for this release.
