# V2 assembly contract and plan

Status: preparatory implementation; research finalization pending. Ownership: assembly and staged/published content assets only; no UI edits or publication. `site/V2_CONTRACT.md` governs additive schema fields. Public v1 is read-only to `assembly/build_v2.py`.

## Research root handoff gate

Assembler reads ONLY finalized files under `research/pyq_v2/`, never individual year fragments:
- `READY.md`: first line `# READY` (write last).
- `question_bank.json`: `{ "status": "ready", "questions": [...] }` (complete audited candidates; array form also accepted with READY marker).
- `publication_metadata.json`: object keyed by bank IDs; `{}` is valid when bank is already publication-normalized. Updates need `metadata_review`, may change only the legacy builder's source-backed overlay fields, and MUST NOT upgrade `verified` / `answer_verified` or change IDs/source IDs/URLs. V2 does not read legacy overlay hash validation.
- `ledger.json`: array or `{ "rows": [...] }`; one row per physical PDF, retaining hash, official URL, physical pages, reviewed pages, status, exclusions, duplicates/languages, question IDs, unresolved issues. Do not summarize keyword hits as full review. Original ledger is retained in staged audit report; compact `coverage.source_ledger` derives without promoting review flags.
- `quarantine.json`: array or `{ "records": [...] }`; explicitly held/unresolved candidates. These are not public verified questions.
- `coverage.json`: truthful detailed coverage; no unconditional all-set claim.
- `validation.json`: `{ "status": "ready", "errors": [] }` recommended. `valid: true` or `passed: true` also accepted with no errors. READY signifies finalized best-effort audit, NOT exhaustive coverage.

Record fields follow PLAN.md + site/CONTRACT.md, especially verified boolean, exact source identity/number/section/marks/year/session, one-based pages, official HTTPS URL, evidence image paths, branch/choice accounting. Preserve `source_id` if supplied. If absent, assembly creates an explicitly labelled synthetic *index identifier*, not an official source identity. Paths resolve project-relative or absolute inside project. Every accepted record enters search and its pure master/year collection, including short1, repeated wording in distinct sets, and all resolved alternatives. No 14-slot limit or text-fingerprint deduplication.

Do not reuse a legacy published question ID for changed source wording, provenance, marks, branch or evidence. Supply a distinct v2 occurrence/revision ID if a new audited record differs; v1 records remain intact for the existing 15 compilations. The builder blocks ID conflicts rather than silently overwriting. Explicit quarantine of an already-published ID also blocks pending parent resolution (preserve-v1 versus newly identified source hold).

## Staging and collections

`/opt/venv/bin/python assembly/build_v2.py` produces `assembly/staging-v2/site/` only after input gates and validation. Exit 2 plus `assembly/v2-status.json` when blocked. No polling. No commit/deploy/credentials. A failed rebuild does not replace an earlier complete stage. Public `site/data/content.json`, PDFs and images are untouched.

Retain all 21 document IDs, their existing PDF bytes and question membership. Add official document classification `mixed` / `compilation` to the 15 legacy papers. Originals/notes unchanged. Preserve existing question/source records. Add `pyq-master`, `pyq-year-<year>`, `sqp-master`, `sqp-year-<session>`; `collection_scope` is master/year and year equals authoritative year/session. Chronological natural ordering: year, session, paper code, source identity, original question number/branch, ID. Do not infer a year or paper code from filenames.

No summed marks or duration on archive collections: each printed record retains exact marks; alternatives are independent and explicitly nonadditive. The bank retains all eligible verified records even when not in a legacy paper.

Renderer `pdf_v2.py`: full-width exact source rasters, expandable page height instead of fit-height shrinkage/clipping, numbered linked index, outlines, source-code/year/number/marks headings, exact provenance appendix, official links and verified-only solutions. Long/tall pages require on-screen zoom; printing them fitted to A4 is not a fidelity claim. Very low-resolution source warnings require release visual review.

Each generated file must be **strictly below 90,000,000 bytes**. Actual rendered output is checked; oversized/very long collections split into contiguous near-balanced volumes at question boundaries (default maximum 750 PDF pages per volume, configurable). No arbitrary question-count cap. One record that cannot fit remains a blocker, never silently dropped or degraded. Volume docs retain master/year scope and add collection_id, volume_number, volume_count. Source asset files also must remain under the size ceiling; originals are not recompressed.

## Acceptance and continuation

Assembler tests cover readiness gate, preserved v1 bytes, all-record membership/order, repeated wording/alternatives, collection purity, ID/source-ID conflicts, holds, volume completeness/size, and PDF pixel fidelity/navigation. Run owner validator against the staged root, `final: true`; UI owner now permits minimum 15/4/2. Before release parent must review representative large/tall PDF pages, confirm pending ledger adapter details against final research artifacts, rerun full assembly/site tests, and explicitly publish the validated stage. This entry point never publishes automatically.
