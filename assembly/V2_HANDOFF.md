# V2 assembly preparatory handoff

## Status

Implementation and legacy-data smoke tests complete; **expanded v2 research not ready, no public changes or final expanded release**. The root research handoff gate returns exit 2 immediately. No polling, commits, deployment, credentials or UI edits. Public content SHA-256 before/after gate: `6976bf0e51ffbb2e3b532aa4770a4506796e512d7df22608596aedcbeb6402a1`.

Read `assembly/V2_PLAN_CONTRACT.md` alongside `site/V2_CONTRACT.md` and `research/pyq_v2/PLAN.md`. Research owner must align finalized root files/ledger adapter with that contract. The marker is exactly `# READY` on first line. Per-year fragments are never assembled automatically.

## Implemented

- `build_v2.py`: standalone staging-only entry point. Copies and hash-checks the complete public content/assets/downloads snapshot; never writes public files. Preserves all 21 legacy document IDs, memberships and PDF bytes, all 142 current questions and source records. Adds only mixed/compilation document classification to legacy official worksheets.
- Pure PYQ master/year and SQP master/session collection generation, natural year/set/source-number order, no 14-question selection cap or fingerprint deduplication. Distinct repeated source occurrences and resolved alternatives remain independent. No additive total marks/time on collections.
- Exact source IDs preserved; absent IDs get a disclosed synthetic index identifier. Conflicting IDs block instead of overwriting; explicit new quarantine affecting a preserved v1 ID blocks for parent resolution.
- Verified eligibility and source-backed overlay policy reused without verification upgrades. Incomplete/unverified new records are explicit quarantines, with only ID/reason metadata exposed publicly; raw held answers never become searchable questions. All eligible verified additions enter both search and pure collections.
- `pdf_v2.py`: linked numbered index, year/set/question PDF outline, original question/year/code/marks headings, per-question source appendix and clickable official source/MS URLs. Supplied PNG/RGBA pixels and JPEG compressed bytes preserved in tested embeddings. Full-width source crops; tall pages expand instead of clipping, splitting figures or fit-height shrinkage. Verified-only solutions.
- Actual generated PDFs measured; contiguous balanced volumes only if >=90,000,000 bytes or >750 pages (page ceiling configurable). Individual oversize records block, never downsample/drop. All staged files checked below 90 MB.
- Strict staged UI validator and collection membership/purity/order/preservation/navigation checks. Successful output goes to `assembly/staging-v2/site/` with `assembly/staging-v2/validation.json`. Failed attempts do not replace an earlier complete stage.
- Minimal shared change: `build.apply_publication_metadata(..., validate_legacy_base=True)`; default retains v1 hash checking, v2 skips only the unrelated legacy overlay-base hash check.

## Checks actually run

- `/opt/venv/bin/python -m unittest discover -s assembly -v`: **31 tests pass** (13 legacy, 10 v2 integration-policy tests, 8 PDF renderer tests). Log: `v2-test-results.log`.
- `assembly/build_v2.py`: **exit 2 expected**: READY and six finalized root research files missing. `v2-status.json` records blockers. Public content hash unchanged.
- `node site/tools/validate.mjs --final`: **PASS, 21 documents / 142 questions / 216 linked assets, zero errors/warnings**.
- Disposable full legacy-bank smoke: generated **18 additional pure collections**, combined **39 documents / 142 questions**; added PDFs total **582 pages / 16,968,506 bytes**. Exact staged UI final validation plus v2 checks passed. **217 existing content/assets/PDF files hash-verified**, public files unchanged. Temporary generated PDFs removed; machine summary retained in `v2-smoke-summary.json`, log in `v2-smoke.log`. This is not an expanded-research release.
- Visual spotcheck of PYQ master cover/index and 2025 source Q39 first crop: readable headings/index, circuit complete and unclipped. The separate graph crop was not visually checked in this preparation. Automated bounds/pixel/navigation tests cover synthetic tall/full-width images and long indexes.

## Parent resume

1. Research owner finalizes root files per contract; reconcile actual ledger schema/statuses (do not infer review completeness), verification flags, source IDs, reused v1 IDs and explicit hold conflicts. Current source ledger adapter requires unique `id` (or `source_id`), exact `year`, explicit `status`; preserves false/zero values. Full raw ledger retained in assembly report.
2. Run `/opt/venv/bin/python assembly/build_v2.py` and inspect blockers/validation. It never publishes. Resolve audit defects with research owner, not by weakening checks.
3. Rerun assembly tests and current UI tests/validator. Review representative expanded master/year/volume PDFs, especially long/tall crops, graphs, accessibility alternatives and volume boundaries. Confirm image quality at actual-size/zoom. Custom-height pages are fidelity-first screen documents; A4 fit-to-page printing can reduce readability and is not certified.
4. Parent explicitly publishes validated stage only after cross-checks. Existing `build.py --final` remains the legacy v1 publisher and should NOT be used as the v2 publication command.

Not yet run/claimed: finalized expanded bank assembly, exhaustive all-set source audit, final count, release-wide visual inspection, new UI/browser E2E tests or deployment/live download checks. Existing renderer reports low-resolution warnings rather than inventing detail; those require parent review. Research may require a small final schema adapter change once completed; no endless readiness polling was done.
