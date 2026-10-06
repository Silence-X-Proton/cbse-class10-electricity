# Class 10 Electricity — The Chapter Library

An independent, evidence-linked revision website built from official CBSE and NCERT sources. Not affiliated with or endorsed by CBSE/NCERT.

- Website: https://silence-x-proton.github.io/cbse-class10-electricity/
- Site source and content: [`site/`](site/)
- Reusable next-chapter procedure: [`site/NEXT_CHAPTER.md`](site/NEXT_CHAPTER.md)
- Question/document schema: [`site/CONTRACT.md`](site/CONTRACT.md)
- Assembly and PDF-generation tools: [`assembly/`](assembly/)

## Collection and accuracy

The intended collection is 15 compilations of official-source Electricity questions, four original prediction-style practice papers, and two detailed notes/guidance documents. The website derives actual inventory and readiness from `site/data/content.json`; these counts must pass final validation before deployment. Compilations are editorial chapter practice papers, **not official CBSE-issued chapter papers**. Questions may recur across compilations; source alternatives must not be counted additively. Original practice is not a prediction guarantee.

Source question crops preserve original diagrams and mathematical typography. Each official compilation has a question-by-question source appendix with session/year, original question identifier, section, marks, physical PDF page, and official link. Supplementary text is not a replacement for the source evidence. Missing or erroneous official answers are disclosed, not invented.

The source window is the latest ten sample-paper sessions available at retrieval (2017–18 through 2026–27), and board-paper research for 2017–2026. **This is not an exhaustive extraction of every board set.** Consult the published coverage limitations and source records for actual inclusion and gaps. Downloaded archives are not equivalent to reviewed papers.

## Correct chapter scope

The supplied `leph103.pdf` identifies Class XII Current Electricity, not Class X. This project instead uses official Class X NCERT `jesc111.pdf`, Chapter 11 Electricity, Reprint 2026–27. Activities, references and concepts follow that chapter. Magnetic fields, electromagnetic induction and motor/generator mechanisms are excluded. Fuse heating and parallel appliance connections are retained where supported by the Electricity chapter; a motor used merely in an energy calculation is not a magnetic-effects question.

## Local preview and checks

```sh
cd site
node tools/serve.mjs
# http://127.0.0.1:8080/
node --test tests/content.test.mjs
node tools/validate.mjs --final
```

The checked-in PDFs are generated artifacts; visitors need no installation. To reproduce assembly, obtain the official sources and prepare the audited input bundles described in `assembly/README.md`, install its pinned requirements, and run `python assembly/build.py --final`. Raw downloads, working crops and private scratch files are intentionally excluded from Git. Curated referenced assets are retained in the site.

## GitHub Pages

`.github/workflows/pages.yml` runs interface tests and final content/link validation, then deploys `site/` with GitHub Pages Actions. Enable Pages with GitHub Actions as its build source. No token is stored in the repository or used by the browser. Credentials are never part of a chapter dataset.

## Reuse for another chapter

Start with `site/NEXT_CHAPTER.md`. Verify the user's textbook URL/class first; inventory official sources; preserve exact question/diagram evidence; audit question boundaries, choices and marks; separate original practice; disclose missing sets; generate PDFs with source appendices; test desktop/mobile and download bytes; only then publish. Never relabel downloaded-but-unread files as analysed or force uncertain questions through a readiness gate.

## Attribution

Official question text, diagrams and source PDFs remain attributable to their respective publishers. Their inclusion does not imply ownership, endorsement or a new open-content licence. Do not apply a blanket software licence to third-party examination or textbook content. Original commentary and website implementation are distinguished from official source material.
