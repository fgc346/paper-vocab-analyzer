# System Design

## Goal

The system helps a reader turn a paper into a practical vocabulary workflow:

1. Upload a PDF paper.
2. Extract and normalize English words from the paper body.
3. Compare paper words with `data/known_words.txt`.
4. Exclude noise words from `data/ignored_words.txt`.
5. Mark domain-relevant words using `data/domain_words.txt`.
6. Save or export unknown words for later study.

## Architecture

The app is intentionally small and local:

- FastAPI serves both the HTML page and JSON APIs.
- The frontend is embedded in `app.py` as static HTML/CSS/JS.
- Text data is stored in local files.
- No external database is used.
- No paper content is uploaded outside the machine.

## Data Model

All vocabulary files use one word per line.

`data/known_words.txt`

- Represents words the user already knows.
- A word in this file is excluded from unknown-word results.
- Clicking `Known` writes to this file.

`data/domain_words.txt`

- Represents the target domain vocabulary.
- It does not mean the user already knows these words.
- If an unknown word is in this file, the UI marks it with the `domain` badge.

`data/unknown_words.txt`

- Represents saved unknown words.
- It is pruned against `data/known_words.txt` and `data/ignored_words.txt`.
- It can be exported for tools such as 不背单词.

`data/last_unknown_words.txt`

- Stores unknown words from the most recent PDF analysis.
- It is useful for export and comparison with cumulative saved words.

`data/ignored_words.txt`

- Stores words that should not be studied as vocabulary.
- Examples include dataset names, model names, acronyms, metric names, and benchmark names such as `refcoco`, `imagenet`, `lvis`, `pytorch`, `apr`.
- It also handles PDF extraction artifacts from metric subscripts, such as `AP_r` becoming `apr`.
- It also excludes joined artifacts from hyphenated task phrases, such as `text-to-image` becoming `texttoimage` and `cross-modality` becoming `crossmodality`.

## Analysis Pipeline

1. PDF bytes are parsed with PyMuPDF.
2. Text is extracted page by page.
3. Text is cleaned:
   - Soft hyphens are removed.
   - Hyphenated line breaks are joined.
   - Hyphenated phrases such as `text-to-image` and `cross-modality` are removed because the app exports only single words.
   - Content after headings such as `References`, `Bibliography`, `Appendix`, and `Acknowledgements` is cut off.
4. spaCy tokenizes and lemmatizes the text.
5. Tokens are filtered:
   - Only alphabetic words are kept.
   - Single-letter words are removed.
   - stop words are removed.
   - proper nouns are removed when spaCy detects them.
   - short all-caps tokens are removed.
6. Candidate vocabulary is filtered against `data/ignored_words.txt`.
7. Unknown words are computed as:

```text
paper_vocabulary - ignored_words - known_words
```

8. Domain unknown words are computed as:

```text
unknown_words ∩ domain_words
```

## API Surface

- `GET /`: main web page.
- `GET /api/status`: current vocabulary counts.
- `POST /api/analyze`: analyze an uploaded PDF.
- `POST /api/known/generate`: generate the default known-word list.
- `POST /api/known/import`: import known words from txt.
- `POST /api/known/add`: mark a word as known.
- `POST /api/ignored/add`: add a word to the ignored list.
- `POST /api/unknown/save`: save current unknown words.
- `GET /api/unknown/export`: export unknown words as txt.
- `GET /api/history`: read analysis history.
- `GET /api/logs`: read recent structured log events.
- `POST /api/logs/clear`: clear structured log events and leave a `logs.clear` marker.

## Logging Design

Logs are stored under `logs/`.

Structured event log:

```text
logs/app_events.jsonl
```

This file is JSON Lines and records user-facing actions such as:

- `paper.analyze`
- `known.add`
- `known.import`
- `ignored.add`
- `unknown.save`
- `unknown.prune`
- `logs.clear`

Timestamped text logs:

```text
logs/app_YYYYMMDD_HHMMSS.log
```

Each service start creates a new timestamped log file.

Latest log symlink:

```text
logs/app.log -> app_YYYYMMDD_HHMMSS.log
```

This makes it easy to open the latest text log while preserving older runs.

## Important Design Decisions

- `data/domain_words.txt` is a learning target list, not a known-word list.
- Unknown-word statistics are based on `data/known_words.txt`.
- Saved unknown words do not automatically become known.
- Clicking `Known` removes that word from unknown files.
- Clicking row-level `Ignore` adds the word to `data/ignored_words.txt` and removes it from unknown files.
- The UI distinguishes `Save shown`, `Save all`, and `Save domain`; all three call the same save API with different word lists.
- Ignored words are different from known words: they are not vocabulary learning targets at all.
- Logs are local and readable without a log server.
