# User Guide

## Start The Server

```bash
conda activate paper_vocab
uvicorn app:app --host 127.0.0.1 --port 18001
```

Open:

```text
http://127.0.0.1:18001
```

If `18001` is already in use, stop the old Uvicorn process or choose another port.

## Analyze A Paper

1. Use the `PDF` file picker to choose a paper.
2. Set `显示数量`.
3. Click `Analyze`.

`显示数量` only controls how many unknown words are shown in the table. If it is `200`, the page displays the top 200 unknown words by frequency.

Use the result filters after analysis:

- Search filters unknown words by text.
- `Domain only` shows only words that also appear in `data/domain_words.txt`.
- The display limit still applies after search and domain filtering.

## Understand The Counters

Top status line:

- `known`: number of words in `data/known_words.txt`.
- `domain`: number of target domain words in `data/domain_words.txt`.
- `ignored`: number of excluded words in `data/ignored_words.txt`.
- `saved unknown`: number of saved unknown words in `data/unknown_words.txt`.
- `current`: number of unknown words from the latest analysis in `data/last_unknown_words.txt`.

Analysis cards:

- `Total words`: total filtered paper tokens.
- `Unique words`: unique filtered paper words after ignored-word removal.
- `Unknown`: words not in `data/known_words.txt`.
- `Domain focus`: unknown words that are also in `data/domain_words.txt`.

## Mark Known Words

If a table word is actually known, click `Known`.

This will:

- Add the word to `data/known_words.txt`.
- Add lemma variants when applicable.
- Remove it from `data/unknown_words.txt`.
- Remove it from `data/last_unknown_words.txt`.
- Write a `known.add` event to `logs/app_events.jsonl`.

After marking several words as known, click `Analyze` again to recompute the PDF statistics.

## Save Unknown Words

Use the buttons under `Unknown Words`.

- `Save shown`: saves only the words currently visible in the table.
- `Save all`: saves all unknown words from the latest analysis.
- `Save domain`: saves only domain-focus unknown words from the latest analysis.

Important:

- `Save` does not mean "I know this word".
- `Save` means "I want to study this word later".

## Export Unknown Words

Click `Export`.

The app downloads a txt file with one word per line. This format is suitable for tools such as 不背单词.

## Import Known Words

Use `Import txt` under `Known Words`.

This imports a txt file into `data/known_words.txt`.

Format:

```text
model
feature
image
training
dataset
```

One word per line.

## Ignore Dataset Or Model Names

Use the `Ignored Words` panel when a token is not a vocabulary word, for example:

- dataset names: `refcoco`, `imagenet`, `lvis`
- benchmark names: `visualgenome`, `objects365`
- model/library names: `pytorch`, `github`, `groundingdino`
- metric/subscript artifacts: `apr`, `aps`, `apm`, `apl`, `apc`, `apf`
- hyphenated task phrase artifacts: `texttoimage`, `crossmodality`

Entering a word and clicking `Ignore` will:

- Add it to `data/ignored_words.txt`.
- Remove it from `data/unknown_words.txt`.
- Remove it from `data/last_unknown_words.txt`.
- Exclude it from future analysis.

## Read Logs

Structured operation log:

```text
logs/app_events.jsonl
```

Latest text log:

```text
logs/app.log
```

Historical text logs:

```text
logs/app_YYYYMMDD_HHMMSS.log
```

Common actions in `app_events.jsonl`:

- `paper.analyze`: a PDF was analyzed.
- `known.add`: a word was marked known.
- `known.import`: a known-word txt file was imported.
- `ignored.add`: a word was ignored.
- `unknown.save`: unknown words were saved.
- `unknown.prune`: saved unknown words were cleaned.
- `logs.clear`: the Activity Log was cleared from the UI.

The `Activity Log` panel has a `Clear` button. It clears old structured events and then writes a single `logs.clear` marker so there is still a trace that the log was reset.

## Troubleshooting

If a word still appears after clicking `Known`:

1. Check that it appears in `data/known_words.txt`.
2. Re-run `Analyze` on the same PDF.
3. Check `logs/app_events.jsonl` for a `known.add` entry.

If `saved unknown` is larger than `current`:

- `saved unknown` is cumulative.
- `current` is only the latest analysis.
- The app prunes known and ignored words from saved unknown words when status or save actions run.

If dataset names appear as unknown words:

1. Add them to `data/ignored_words.txt`, or
2. Use the `Ignored Words` panel.
3. Or click the row-level `Ignore` button in the results table.

If hyphenated phrases appear as joined words, such as `texttoimage` or `crossmodality`, add the joined form to `data/ignored_words.txt`. Normal hyphenated phrases such as `text-to-image` are removed during text cleaning.

If the page does not show a new UI feature:

- Restart the Uvicorn server.
- Refresh the browser page.
