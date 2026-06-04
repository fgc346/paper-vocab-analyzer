# Paper Vocabulary Analyzer Documentation

## What This Project Does

This project is a local web tool for paper reading. It analyzes an English PDF paper, compares the paper vocabulary with words you already know, and produces a list of unknown words that can be saved or exported for vocabulary study.

The first use case is reading embodied intelligence, robotics, VLM/VLA, and computer vision papers.

## Current App

- Entry point: `app.py`
- Local server: FastAPI + Uvicorn
- Runtime environment: conda environment `paper_vocab`
- Default URL: `http://127.0.0.1:18001`
- PDF parser: PyMuPDF
- English NLP: spaCy `en_core_web_sm`

## Main Files

- `data/known_words.txt`: words treated as already known.
- `data/domain_words.txt`: domain target vocabulary, used to mark important domain words.
- `data/unknown_words.txt`: saved unknown words.
- `data/last_unknown_words.txt`: unknown words from the latest analysis.
- `data/ignored_words.txt`: dataset names, model names, acronyms, and other tokens excluded from unknown-word statistics.
- `data/paper_history.json`: per-paper analysis history.
- `logs/app_events.jsonl`: structured operation log.
- `logs/app_YYYYMMDD_HHMMSS.log`: timestamped text log for each service start.
- `logs/app.log`: symlink to the latest timestamped text log.

## Project Layout

```text
.
├── app.py
├── data/
│   ├── known_words.txt
│   ├── domain_words.txt
│   ├── unknown_words.txt
│   ├── last_unknown_words.txt
│   ├── ignored_words.txt
│   └── paper_history.json
├── docs/
├── logs/
└── requirements.txt
```

## Documentation Index

- [System Design](system_design.md)
- [Development Record](development_record.md)
- [User Guide](user_guide.md)

## Start The App

```bash
conda activate paper_vocab
uvicorn app:app --host 127.0.0.1 --port 18001
```

Or without activating:

```bash
conda run -n paper_vocab uvicorn app:app --host 127.0.0.1 --port 18001
```

Then open:

```text
http://127.0.0.1:18001
```
