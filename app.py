from __future__ import annotations

import io
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import fitz
import spacy
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from spacy.lang.en.stop_words import STOP_WORDS


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
KNOWN_WORDS_FILE = DATA_DIR / "known_words.txt"
DOMAIN_WORDS_FILE = DATA_DIR / "domain_words.txt"
UNKNOWN_WORDS_FILE = DATA_DIR / "unknown_words.txt"
LAST_UNKNOWN_FILE = DATA_DIR / "last_unknown_words.txt"
IGNORED_WORDS_FILE = DATA_DIR / "ignored_words.txt"
HISTORY_FILE = DATA_DIR / "paper_history.json"
LOG_DIR = BASE_DIR / "logs"
APP_LOG_FILE = LOG_DIR / "app_events.jsonl"
LOG_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TEXT_LOG_FILE = LOG_DIR / f"app_{LOG_TIMESTAMP}.log"
LATEST_TEXT_LOG_LINK = LOG_DIR / "app.log"

HEADING_CUTOFF_RE = re.compile(
    r"(?im)^\s*(references|bibliography|appendix|acknowledg(?:e)?ments?)\s*$"
)
ALPHA_RE = re.compile(r"^[a-z]+$")
HYPHENATED_PHRASE_RE = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b")

nlp = spacy.load("en_core_web_sm", disable=["ner"])
app = FastAPI(title="Paper Vocabulary Analyzer")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
if LATEST_TEXT_LOG_LINK.exists() or LATEST_TEXT_LOG_LINK.is_symlink():
    LATEST_TEXT_LOG_LINK.unlink()
try:
    LATEST_TEXT_LOG_LINK.symlink_to(TEXT_LOG_FILE.name)
except OSError:
    LATEST_TEXT_LOG_LINK.write_text(f"Latest log: {TEXT_LOG_FILE.name}\n", encoding="utf-8")
logger = logging.getLogger("paper_vocab")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(TEXT_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)


BASIC_KNOWN_WORDS = """
able about above accept across act add after again against age ago agree air all allow
almost alone along already also although always among amount an and animal another answer
any anyone anything appear area around arrive art article as ask at attention away back
bad bag ball bank base be beautiful because become bed before begin behind believe best
better between big book both box boy bring brother build bus business but buy by call
can car care carry case cat cause center certain change check child choose city class
clean clear close cold college color come common company compare complete computer condition
consider continue cost country course create cut day deal decide deep describe design desk
develop difference different difficult dinner direction do doctor dog door down draw dream
drive drop during each early earth easy eat education effect effort either else end enjoy
enough enter example eye face fact fall family far fast father feel few field figure fill
final find fine finish fire first fish floor follow food foot for force form friend from
front full game general get girl give go good government great green ground group grow
guess hand happen hard have head health hear help here high history hold home hope hour
house how however human idea if important in include increase information inside interest
international into issue job join just keep kind know large last late later law learn leave
left less let letter life light like line list listen little live local long look lose lot
love low machine main make man many mark market matter may me mean measure meet member
memory method middle might mind minute miss money month more morning most mother move much
music must my name nation natural near need never new next nice night no north not note
nothing notice now number object of off offer office often old on once one only open order
other our out outside over own page paper parent part pass past pay people perhaps person
place plan play point poor position possible power practice prepare present problem process
produce product program project public pull purpose put question quickly quite read real
reason receive recent record red remember report research rest result return right rise
road room run same say school science sea second see seem sell send sense service set
several short should show side simple since sit situation six size skill small social
society some someone something sometimes son soon sound south space speak special spend
stand start state stay step still stop story street strong student study subject success
such sure system table take talk task teach team tell term test than thank that the their
them then there these they thing think third this those though thought three through time
today together too tool top total town train true try turn two type under understand unit
until up upon us use user usually value various very view visit voice wait walk wall want
war watch water way we week well west what when where whether which while white who whole
why will with within without woman word work world would write wrong year yes yet you young
your
"""

DEFAULT_IGNORED_WORDS = """
ade ade20k coco cocostuff flickr flickr30k imagenet lvis mscoco nocaps objects365
openimages pascal refcoco refcocog refcocoplus sa1b vqa visualgenome voc yfcc
bert clip convnext dinov dinov2 gpt groundingdino llava resnet sam swin vit
arxiv github latex pytorch tensorflow
openvocabulary
ap apc apf apl apm apr aps ar mar
crossmodality crossmodal crossmodility texttoimage imagetotext
"""


def normalize_words(words: Iterable[str]) -> set[str]:
    normalized = set()
    for word in words:
        item = word.strip().lower()
        if ALPHA_RE.match(item) and len(item) > 1:
            normalized.add(item)
    return normalized


def read_word_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return normalize_words(path.read_text(encoding="utf-8").splitlines())


def write_word_file(path: Path, words: Iterable[str]) -> None:
    path.write_text("\n".join(sorted(normalize_words(words))) + "\n", encoding="utf-8")


def prune_saved_unknown_words() -> set[str]:
    known_words = read_word_file(KNOWN_WORDS_FILE)
    ignored_words = read_word_file(IGNORED_WORDS_FILE)
    saved_unknown = read_word_file(UNKNOWN_WORDS_FILE)
    pruned = saved_unknown - known_words - ignored_words
    if UNKNOWN_WORDS_FILE.exists() and pruned != saved_unknown:
        write_word_file(UNKNOWN_WORDS_FILE, pruned)
        log_event(
            "unknown.prune",
            {"removed": len(saved_unknown - pruned), "unknown_words": len(pruned)},
        )
    return pruned


def append_history(entry: dict) -> None:
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2), encoding="utf-8")


def log_event(action: str, detail: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "detail": detail,
    }
    with APP_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("%s %s", action, json.dumps(detail, ensure_ascii=False))


def read_log_events(limit: int = 60) -> list[dict]:
    if APP_LOG_FILE.exists():
        lines = APP_LOG_FILE.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    lines = lines[-limit:]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def clear_log_events() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    APP_LOG_FILE.write_text("", encoding="utf-8")
    logger.info("logs.clear {}")


def ensure_known_words() -> set[str]:
    if not KNOWN_WORDS_FILE.exists():
        base_words = BASIC_KNOWN_WORDS.split()
        stop_words = [word for word in STOP_WORDS if ALPHA_RE.match(word.lower())]
        write_word_file(KNOWN_WORDS_FILE, [*base_words, *stop_words])
        log_event("known.generate", {"known_words": len(read_word_file(KNOWN_WORDS_FILE))})
    return read_word_file(KNOWN_WORDS_FILE)


def ensure_ignored_words() -> set[str]:
    if not IGNORED_WORDS_FILE.exists():
        write_word_file(IGNORED_WORDS_FILE, DEFAULT_IGNORED_WORDS.split())
        log_event("ignored.generate", {"ignored_words": len(read_word_file(IGNORED_WORDS_FILE))})
    return read_word_file(IGNORED_WORDS_FILE)


def clean_pdf_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"([A-Za-z])-\s*\n\s*([A-Za-z])", r"\1\2", text)
    text = HYPHENATED_PHRASE_RE.sub(" ", text)
    text = re.sub(r"\s+\n", "\n", text)
    match = HEADING_CUTOFF_RE.search(text)
    if match:
        text = text[: match.start()]
    return text


def extract_pdf_pages(data: bytes) -> list[dict]:
    document = fitz.open(stream=data, filetype="pdf")
    pages = []
    for index, page in enumerate(document, start=1):
        pages.append({"page": index, "text": page.get_text("text")})
    document.close()
    return pages


def lemma_for_token(token) -> str:
    lemma = token.lemma_.lower().strip()
    if not lemma or lemma == "-pron-":
        lemma = token.text.lower().strip()
    return lemma


def should_keep_token(token, lemma: str) -> bool:
    text = token.text.strip()
    if "-" in text or "\u2010" in text or "\u2011" in text or "\u2013" in text or "\u2014" in text:
        return False
    if not text or not ALPHA_RE.match(lemma):
        return False
    if len(lemma) <= 1:
        return False
    if token.is_stop or lemma in STOP_WORDS:
        return False
    if token.pos_ == "PROPN":
        return False
    if text.isupper() and len(text) <= 5:
        return False
    return True


def analyze_text_pages(
    pages: list[dict], known_words: set[str], domain_words: set[str], ignored_words: set[str]
) -> dict:
    counts: Counter[str] = Counter()
    page_map: dict[str, set[int]] = defaultdict(set)
    total_tokens = 0

    combined = "\n".join(page["text"] for page in pages)
    cutoff_match = HEADING_CUTOFF_RE.search(combined)
    cutoff_text = combined[: cutoff_match.start()] if cutoff_match else combined
    cutoff_text = clean_pdf_text(cutoff_text)

    docs = nlp.pipe([cutoff_text], batch_size=1)
    for doc in docs:
        for token in doc:
            lemma = lemma_for_token(token)
            if should_keep_token(token, lemma):
                total_tokens += 1
                counts[lemma] += 1

    for page in pages:
        doc = nlp(clean_pdf_text(page["text"]))
        for token in doc:
            lemma = lemma_for_token(token)
            if should_keep_token(token, lemma):
                page_map[lemma].add(page["page"])

    vocabulary = set(counts)
    filtered_vocabulary = vocabulary - ignored_words
    unknown = sorted(filtered_vocabulary - known_words, key=lambda word: (-counts[word], word))
    domain_unknown = [word for word in unknown if word in domain_words]

    return {
        "total_words": total_tokens,
        "unique_words": len(filtered_vocabulary),
        "ignored_words": len(vocabulary & ignored_words),
        "unknown_count": len(unknown),
        "domain_unknown_count": len(domain_unknown),
        "unknown_rate": round(len(unknown) / max(len(vocabulary), 1), 4),
        "unknown_words": [
            {
                "word": word,
                "count": counts[word],
                "domain": word in domain_words,
                "pages": sorted(page_map[word])[:8],
            }
            for word in unknown
        ],
    }


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paper Vocabulary</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17202a;
      --muted: #667085;
      --line: #d0d7de;
      --paper: #ffffff;
      --soft: #f8fafc;
      --bg: #eef2f6;
      --blue: #1f5fbf;
      --blue-quiet: #e8f0ff;
      --green: #0d7a5f;
      --red: #b42318;
      --shadow: 0 12px 32px rgba(20, 31, 43, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 16px 28px;
      border-bottom: 1px solid var(--line);
      background: var(--paper);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { margin: 0; font-size: 20px; font-weight: 750; }
    main {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      gap: 20px;
      padding: 20px 28px 28px;
    }
    section, aside {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    aside { padding: 14px; align-self: start; position: sticky; top: 76px; }
    .panel { padding: 16px; margin-bottom: 16px; }
    .panel:last-child { margin-bottom: 0; }
    .panel h2, .toolbar h2 { margin: 0; font-size: 14px; font-weight: 750; }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 12px;
    }
    label { display: block; margin: 10px 0 6px; font-size: 13px; color: var(--muted); }
    input[type=file], input[type=text] {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 7px 9px;
      font-size: 14px;
    }
    input:focus {
      outline: 2px solid rgba(31, 95, 191, .16);
      border-color: var(--blue);
    }
    button {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 7px 11px;
      font-size: 14px;
      cursor: pointer;
    }
    button:hover { border-color: #9aa7b4; background: var(--soft); }
    button.primary { background: var(--blue); color: #fff; border-color: var(--blue); }
    button.primary:hover { background: #174f9f; border-color: #174f9f; }
    button.ghost { background: transparent; border-color: transparent; color: var(--muted); }
    button.ghost:hover { background: #f1f5f9; color: var(--ink); }
    button.danger { color: var(--red); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .row > * { flex: 1; }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .actions button { min-height: 32px; padding: 5px 9px; font-size: 13px; }
    .filters {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }
    .checkline {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .checkline input { margin: 0; }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    }
    .stat strong { display: block; font-size: 24px; line-height: 1.2; }
    .stat span { color: var(--muted); font-size: 12px; }
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .table-wrap {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td {
      border-top: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      font-size: 14px;
      vertical-align: middle;
    }
    thead th { border-top: 0; }
    th { color: var(--muted); font-weight: 650; background: #f8fafc; }
    tbody tr:hover { background: #fbfdff; }
    td.word { font-weight: 650; }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      background: #e6f7f1;
      color: var(--green);
    }
    .status { color: var(--muted); font-size: 13px; min-height: 20px; }
    .danger { color: #b42318; }
    .empty {
      padding: 40px 16px;
      text-align: center;
      color: var(--muted);
      border-top: 1px solid var(--line);
    }
    .log {
      max-height: 220px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      padding: 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .log div { padding: 6px 0; border-bottom: 1px solid rgba(215, 221, 227, .65); line-height: 1.45; }
    .log div:last-child { border-bottom: 0; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 14px; }
      header { padding: 14px; }
      aside { position: static; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>Paper Vocabulary</h1>
    <div class="status" id="status"></div>
  </header>
  <main>
    <aside>
      <section class="panel">
        <div class="panel-head"><h2>Paper</h2></div>
        <form id="analyzeForm">
          <label for="paperFile">PDF</label>
          <input id="paperFile" name="paper" type="file" accept="application/pdf" required>
          <label for="limitInput">显示数量</label>
          <input id="limitInput" type="text" value="200">
          <div style="height:12px"></div>
          <button class="primary" type="submit">Analyze</button>
        </form>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Known Words</h2></div>
        <div class="row">
          <button id="generateKnown">Generate</button>
          <button id="refreshStatus">Refresh</button>
        </div>
        <label for="knownFile">Import txt</label>
        <input id="knownFile" type="file" accept=".txt,text/plain">
        <div style="height:8px"></div>
        <button id="importKnown">Import</button>
        <label for="knownInput">Add word</label>
        <div class="row">
          <input id="knownInput" type="text" placeholder="word">
          <button id="addKnown">Add</button>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Ignored Words</h2></div>
        <label for="ignoredInput">Add dataset / acronym</label>
        <div class="row">
          <input id="ignoredInput" type="text" placeholder="refcoco">
          <button id="addIgnored">Ignore</button>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Unknown Words</h2></div>
        <div class="row">
          <button id="saveShown">Save shown</button>
          <button id="saveAll">Save all</button>
        </div>
        <div style="height:8px"></div>
        <div class="row">
          <button id="saveDomain">Save domain</button>
          <button id="exportUnknown">Export</button>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Activity Log</h2>
          <button class="ghost danger" id="clearLog">Clear</button>
        </div>
        <div class="log" id="activityLog"></div>
      </section>
    </aside>
    <section class="panel">
      <div class="stats">
        <div class="stat"><strong id="totalWords">0</strong><span>Total words</span></div>
        <div class="stat"><strong id="uniqueWords">0</strong><span>Unique words</span></div>
        <div class="stat"><strong id="unknownCount">0</strong><span>Unknown</span></div>
        <div class="stat"><strong id="domainCount">0</strong><span>Domain focus</span></div>
      </div>
      <div class="toolbar">
        <h2>Results</h2>
        <div class="status" id="summary"></div>
      </div>
      <div class="filters">
        <input id="searchInput" type="text" placeholder="Search unknown words">
        <label class="checkline"><input id="domainOnly" type="checkbox"> Domain only</label>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:36%">Word</th>
              <th style="width:16%">Count</th>
              <th style="width:22%">Pages</th>
              <th style="width:26%">Action</th>
            </tr>
          </thead>
          <tbody id="resultsBody"></tbody>
        </table>
        <div class="empty" id="emptyState">No analysis yet</div>
      </div>
    </section>
  </main>
  <script>
    let allWords = [];
    let visibleWords = [];

    const setStatus = (text, bad = false) => {
      const node = document.getElementById('status');
      node.textContent = text;
      node.className = bad ? 'status danger' : 'status';
    };

    const refreshStatus = async () => {
      const res = await fetch('/api/status');
      const data = await res.json();
      setStatus(`known ${data.known_words} · domain ${data.domain_words} · ignored ${data.ignored_words} · saved unknown ${data.unknown_words} · current ${data.current_unknown_words}`);
      await refreshLog();
    };

    const refreshLog = async () => {
      const res = await fetch('/api/logs');
      const data = await res.json();
      const node = document.getElementById('activityLog');
      node.innerHTML = '';
      for (const item of data.slice().reverse()) {
        const line = document.createElement('div');
        const detail = item.detail || {};
        line.textContent = `${item.time} · ${item.action} · ${Object.entries(detail).map(([key, value]) => `${key}: ${value}`).join(' · ')}`;
        node.appendChild(line);
      }
    };

    const applyFilters = () => {
      const query = document.getElementById('searchInput').value.trim().toLowerCase();
      const domainOnly = document.getElementById('domainOnly').checked;
      const limit = Math.max(1, Number(document.getElementById('limitInput').value) || 200);
      visibleWords = allWords
        .filter(item => !domainOnly || item.domain)
        .filter(item => !query || item.word.includes(query))
        .slice(0, limit);
      renderResults(visibleWords);
      document.getElementById('summary').textContent = `${visibleWords.length} shown · ${allWords.length} total unknown`;
    };

    const saveWordList = async (words, label) => {
      if (!words.length) {
        setStatus(`${label}: nothing to save`);
        return;
      }
      const form = new FormData();
      form.append('words', words.map(item => item.word).join('\\n'));
      await fetch('/api/unknown/save', { method: 'POST', body: form });
      setStatus(`${label} saved: ${words.length}`);
      await refreshStatus();
    };

    const renderResults = (words) => {
      const body = document.getElementById('resultsBody');
      const empty = document.getElementById('emptyState');
      body.innerHTML = '';
      empty.style.display = words.length ? 'none' : 'block';
      for (const item of words) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="word">${item.word} ${item.domain ? '<span class="badge">domain</span>' : ''}</td>
          <td>${item.count}</td>
          <td>${(item.pages || []).join(', ')}</td>
          <td>
            <div class="actions">
              <button data-action="known" data-word="${item.word}">Known</button>
              <button data-action="ignore" data-word="${item.word}">Ignore</button>
            </div>
          </td>
        `;
        body.appendChild(tr);
      }
      body.querySelectorAll('button[data-action]').forEach(button => {
        button.addEventListener('click', async () => {
          const word = button.dataset.word;
          if (button.dataset.action === 'known') {
            await addKnownWord(word);
          } else {
            await addIgnoredWord(word);
          }
          allWords = allWords.filter(item => item.word !== word);
          applyFilters();
        });
      });
    };

    const addKnownWord = async (word) => {
      const form = new FormData();
      form.append('word', word);
      const res = await fetch('/api/known/add', { method: 'POST', body: form });
      if (!res.ok) throw new Error('failed');
      const data = await res.json();
      setStatus(`marked known: ${data.added.join(', ') || word}`);
      await refreshStatus();
    };

    const addIgnoredWord = async (word) => {
      const form = new FormData();
      form.append('word', word);
      const res = await fetch('/api/ignored/add', { method: 'POST', body: form });
      if (!res.ok) throw new Error('failed');
      const data = await res.json();
      setStatus(`ignored: ${data.added.join(', ') || word}`);
      await refreshStatus();
      return data.added || [];
    };

    document.getElementById('analyzeForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = document.getElementById('paperFile');
      if (!input.files.length) return;
      setStatus('analyzing...');
      const form = new FormData();
      form.append('paper', input.files[0]);
      const res = await fetch('/api/analyze', { method: 'POST', body: form });
      if (!res.ok) {
        setStatus('analysis failed', true);
        return;
      }
      const data = await res.json();
      allWords = data.unknown_words;
      document.getElementById('totalWords').textContent = data.total_words;
      document.getElementById('uniqueWords').textContent = data.unique_words;
      document.getElementById('unknownCount').textContent = data.unknown_count;
      document.getElementById('domainCount').textContent = data.domain_unknown_count;
      applyFilters();
      setStatus('analysis complete');
      await refreshStatus();
    });

    document.getElementById('searchInput').addEventListener('input', applyFilters);
    document.getElementById('domainOnly').addEventListener('change', applyFilters);
    document.getElementById('limitInput').addEventListener('input', applyFilters);

    document.getElementById('generateKnown').addEventListener('click', async () => {
      await fetch('/api/known/generate', { method: 'POST' });
      setStatus('generated default known words');
      await refreshStatus();
    });

    document.getElementById('refreshStatus').addEventListener('click', refreshStatus);

    document.getElementById('importKnown').addEventListener('click', async () => {
      const input = document.getElementById('knownFile');
      if (!input.files.length) return;
      const form = new FormData();
      form.append('words_file', input.files[0]);
      form.append('mode', 'merge');
      await fetch('/api/known/import', { method: 'POST', body: form });
      setStatus('known words imported');
      await refreshStatus();
    });

    document.getElementById('addKnown').addEventListener('click', async () => {
      const input = document.getElementById('knownInput');
      if (!input.value.trim()) return;
      await addKnownWord(input.value.trim());
      input.value = '';
    });

    document.getElementById('addIgnored').addEventListener('click', async () => {
      const input = document.getElementById('ignoredInput');
      if (!input.value.trim()) return;
      const added = await addIgnoredWord(input.value.trim());
      allWords = allWords.filter(item => !added.includes(item.word));
      applyFilters();
      input.value = '';
    });

    document.getElementById('saveShown').addEventListener('click', async () => {
      await saveWordList(visibleWords, 'shown unknown words');
    });

    document.getElementById('saveAll').addEventListener('click', async () => {
      await saveWordList(allWords, 'all unknown words');
    });

    document.getElementById('saveDomain').addEventListener('click', async () => {
      await saveWordList(allWords.filter(item => item.domain), 'domain unknown words');
    });

    document.getElementById('exportUnknown').addEventListener('click', () => {
      window.location.href = '/api/unknown/export';
    });

    document.getElementById('clearLog').addEventListener('click', async () => {
      await fetch('/api/logs/clear', { method: 'POST' });
      setStatus('activity log cleared');
      await refreshStatus();
    });

    refreshStatus();
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    ensure_known_words()
    ensure_ignored_words()
    return dashboard_html()


@app.get("/api/status")
def status() -> dict:
    known_words = ensure_known_words()
    ignored_words = ensure_ignored_words()
    unknown_words = prune_saved_unknown_words()
    return {
        "known_words": len(known_words),
        "domain_words": len(read_word_file(DOMAIN_WORDS_FILE)),
        "ignored_words": len(ignored_words),
        "unknown_words": len(unknown_words),
        "current_unknown_words": len(read_word_file(LAST_UNKNOWN_FILE)),
    }


@app.post("/api/known/generate")
def generate_known_words() -> dict:
    known_words = normalize_words([*BASIC_KNOWN_WORDS.split(), *STOP_WORDS])
    write_word_file(KNOWN_WORDS_FILE, known_words)
    log_event("known.generate", {"known_words": len(known_words)})
    return {"known_words": len(known_words)}


@app.post("/api/known/import")
async def import_known_words(words_file: UploadFile = File(...), mode: str = Form("merge")) -> dict:
    content = (await words_file.read()).decode("utf-8", errors="ignore")
    imported = normalize_words(content.splitlines())
    existing = read_word_file(KNOWN_WORDS_FILE) if mode != "replace" else set()
    merged = existing | imported
    write_word_file(KNOWN_WORDS_FILE, merged)
    log_event("known.import", {"imported": len(imported), "known_words": len(merged), "mode": mode})
    return {"imported": len(imported), "known_words": len(merged)}


@app.post("/api/known/add")
def add_known_word(word: str = Form(...)) -> dict:
    words = ensure_known_words()
    raw_words = normalize_words(re.findall(r"[A-Za-z]+", word))
    additions = set(raw_words)
    for item in raw_words:
        doc = nlp(item)
        additions |= normalize_words(lemma_for_token(token) for token in doc)
    additions = normalize_words(additions)
    before_count = len(words)
    words |= additions
    write_word_file(KNOWN_WORDS_FILE, words)
    removed_unknown = read_word_file(UNKNOWN_WORDS_FILE) - additions
    removed_last = read_word_file(LAST_UNKNOWN_FILE) - additions
    if UNKNOWN_WORDS_FILE.exists():
        write_word_file(UNKNOWN_WORDS_FILE, removed_unknown)
    if LAST_UNKNOWN_FILE.exists():
        write_word_file(LAST_UNKNOWN_FILE, removed_last)
    log_event(
        "known.add",
        {
            "input": word,
            "added": ", ".join(sorted(additions)),
            "changed": len(words) - before_count,
            "known_words": len(words),
        },
    )
    return {"known_words": len(words), "added": sorted(additions), "changed": len(words) - before_count}


@app.post("/api/ignored/add")
def add_ignored_word(word: str = Form(...)) -> dict:
    words = ensure_ignored_words()
    additions = normalize_words(re.findall(r"[A-Za-z]+", word))
    before_count = len(words)
    words |= additions
    write_word_file(IGNORED_WORDS_FILE, words)
    removed_unknown = read_word_file(UNKNOWN_WORDS_FILE) - additions
    removed_last = read_word_file(LAST_UNKNOWN_FILE) - additions
    if UNKNOWN_WORDS_FILE.exists():
        write_word_file(UNKNOWN_WORDS_FILE, removed_unknown)
    if LAST_UNKNOWN_FILE.exists():
        write_word_file(LAST_UNKNOWN_FILE, removed_last)
    log_event(
        "ignored.add",
        {
            "input": word,
            "added": ", ".join(sorted(additions)),
            "changed": len(words) - before_count,
            "ignored_words": len(words),
        },
    )
    return {"ignored_words": len(words), "added": sorted(additions), "changed": len(words) - before_count}


@app.post("/api/analyze")
async def analyze_paper(paper: UploadFile = File(...)) -> dict:
    if not paper.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are supported."}
    data = await paper.read()
    pages = extract_pdf_pages(data)
    known_words = ensure_known_words()
    ignored_words = ensure_ignored_words()
    domain_words = read_word_file(DOMAIN_WORDS_FILE)
    result = analyze_text_pages(pages, known_words, domain_words, ignored_words)
    unknown_words = [item["word"] for item in result["unknown_words"]]
    write_word_file(LAST_UNKNOWN_FILE, unknown_words)
    append_history(
        {
            "filename": paper.filename,
            "analyzed_at": datetime.now().isoformat(timespec="seconds"),
            "total_words": result["total_words"],
            "unique_words": result["unique_words"],
            "unknown_count": result["unknown_count"],
            "domain_unknown_count": result["domain_unknown_count"],
            "ignored_words": result["ignored_words"],
            "top_unknown_words": unknown_words[:30],
        }
    )
    log_event(
        "paper.analyze",
        {
            "filename": paper.filename,
            "total_words": result["total_words"],
            "unique_words": result["unique_words"],
            "unknown_count": result["unknown_count"],
            "domain_unknown_count": result["domain_unknown_count"],
            "ignored_words": result["ignored_words"],
        },
    )
    return result


@app.post("/api/unknown/save")
def save_unknown_words(words: str = Form("")) -> dict:
    current = prune_saved_unknown_words()
    known_words = read_word_file(KNOWN_WORDS_FILE)
    ignored_words = ensure_ignored_words()
    incoming = normalize_words(words.splitlines())
    if not incoming and LAST_UNKNOWN_FILE.exists():
        incoming = read_word_file(LAST_UNKNOWN_FILE)
    incoming -= known_words | ignored_words
    merged = current | incoming
    write_word_file(UNKNOWN_WORDS_FILE, merged)
    log_event("unknown.save", {"saved": len(incoming), "unknown_words": len(merged)})
    return {"saved": len(incoming), "unknown_words": len(merged)}


@app.get("/api/unknown/export", response_class=PlainTextResponse)
def export_unknown_words() -> PlainTextResponse:
    words = read_word_file(LAST_UNKNOWN_FILE) or read_word_file(UNKNOWN_WORDS_FILE)
    text = "\n".join(sorted(words)) + ("\n" if words else "")
    return PlainTextResponse(
        text,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=unknown_words.txt"},
    )


@app.get("/api/history")
def history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


@app.get("/api/logs")
def logs() -> list[dict]:
    return read_log_events()


@app.post("/api/logs/clear")
def clear_logs() -> dict:
    clear_log_events()
    log_event("logs.clear", {"events": 0})
    return {"cleared": True}
