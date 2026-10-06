# Electricity site content contract — version 1

Owner boundary: the site developer owns UI/tools/docs; the content assembler owns `data/content.json` and `assets/research/`. This contract is ready for assembly. No UI edit is required to populate content.

## Root JSON

```json
{
  "schema_version": 1,
  "meta": {
    "title": "Electricity — Class 10 study library",
    "chapter": "Electricity",
    "updated": null,
    "intro": "Evidence-led revision, one chapter at a time."
  },
  "coverage": {
    "summary": "Content assembly is pending.",
    "limitations": ["Not an exhaustive archive of all CBSE paper sets."],
    "topics": [{"name": "Electric current and potential difference", "status": "pending", "note": "Awaiting audited content."}]
  },
  "documents": [],
  "questions": [],
  "sources": []
}
```

The expected final inventory is exactly **15 official compilations + 4 original practice/prediction papers + 2 notes/guidance documents = 21 documents**. Counts are computed from data, never asserted by the UI. Empty arrays are valid during assembly. `coverage.topics[].status`: `covered`, `partial`, `pending`. `meta.updated` is a human-readable date or null, not a fabricated verification timestamp.

## Documents

Each document has:
- `id`: unique slug (`[a-z0-9_-]+`); stable URL fragment.
- `kind`: `official`, `practice`, or `notes`.
- `title`, `subtitle` (optional), `description` (optional): plain text.
- `status`: `pending`, `draft`, or `ready`. Ready means editorially checked; not CBSE approved.
- `question_ids`: ordered array of question IDs. References must resolve. Official compilations can mix years/sessions and retain exact question provenance individually.
- `sections`: optional ordered array of `{ "heading": "...", "paragraphs": ["..."], "bullets": ["..."], "images": ["assets/research/..."] }` for instructions, original notes, formula guides, and explanations. All content is plain text, not Markdown/HTML. Use Unicode maths. Arrays may be empty.
- `pdf`: optional **existing generated** site-relative PDF path (e.g. `downloads/official-01.pdf`); leave null/omit until generated. Never point this at an original full Science paper as if it were the chapter compilation.
- `duration_minutes`, `marks`: optional positive numbers. These are compilation totals, not assertions about the full board-paper format.

Practice must be genuinely original and labelled original prediction practice, not an official prediction or guarantee. Official means a compilation of official source questions, not an official CBSE-produced chapter paper. Pending documents may have empty content; ready documents must not.

## Questions

Required common fields: `id` (unique string), `origin` (`official` or `original`), `text` (plain text; may be empty when evidence is authoritative), `topic` (plain text), `marks` (positive number or null), `type` (plain-text label such as `short2`, `MCQ`, `numerical`), `verified` (boolean). Optional `options` (array of strings), `answer` (plain text), `answer_verified` (boolean), `notes` (plain text).

Official question fields (preserve exact source information):
- `source_title`, `session`, `year` (number or string), `exam_type` (`PYQ` / `SQP`), `question_number`, `original_section`, `marks`.
- `page` (one-based PDF page) and/or `pages` (ordered array of one-based PDF pages). Optional `printed_pages` (string) disambiguates printed vs PDF pagination.
- `source_url` (official HTTPS source URL, potentially a ZIP), optional `source_id` (references `sources[].id`), optional `paper_code`.
- `pdf_file` (optional local site-relative original PDF), `marking_scheme_url` (optional official URL), `marking_scheme_pdf_file` or `marking_scheme_file` (optional local site-relative original MS PDF).
- `evidence_images` and/or `evidence_image`: string or array of strings, or image objects `{ "src": "assets/research/...png", "alt": "Exact source question, PDF page 3" }`. Multiple pages/images are rendered in order and duplicates removed.
- `diagram_image`: optional string, array or image object, handled as evidence. **Never reconstruct official source diagrams.** Copy original page/crop images and retain provenance. Questions asking students to draw do not imply a supplied diagram exists.
- `answer_evidence_images` and/or `answer_evidence_image`: same image shape; `answer_source_page`: number or array of page numbers; `answer_transcription`: optional fidelity note.

No local `/a0/...` paths in published JSON. Convert all such fields to copied `assets/research/...` paths. Do not silently mark extracted questions/answers verified. The UI visibly warns when `verified` or `answer_verified` is not true, including on ready documents. Missing source values render as “Not recorded”, never inferred or invented. Every official document has a generated source appendix containing **each question's exact year/session/question/section/marks/PDF pages/source link**. Internal-choice alternatives should have distinct IDs and retain their exact printed labels. Avoid double-counting mutually exclusive alternatives in document marks.

## Sources

Optional source index records:
`{ "id": "unique-slug", "title": "Exact official title", "year": "...", "session": "...", "exam_type": "PYQ", "url": "https://...", "local_pdf": "assets/research/...pdf", "marking_scheme_url": "https://...", "notes": "..." }`.

Question-level provenance is authoritative; the Sources view also enumerates provenance from questions even if this index is empty.

## URLs, security, publication

All local links resolve relative to the site root and must use forward slashes; do not begin with `/`, contain `..` segments, or use filesystem paths. HTTPS and HTTP links are supported, but official production citations should use HTTPS. Unsafe URL schemes are rejected. Strings are always rendered as text. The app fetches `data/content.json` relative to its own page, so GitHub Pages project subpaths work. Serve over HTTP for preview (opening `index.html` as `file://` may block fetch).

Do not commit tokens, credentials, research scratch files, or private annotations. Only populate `pdf` after the output file exists. Review copyright/source attribution before publication. No deployment is performed by the site tooling.

## Validation and printing

Run `node tools/validate.mjs` from `site/` (structural, link, provenance checks; pending data allowed). `node tools/validate.mjs --final` additionally requires the 15/4/2 ready inventory and verified official provenance/evidence/answers when present. Browser print supports one document or all ready documents with evidence and source appendices, including answers by explicit checkbox. CSS removes UI controls and page-breaks documents. Browser “Save as PDF” is a manual supported export; output must be copied into the site and its path added to `pdf` to expose download links.
