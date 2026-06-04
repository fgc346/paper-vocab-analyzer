# Paper Vocabulary Analyzer

A local web tool for reading English papers and collecting unknown vocabulary.

It is designed for personal paper reading workflows, especially embodied intelligence, robotics, VLM/VLA, and computer vision papers. Upload a PDF, compare extracted words against your known-word list, mark domain words, ignore dataset/model/metric artifacts, and export unknown words as a one-word-per-line txt file.

## Features

- PDF text extraction with PyMuPDF.
- English tokenization and lemmatization with spaCy.
- Local known-word, unknown-word, domain-word, and ignored-word lists.
- Result filtering with search and `Domain only`.
- Row-level `Known` and `Ignore` actions.
- `Save shown`, `Save all`, and `Save domain` workflows.
- Local structured activity logs.
- No external API calls for paper analysis.

## Project Layout

```text
.
├── app.py
├── data/
│   ├── domain_words.txt
│   ├── ignored_words.txt
│   ├── known_words.txt          # local personal data, ignored by git
│   ├── unknown_words.txt        # local personal data, ignored by git
│   ├── last_unknown_words.txt   # local runtime data, ignored by git
│   └── paper_history.json       # local runtime data, ignored by git
├── docs/
├── logs/                        # runtime logs, ignored by git
└── requirements.txt
```

## Environment

The project was developed with:

```text
Python 3.10
FastAPI
PyMuPDF
spaCy
```

Install dependencies:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Run

```bash
uvicorn app:app --host 127.0.0.1 --port 18001
```

Then open:

```text
http://127.0.0.1:18001
```

## Vocabulary Files

- `data/domain_words.txt`: domain target vocabulary.
- `data/ignored_words.txt`: dataset names, model names, metric artifacts, and phrase artifacts to exclude.
- `data/known_words.txt`: your personal known words. This file is ignored by git.
- `data/unknown_words.txt`: your saved unknown words. This file is ignored by git.

If `data/known_words.txt` does not exist, the app can generate a small default known-word list.

## Documentation

See:

- [docs/README.md](docs/README.md)
- [docs/system_design.md](docs/system_design.md)
- [docs/user_guide.md](docs/user_guide.md)
- [docs/development_record.md](docs/development_record.md)

## Privacy Notes

The app stores personal vocabulary and paper history locally. The default `.gitignore` excludes:

- `data/known_words.txt`
- `data/unknown_words.txt`
- `data/last_unknown_words.txt`
- `data/paper_history.json`
- `logs/`
