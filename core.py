"""
core.py — Generative UI Studio
All non-UI logic: config, file processing, LLM calls, JSON repair, widget rendering.
"""

import openai
import json
import base64
import re
import io
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = "gpt-5.4-mini"

SUPPORTED_TYPES = [
    "png", "jpg", "jpeg", "webp", "gif",          # images
    "csv", "json", "txt", "md",                    # data / text
    "py", "js", "java", "cpp", "html", "css",      # code
    "pdf",                                         # documents
]

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Generative UI Architect. Your SOLE job is to analyse the user's
input and respond with a single, valid JSON object defining a rich, interactive UI layout.

CRITICAL RULES:
1. Output ONLY valid JSON. No markdown fences, no explanations, no prose.
2. Root object MUST be: {"title": string, "layout": [...]}
3. Every widget MUST have a "type" field.
4. LAYOUT SIZE LIMIT: max 10 top-level widgets. Use columns to pack content. Never exceed.
5. Keep data arrays short: max 8 items in charts, max 6 rows in tables, max 5 progress items.
6. If an image is provided, use it as context only — build a focused, data-driven layout.
7. ALWAYS close every JSON bracket/brace. Double-check nesting.

FILE-TYPE ADAPTIVE BEHAVIOUR:
• CSV  → lead with metrics row, then charts (bar/line/pie chosen by data shape), then table
• JSON → tree/table view + summary metrics
• Code (py/js/java/cpp/html/css) → syntax-highlighted code_block, markdown doc summary,
         function/class list as badge_list, detected imports as tags, architecture note, improvements
• PDF/TXT/MD → summary heading + info boxes for key points + timeline if sequential
• Image → visual theme analysis + descriptive text + relevant metrics if inferable
• No file → honour the user's prompt literally

CSV INTELLIGENCE (auto-detect):
• numeric-only columns → bar or line chart
• categorical + numeric → bar chart
• time-like column present → line chart (time on x)
• ≤6 unique categories → pie chart for share breakdown
• two numeric columns → scatter plot for correlation

CHART SELECTION GUIDE:
  categorical   → bar_chart
  time series   → line_chart
  percentages   → pie_chart
  correlations  → scatter_plot

LAYOUT INTELLIGENCE:
  • metrics row at the top
  • charts before tables
  • use columns for side-by-side panels
  • group related widgets under headings + dividers
  • end with an AI insights section (info/success/warning boxes)

WIDGET TYPES & SCHEMAS:
• heading      – {"type":"heading","text":"...","level":1-4}
• text         – {"type":"text","content":"..."}
• markdown     – {"type":"markdown","content":"..."}
• info         – {"type":"info","content":"..."}
• warning      – {"type":"warning","content":"..."}
• success      – {"type":"success","content":"..."}
• metrics      – {"type":"metrics","items":[{"label":"...","value":"...","delta":"...","delta_type":"positive|negative|neutral"}]}
• stats_summary– {"type":"stats_summary","items":[{"label":"...","value":"...","unit":"..."}]}
• table        – {"type":"table","headers":[...],"rows":[[...],...]}
• bar_chart    – {"type":"bar_chart","title":"...","x_label":"...","y_label":"...","data":[{"label":"...","value":number}]}
• line_chart   – {"type":"line_chart","title":"...","x_label":"...","y_label":"...","series":[{"name":"...","data":[number,...]}],"x_values":[...],"smooth":true}
• pie_chart    – {"type":"pie_chart","title":"...","data":[{"label":"...","value":number}]}
• scatter_plot – {"type":"scatter_plot","title":"...","x_label":"...","y_label":"...","data":[{"x":number,"y":number,"label":"..."}]}
• progress     – {"type":"progress","items":[{"label":"...","value":0-100}]}
• tags         – {"type":"tags","items":["tag1","tag2"]}
• badge_list   – {"type":"badge_list","items":[{"label":"...","status":"success|warning|error"}]}
• code_block   – {"type":"code_block","language":"...","code":"..."}
• timeline     – {"type":"timeline","items":[{"time":"...","title":"...","description":"..."}]}
• form         – {"type":"form","title":"...","fields":[{"label":"...","type":"text|number|email|select","options":[...],"placeholder":"..."}]}
• columns      – {"type":"columns","cols":[{"width":1-12,"widgets":[...nested...]}]}
• tabs         – {"type":"tabs","tabs":[{"label":"...","widgets":[...]}]}
• accordion    – {"type":"accordion","items":[{"title":"...","widgets":[...]}]}
• json_tree    – {"type":"json_tree","data":{...}}
• file_metadata– {"type":"file_metadata","items":[{"label":"...","value":"..."}]}
• divider      – {"type":"divider"}

DESIGN RULES:
- Prefer visual widgets (charts, metrics) over plain text when data is present.
- Use columns to create dense, information-rich layouts.
- Group related info with headings and dividers.
- Always include 4–8 diverse widgets. Never more than 10 top-level items.
- Match widget semantics to content type (see adaptive rules above).
- Use markdown widget for rich formatted summaries."""


# ── File processing ────────────────────────────────────────────────────────────

def encode_image(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode()


def _csv_intelligence(df: pd.DataFrame) -> str:
    """Return an enriched CSV context with stats and column type hints."""
    lines = [f"[CSV — {len(df)} rows × {len(df.columns)} cols]"]

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(exclude="number").columns.tolist()
    time_like = [c for c in df.columns if any(k in c.lower() for k in ("date", "time", "month", "year", "week", "day"))]

    lines.append(f"Numeric columns: {numeric_cols}")
    lines.append(f"Categorical columns: {categorical_cols}")
    if time_like:
        lines.append(f"Time-like columns detected: {time_like} — prefer line_chart")

    # Basic statistics
    if numeric_cols:
        lines.append("\nColumn statistics:")
        lines.append(df[numeric_cols].describe().to_string())

    # Category cardinality
    for col in categorical_cols[:3]:
        vc = df[col].value_counts().head(8)
        lines.append(f"\nTop values in '{col}':\n{vc.to_string()}")

    # Raw preview (token-limited to 60 rows)
    lines.append("\nData preview (first 60 rows):")
    lines.append(df.head(60).to_string(index=False))

    return "\n".join(lines)


def _detect_language(filename: str) -> str:
    ext_map = {".py": "python", ".js": "javascript", ".java": "java",
               ".cpp": "cpp", ".html": "html", ".css": "css"}
    ext = os.path.splitext(filename)[1].lower()
    return ext_map.get(ext, "text")


def _extract_pdf_text(raw: bytes, filename: str) -> str:
    """Try pdfplumber then PyPDF2 for PDF text extraction."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages[:10]]
        text = "\n\n".join(pages).strip()
        if text:
            return f"[PDF: {filename} — {len(pages)} pages extracted]\n\n{text[:4000]}"
    except Exception:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(raw))
        pages = [reader.pages[i].extract_text() or "" for i in range(min(10, len(reader.pages)))]
        text = "\n\n".join(pages).strip()
        if text:
            return f"[PDF: {filename} — {len(pages)} pages]\n\n{text[:4000]}"
    except Exception:
        pass

    return f"[PDF: {filename} — could not extract text; binary content]"


def build_file_context(uploaded_file) -> tuple[str, dict | None]:
    """
    Returns (context_text, image_part_or_None).
    image_part is an OpenAI vision content dict when the file is an image.
    """
    # Guard: reset read pointer each call
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    name = uploaded_file.name
    mime = uploaded_file.type
    size_kb = len(raw) / 1024

    # ── Images ──
    if mime.startswith("image/"):
        b64 = encode_image(raw)
        image_part = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        meta = f"[Image: {name} | {size_kb:.1f} KB]"
        return meta, image_part

    # ── PDF ──
    if name.lower().endswith(".pdf"):
        return _extract_pdf_text(raw, name), None

    # ── Text-based files ──
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            return f"[Binary file: {name} — cannot decode]", None

    # Token safety: hard cap on raw text sent to API
    MAX_CHARS = 6000

    # CSV
    if name.lower().endswith(".csv"):
        try:
            df = pd.read_csv(io.StringIO(text))
            ctx = _csv_intelligence(df)
            return ctx[:MAX_CHARS], None
        except Exception as e:
            return f"[CSV parse error: {e}]\nRaw:\n{text[:2000]}", None

    # JSON
    if name.lower().endswith(".json"):
        try:
            parsed = json.loads(text)
            pretty = json.dumps(parsed, indent=2)
            # Add a short structure summary
            top_keys = list(parsed.keys()) if isinstance(parsed, dict) else f"array[{len(parsed)}]"
            summary = f"[JSON: {name} | top-level keys: {top_keys}]\n"
            return summary + pretty[:MAX_CHARS], None
        except Exception as e:
            return f"[JSON parse error: {e}]\nRaw:\n{text[:2000]}", None

    # Code files
    ext = os.path.splitext(name)[1].lower()
    if ext in (".py", ".js", ".java", ".cpp", ".html", ".css"):
        lang = _detect_language(name)
        lines = text.splitlines()
        line_count = len(lines)
        truncated = "\n".join(lines[:200])  # first 200 lines
        ctx = (
            f"[Code file: {name} | language: {lang} | {line_count} lines | {size_kb:.1f} KB]\n"
            f"Provide: syntax-highlighted viewer, documentation summary, "
            f"function/class list, imports/dependencies, architecture explanation, improvements.\n\n"
            f"{truncated}"
        )
        return ctx[:MAX_CHARS], None

    # Markdown / TXT / anything else
    return f"[{name} | {size_kb:.1f} KB]\n{text[:MAX_CHARS]}", None


# ── LLM call with true streaming ───────────────────────────────────────────────

def stream_and_collect(client: openai.OpenAI, messages: list) -> tuple[str, object]:
    """
    Stream the LLM response, show a live character counter, return (full_text, usage).
    usage object has .prompt_tokens, .completion_tokens, .total_tokens (available after stream).
    """
    status_area = st.empty()
    output_area = st.empty()

    status_area.markdown(
        '<div style="color:#6366f1;font-family:DM Mono,monospace;font-size:12px;'
        'letter-spacing:0.08em;">✦ Generating interface…</div>',
        unsafe_allow_html=True,
    )

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_completion_tokens=12000,
        stream=True,
        stream_options={"include_usage": True},
    )

    chunks = []
    char_count = 0
    usage = None
    for chunk in stream:
        # Capture usage from the final chunk (sent when stream_options include_usage=True)
        if chunk.usage is not None:
            usage = chunk.usage
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            chunks.append(delta)
            char_count += len(delta)
            output_area.markdown(
                f'<div style="font-family:DM Mono,monospace;font-size:11px;'
                f'color:#6b6b8f;">{char_count:,} chars received…</div>',
                unsafe_allow_html=True,
            )

    full_text = "".join(chunks)
    status_area.markdown(
        '<div style="color:#10b981;font-family:DM Mono,monospace;font-size:12px;">'
        f'✓ Done — {len(full_text):,} chars</div>',
        unsafe_allow_html=True,
    )
    output_area.empty()

    return full_text, usage


# ── JSON extraction & repair ───────────────────────────────────────────────────

VALID_WIDGET_TYPES = {
    "heading", "text", "markdown", "info", "warning", "success",
    "metrics", "stats_summary", "table", "bar_chart", "line_chart",
    "pie_chart", "scatter_plot", "progress", "tags", "badge_list",
    "code_block", "timeline", "form", "columns", "tabs", "accordion",
    "json_tree", "file_metadata", "divider",
}

REQUIRED_FIELDS: dict[str, list[str]] = {
    "heading":      ["text"],
    "text":         ["content"],
    "markdown":     ["content"],
    "metrics":      ["items"],
    "table":        ["headers", "rows"],
    "bar_chart":    ["data"],
    "line_chart":   ["series"],
    "pie_chart":    ["data"],
    "scatter_plot": ["data"],
    "progress":     ["items"],
    "tags":         ["items"],
    "badge_list":   ["items"],
    "code_block":   ["code"],
    "timeline":     ["items"],
    "form":         ["fields"],
    "columns":      ["cols"],
    "tabs":         ["tabs"],
    "accordion":    ["items"],
    "json_tree":    ["data"],
    "file_metadata":["items"],
    "stats_summary":["items"],
}


def _repair_json(raw: str) -> dict:
    """Multi-stage JSON extraction and repair pipeline."""
    # Strip markdown fences
    raw = re.sub(r"```(?:json|JSON)?", "", raw).strip().strip("`").strip()

    # Stage 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Stage 2: slice between first { and last }
    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model response.")
    last = raw.rfind("}")
    if last != -1 and last > start:
        try:
            return json.loads(raw[start : last + 1])
        except json.JSONDecodeError:
            pass

    # Stage 3: walk balanced braces
    depth, end = 0, -1
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end != -1:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    # Stage 4: truncation repair — close open brackets
    candidate = raw[start:]
    candidate = re.sub(r",\s*(?=[\]\}])", "", candidate)
    candidate = re.sub(r",\s*$", "", candidate.rstrip())
    open_brackets = candidate.count("[") - candidate.count("]")
    open_braces   = candidate.count("{") - candidate.count("}")
    candidate += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Stage 5: last resort — walk backward for largest valid JSON
    for end_pos in range(len(raw), start, -1):
        if raw[end_pos - 1] == "}":
            try:
                return json.loads(raw[start:end_pos])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not parse JSON from model output. Tail: …{raw[-200:]}")


def _validate_widget(w: dict) -> dict:
    """Validate a single widget dict; return a safe fallback if invalid."""
    wtype = w.get("type", "")
    if wtype not in VALID_WIDGET_TYPES:
        return {"type": "warning", "content": f"⚠ Unknown widget type: '{wtype}'"}
    for field in REQUIRED_FIELDS.get(wtype, []):
        if field not in w:
            return {"type": "warning", "content": f"⚠ Widget '{wtype}' missing required field '{field}'"}
    return w


def _validate_chart_data(w: dict) -> dict:
    """Ensure chart data arrays contain valid numeric values."""
    wtype = w.get("type", "")
    if wtype in ("bar_chart", "pie_chart"):
        clean = []
        for item in w.get("data", []):
            try:
                item["value"] = float(item["value"])
                clean.append(item)
            except (KeyError, TypeError, ValueError):
                pass
        w["data"] = clean
    elif wtype == "scatter_plot":
        clean = []
        for item in w.get("data", []):
            try:
                item["x"] = float(item["x"])
                item["y"] = float(item["y"])
                clean.append(item)
            except (KeyError, TypeError, ValueError):
                pass
        w["data"] = clean
    elif wtype == "line_chart":
        for s in w.get("series", []):
            s["data"] = [v for v in s.get("data", []) if isinstance(v, (int, float))]
    return w


def extract_json(raw: str) -> dict:
    """Parse, validate, and return a clean UI schema dict."""
    schema = _repair_json(raw)

    if not isinstance(schema, dict):
        raise ValueError("Model returned a non-object JSON value.")
    if "layout" not in schema:
        schema = {"title": "Generated UI", "layout": [schema]}

    validated = []
    for w in schema.get("layout", []):
        if not isinstance(w, dict):
            continue
        w = _validate_widget(w)
        w = _validate_chart_data(w)
        validated.append(w)

    schema["layout"] = validated
    return schema


# ── Plotly theme ───────────────────────────────────────────────────────────────
PLOTLY_COLORS = ["#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"]
PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Outfit", color="#e2e2f0"),
    margin=dict(l=20, r=20, t=40, b=20),
    template="plotly_dark",
)


# ── Widget renderer ────────────────────────────────────────────────────────────

def render_widget(w: dict):
    wtype = w.get("type", "")

    # ── Text widgets ──────────────────────────────────────────────────────────
    if wtype == "heading":
        level = w.get("level", 2)
        sizes   = {1: "2rem",   2: "1.5rem", 3: "1.2rem", 4: "1rem"}
        weights = {1: 900, 2: 800, 3: 700, 4: 600}
        st.markdown(
            f'<h{level} style="font-size:{sizes.get(level,"1.2rem")};'
            f'font-weight:{weights.get(level,700)};margin:0.5rem 0;">'
            f'{w.get("text","")}</h{level}>',
            unsafe_allow_html=True,
        )

    elif wtype == "text":
        st.markdown(
            f'<p style="color:var(--text);line-height:1.75;margin:0.4rem 0;">'
            f'{w.get("content","")}</p>',
            unsafe_allow_html=True,
        )

    elif wtype == "markdown":
        st.markdown(w.get("content", ""))

    elif wtype == "info":
        st.markdown(f'<div class="box-info">{w.get("content","")}</div>', unsafe_allow_html=True)

    elif wtype == "warning":
        st.markdown(f'<div class="box-warning">{w.get("content","")}</div>', unsafe_allow_html=True)

    elif wtype == "success":
        st.markdown(f'<div class="box-success">{w.get("content","")}</div>', unsafe_allow_html=True)

    elif wtype == "divider":
        st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Data widgets ──────────────────────────────────────────────────────────
    elif wtype == "metrics":
        items = w.get("items", [])
        if not items:
            return
        cols = st.columns(min(len(items), 4))
        for col, item in zip(cols, items):
            with col:
                delta_html = ""
                if item.get("delta"):
                    dt = item.get("delta_type", "neutral")
                    cls   = "delta-pos" if dt == "positive" else ("delta-neg" if dt == "negative" else "")
                    arrow = "▲" if dt == "positive" else ("▼" if dt == "negative" else "")
                    delta_html = f'<div class="metric-delta {cls}">{arrow} {item["delta"]}</div>'
                st.markdown(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">{item.get("label","")}</div>'
                    f'<div class="metric-value">{item.get("value","")}</div>'
                    f'{delta_html}</div>',
                    unsafe_allow_html=True,
                )

    elif wtype == "stats_summary":
        items = w.get("items", [])
        cols = st.columns(min(len(items), 4))
        for col, item in zip(cols, items):
            with col:
                unit = item.get("unit", "")
                st.markdown(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">{item.get("label","")}</div>'
                    f'<div class="metric-value" style="font-size:1.6rem;">'
                    f'{item.get("value","")} <span style="font-size:1rem;color:var(--muted);">{unit}</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    elif wtype == "table":
        headers = w.get("headers", [])
        rows    = w.get("rows", [])
        if headers and rows:
            try:
                df = pd.DataFrame(rows, columns=headers)
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Table render error: {e}")

    elif wtype == "file_metadata":
        items = w.get("items", [])
        for item in items:
            st.markdown(
                f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border);">'
                f'<span style="color:var(--muted);font-size:12px;min-width:120px;">{item.get("label","")}</span>'
                f'<span style="font-family:DM Mono,monospace;font-size:12px;">{item.get("value","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    elif wtype == "json_tree":
        data = w.get("data", {})
        st.json(data)

    # ── Chart widgets ─────────────────────────────────────────────────────────
    elif wtype == "bar_chart":
        data = w.get("data", [])
        if data:
            df = pd.DataFrame(data)
            fig = px.bar(
                df, x="label", y="value",
                title=w.get("title", ""),
                labels={"label": w.get("x_label", ""), "value": w.get("y_label", "")},
                color="value",
                color_continuous_scale=["#6366f1", "#f43f5e"],
            )
            fig.update_layout(**PLOTLY_BASE, title_font_size=14, coloraxis_showscale=False)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    elif wtype == "line_chart":
        series = w.get("series", [])
        x_vals = w.get("x_values", [])
        if series:
            fig = go.Figure()
            for i, s in enumerate(series):
                y = s.get("data", [])
                x = x_vals if x_vals else list(range(len(y)))
                fig.add_trace(go.Scatter(
                    x=x, y=y, name=s.get("name", f"Series {i+1}"),
                    mode="lines+markers",
                    line=dict(
                        color=PLOTLY_COLORS[i % len(PLOTLY_COLORS)], width=2.5,
                        shape="spline" if w.get("smooth", True) else "linear",
                    ),
                    marker=dict(size=5),
                ))
            fig.update_layout(
                **PLOTLY_BASE,
                title=w.get("title", ""),
                xaxis_title=w.get("x_label", ""),
                yaxis_title=w.get("y_label", ""),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig, use_container_width=True)

    elif wtype == "pie_chart":
        data = w.get("data", [])
        if data:
            fig = px.pie(
                names=[d["label"] for d in data],
                values=[d["value"] for d in data],
                title=w.get("title", ""),
                color_discrete_sequence=PLOTLY_COLORS,
                hole=0.42,
            )
            fig.update_layout(**PLOTLY_BASE, legend=dict(bgcolor="rgba(0,0,0,0)"))
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    elif wtype == "scatter_plot":
        data = w.get("data", [])
        if data:
            df = pd.DataFrame(data)
            fig = px.scatter(
                df, x="x", y="y",
                text="label" if "label" in df.columns else None,
                title=w.get("title", ""),
                labels={"x": w.get("x_label", "X"), "y": w.get("y_label", "Y")},
                color_discrete_sequence=["#6366f1"],
            )
            fig.update_layout(**PLOTLY_BASE)
            fig.update_traces(marker_size=10)
            st.plotly_chart(fig, use_container_width=True)

    # ── Indicator widgets ─────────────────────────────────────────────────────
    elif wtype == "progress":
        for item in w.get("items", []):
            val = max(0, min(100, int(item.get("value", 0))))
            st.markdown(
                f'<div style="margin:6px 0;">'
                f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">'
                f'<span>{item.get("label","")}</span>'
                f'<span style="font-family:DM Mono,monospace;color:var(--accent);">{val}%</span></div>'
                f'<div class="prog-wrap"><div class="prog-fill" style="width:{val}%;"></div></div></div>',
                unsafe_allow_html=True,
            )

    elif wtype == "tags":
        html = "".join(f'<span class="tag">{t}</span>' for t in w.get("items", []))
        st.markdown(f'<div style="margin:0.5rem 0;">{html}</div>', unsafe_allow_html=True)

    elif wtype == "badge_list":
        for item in w.get("items", []):
            badge_cls = {
                "success": "badge-success",
                "warning": "badge-warning",
                "error":   "badge-error",
            }.get(item.get("status", "success"), "badge-success")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
                f'border-bottom:1px solid var(--border);">'
                f'<span class="{badge_cls}">{item.get("status","").upper()}</span>'
                f'<span style="font-size:13px;">{item.get("label","")}</span></div>',
                unsafe_allow_html=True,
            )

    # ── Interactive widgets ───────────────────────────────────────────────────
    elif wtype == "form":
        with st.expander(f"📋 {w.get('title', 'Form')}", expanded=True):
            for field in w.get("fields", []):
                ftype = field.get("type", "text")
                label = field.get("label", "Field")
                if ftype == "select":
                    st.selectbox(label, field.get("options", []))
                elif ftype == "number":
                    st.number_input(label, value=0)
                else:
                    st.text_input(label, placeholder=field.get("placeholder", ""))
            st.button("Submit", key=f"form_{id(w)}")

    elif wtype == "timeline":
        for item in w.get("items", []):
            st.markdown(
                f'<div class="timeline-item">'
                f'<div class="timeline-dot"></div>'
                f'<div class="timeline-content">'
                f'<div class="timeline-time">{item.get("time","")}</div>'
                f'<div style="font-weight:700;font-size:14px;">{item.get("title","")}</div>'
                f'<div style="color:var(--muted);font-size:13px;margin-top:2px;">'
                f'{item.get("description","")}</div></div></div>',
                unsafe_allow_html=True,
            )

    elif wtype == "code_block":
        st.code(w.get("code", ""), language=w.get("language", "text"))

    # ── Layout widgets ────────────────────────────────────────────────────────
    elif wtype == "columns":
        cols_spec = w.get("cols", [])
        if cols_spec:
            widths = [c.get("width", 6) for c in cols_spec]
            cols = st.columns(widths)
            for col, spec in zip(cols, cols_spec):
                with col:
                    for child in spec.get("widgets", []):
                        render_widget(child)

    elif wtype == "tabs":
        tab_specs = w.get("tabs", [])
        if tab_specs:
            tab_labels = [t.get("label", f"Tab {i+1}") for i, t in enumerate(tab_specs)]
            st_tabs = st.tabs(tab_labels)
            for st_tab, spec in zip(st_tabs, tab_specs):
                with st_tab:
                    for child in spec.get("widgets", []):
                        render_widget(child)

    elif wtype == "accordion":
        for item in w.get("items", []):
            with st.expander(item.get("title", "Section")):
                for child in item.get("widgets", []):
                    render_widget(child)

    else:
        st.caption(f"[unknown widget type: '{wtype}']")


def render_layout(schema: dict):
    """Render a full UI schema (title + layout array)."""
    title = schema.get("title", "Generated UI")
    st.markdown(
       f'<div class="studio-header" style="display:flex; align-items:baseline; gap:12px;">'
       f'<span class="output-title">✦ {title}</span>'
       f'<span class="studio-sub">GENERATIVE INTERFACE</span>'
       f'</div>',
        unsafe_allow_html=True,
    )
    for widget in schema.get("layout", []):
        render_widget(widget)