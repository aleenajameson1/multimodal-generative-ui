# 🌿 Sprout — Generative UI Studio

Sprout is a Streamlit application that accepts **multimodal inputs** — text prompts, CSV files, JSON, code, PDFs, and images — and uses an LLM to dynamically generate a fully custom user interface. No hardcoded dashboards, no static layouts.

---

## How It Works

```
Upload File / Type Prompt
        ↓
  Detect File Type
        ↓
  Extract Content          ← core.py: build_file_context()
        ↓
  Generate Smart Context   ← CSV stats, code hints, PDF text, etc.
        ↓
  Send to gpt-5.4-mini     ← core.py: stream_and_collect()
        ↓
  LLM Returns JSON Schema  ← {"title": "...", "layout": [...widgets...]}
        ↓
  Validate JSON            ← core.py: extract_json() + _validate_widget()
        ↓
  Render Dynamic UI        ← core.py: render_layout() → render_widget()
```

---

## Setup

### 1. Install dependencies

```bash
pip install streamlit openai pandas plotly python-dotenv pdfplumber PyPDF2
```

### 2. Add your API key

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
```

### 3. Run

```bash
streamlit run app.py
```

---

## Project Structure

```
sprout/
├── app.py          # Streamlit layout, CSS, sidebar, input UI, generation trigger
├── core.py         # Config, file processing, LLM call, JSON repair, widget renderers
├── .env            # Your OpenAI API key (never commit this)
└── README.md
```

`app.py` owns what the user sees before clicking Generate. `core.py` owns how everything works. Adding a new widget type only requires editing `core.py`.

---

## Supported Input Types

| Type | Extensions | Behaviour |
|------|-----------|-----------|
| Images | png, jpg, jpeg, webp, gif | Sent via vision API; LLM generates a visual analysis UI |
| Spreadsheet | csv | Auto stats, column-type detection, smart chart selection |
| Data | json | Tree view + summary metrics |
| Code | py, js, java, cpp, html, css | Syntax viewer, doc summary, function list, imports, improvement suggestions |
| Document | pdf | Text extracted (pdfplumber → PyPDF2 fallback), summary layout |
| Text | txt, md | Summary with info boxes and timeline (if sequential) |

---

## Widget Catalogue

All widgets are rendered dynamically from the LLM's JSON output.

**Text & Structure** — `heading` · `text` · `markdown` · `info` · `warning` · `success` · `divider`

**Data Display** — `metrics` · `stats_summary` · `table` · `badge_list` · `progress` · `tags` · `file_metadata` · `json_tree`

**Charts** — `bar_chart` · `line_chart` · `pie_chart` · `scatter_plot`

**Interaction** — `form` · `timeline` · `code_block`

**Layout** — `columns` · `tabs` · `accordion`

---

## Key Features

**True Streaming** — `stream=True` in the OpenAI call; chunks arrive progressively with a live character counter in the UI.

**Generative UI / JSON Schema** — The LLM acts as a UI Architect, outputting only JSON. Every widget, chart, layout column, and tab is schema-driven; nothing is hardcoded.

**Multimodal Input** — Images are base64-encoded and sent as `image_url` content parts. All other files are converted to rich text context.

**CSV Intelligence** — Auto-detects numeric vs. categorical vs. time-like columns, computes `describe()` statistics, finds top category values, and annotates the prompt so the LLM picks the correct chart type automatically.

**PDF Parsing** — Tries `pdfplumber` first, falls back to `PyPDF2`. Up to 10 pages, capped at 4,000 characters for token safety.

**JSON Validation** — Every widget's type is checked against `VALID_WIDGET_TYPES` and required fields are verified. Chart data is coerced and sanitised. Malformed widgets render as warning boxes rather than crashing.

**Token Protection** — Hard `MAX_CHARS = 6000` cap on file content. CSV previews limited to 60 rows, code files to 200 lines, PDFs to 10 pages / 4,000 chars.

**Session State** — Generated schema stored in `st.session_state` so switching tabs or Streamlit reruns don't lose the result.

**Error Handling** — Specific catches for `AuthenticationError`, `RateLimitError`, `BadRequestError`, `ValueError` (JSON failure), and a generic fallback — all display the raw model output for debugging.

**Token Cost Display** — Shows prompt tokens, completion tokens, total tokens, and estimated cost in both USD and INR after each generation.

---

## Changing the Model

Edit one line in `core.py`:

```python
MODEL = "gpt-5.4-mini"
```

---

## Adding a New Widget

1. Add the schema description to `SYSTEM_PROMPT` in `core.py`
2. Add the type string to `VALID_WIDGET_TYPES`
3. Add required fields to `REQUIRED_FIELDS`
4. Add an `elif wtype == "your_widget":` block in `render_widget()`

No changes needed in `app.py`.

---

## License

MIT
