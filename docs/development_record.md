# Development Record

## Initial Vocabulary Book

The project started with a request to create a vocabulary book for 不背单词. The format requirement was one English word per line in a txt file. The first generated file was:

```text
embodied_intelligence_words.txt
```

It contains words related to embodied intelligence, robotics, VLA/VLM, perception, planning, control, simulation, and academic paper reading.

Later additions expanded it with common paper-reading vocabulary such as:

- `proof`
- `theorem`
- `hypothesis`
- `empirical`
- `significant`
- `limitation`
- `formulation`
- `derivation`
- `robust`
- `scalable`
- `posterior`
- `likelihood`

## Product Requirement

The next requirement was to build a tool for reading papers:

- The user knows some words.
- The user uploads a paper.
- The program extracts words from the paper.
- It compares paper words with known words.
- It saves unknown words to a personal word book.

The selected v1 product shape was:

- Local web app.
- PDF-first workflow.
- txt-compatible vocabulary files.
- Page-level management for known and unknown words.

## Environment Setup

A new conda environment was created instead of using `base`:

```text
paper_vocab
```

Python version:

```text
Python 3.10.20
```

Installed dependencies:

- `fastapi`
- `uvicorn`
- `python-multipart`
- `pymupdf`
- `spacy`
- `en_core_web_sm`

The dependencies are recorded in:

```text
requirements.txt
```

## First App Implementation

The first implementation used a single `app.py` file:

- FastAPI backend.
- Embedded HTML/CSS/JS frontend.
- PyMuPDF for PDF parsing.
- spaCy for tokenization and lemmatization.
- Local txt/json/jsonl files for storage.

The first UI supported:

- PDF upload.
- Analyze button.
- Unknown-word table.
- Frequency count.
- Page references.
- `Known` action.
- Save and export unknown words.

## Known Words Clarification

An important correction was made:

`embodied_intelligence_words.txt` was not the known-word list.

Instead:

- `data/known_words.txt` stores words already known.
- `data/domain_words.txt` stores domain words worth learning.

The app generated a default `data/known_words.txt` using a basic English word list plus spaCy stop words. The user later imported a larger known-word txt file, increasing the known-word count.

## Unknown Save Semantics

The user noticed that clicking `Save` did not reduce unknown words. This was clarified and then improved:

- `Save` means "save these unknown words for study".
- `Known` means "I know this word, stop counting it as unknown".

Later, `data/unknown_words.txt` was pruned so that words already marked as known are removed from saved unknown words.

## Known Button Bug

The user reported that `model` still appeared after clicking `Known` and analyzing again.

The fix changed the known-word add path:

- It now writes the raw word.
- It also writes spaCy lemma variants.
- It removes the added word from `data/unknown_words.txt` and `data/last_unknown_words.txt`.
- It writes a structured event log.

## Ignored Words

The user found that dataset names such as `RefCOCO` were recognized as vocabulary words such as `refcoco`.

The fix introduced:

```text
data/ignored_words.txt
```

This list excludes dataset names, benchmark names, model names, acronyms, and tool names from vocabulary statistics.

Examples:

- `refcoco`
- `refcocog`
- `imagenet`
- `lvis`
- `visualgenome`
- `pytorch`
- `github`

Later, PDF extraction artifacts from metrics were also added. For example, table headers such as `AP_r` can be extracted as `apr`, so `ap`, `aps`, `apm`, `apl`, `apr`, `apc`, `apf`, `ar`, and `mar` are ignored by default.

Hyphenated task phrases were also handled. Since the export target accepts single words, phrases such as `text-to-image` and `cross-modality` are removed during text cleaning. Joined extraction artifacts such as `texttoimage`, `imagetotext`, `crossmodal`, `crossmodality`, and `crossmodility` are ignored by default.

An `Ignored Words` UI panel and `/api/ignored/add` API were added.

## Logging Evolution

The project first had a root-level:

```text
app_log.jsonl
```

This was then replaced by a `logs/` directory:

```text
logs/app_events.jsonl
logs/app.log
```

Finally, the text log was changed to timestamped files:

```text
logs/app_YYYYMMDD_HHMMSS.log
logs/app.log -> app_YYYYMMDD_HHMMSS.log
```

This keeps historical logs while making the latest log easy to open.

The Activity Log UI was later improved with a `Clear` button. Clearing the log truncates `logs/app_events.jsonl` and records a fresh `logs.clear` event so future debugging can see when the reset happened.

## Usability Improvements

The result workflow was refined with smaller controls:

- `Save shown` saves only the currently visible rows.
- `Save all` saves every unknown word from the latest analysis.
- `Save domain` saves only domain-focus unknown words.
- A search box filters the result table.
- A `Domain only` toggle narrows the table to domain-focus words.
- Each result row now has both `Known` and `Ignore` actions.

## Project Layout Cleanup

The prototype originally kept vocabulary and history files in the project root. The layout was later cleaned up so app data lives under `data/`:

```text
data/known_words.txt
data/domain_words.txt
data/ignored_words.txt
data/unknown_words.txt
data/last_unknown_words.txt
data/paper_history.json
```

The old root-level `embodied_intelligence_words.txt` was renamed to `data/domain_words.txt` to reflect its role in the app. The old root-level `app_log.jsonl` and Python cache files were removed.

## Current State Snapshot

At the time this documentation was written:

- `data/known_words.txt`: 3347 words.
- `data/domain_words.txt`: 692 words.
- `data/ignored_words.txt`: 59 words.
- `data/unknown_words.txt`: 86 words.
- `data/last_unknown_words.txt`: 83 words.

The app is running on:

```text
http://127.0.0.1:18001
```
