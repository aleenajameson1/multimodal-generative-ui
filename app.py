"""
app.py — Sprout  (entry point)
Run with:  streamlit run app.py
All logic lives in core.py; this file owns only Streamlit layout and CSS.
"""

import streamlit as st
import openai
import json

import core  # ← all logic, rendering, config

# ── Token usage display ────────────────────────────────────────────────────────
def _render_token_usage(usage):
    """Render a compact token + cost bar below the generated UI."""
    if not usage:
        return
    pt = getattr(usage, "prompt_tokens",     0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    tt = getattr(usage, "total_tokens",      0) or pt + ct
    cost_usd = (pt * 0.00000015) + (ct * 0.0000006)
    cost_inr = cost_usd * 84
    st.markdown(
        f'''<div style="display:flex;gap:8px;margin-top:1.2rem;flex-wrap:wrap;
                        border-top:1px solid var(--border);padding-top:0.8rem;">
        <div style="background:rgba(212,168,67,0.07);border:1px solid rgba(212,168,67,0.18);
             border-radius:8px;padding:7px 14px;font-family:DM Mono,monospace;font-size:12px;">
          <span style="color:var(--muted);letter-spacing:0.1em;">IN</span>&nbsp;&nbsp;
          <span style="color:var(--text);font-weight:500;">{pt:,} tokens</span>
        </div>
        <div style="background:rgba(212,168,67,0.07);border:1px solid rgba(212,168,67,0.18);
             border-radius:8px;padding:7px 14px;font-family:DM Mono,monospace;font-size:12px;">
          <span style="color:var(--muted);letter-spacing:0.1em;">OUT</span>&nbsp;&nbsp;
          <span style="color:var(--text);font-weight:500;">{ct:,} tokens</span>
        </div>
        <div style="background:rgba(212,168,67,0.07);border:1px solid rgba(212,168,67,0.18);
             border-radius:8px;padding:7px 14px;font-family:DM Mono,monospace;font-size:12px;">
          <span style="color:var(--muted);letter-spacing:0.1em;">TOTAL</span>&nbsp;&nbsp;
          <span style="color:var(--accent);font-weight:600;">{tt:,} tokens</span>
        </div>
        <div style="background:rgba(76,175,130,0.07);border:1px solid rgba(76,175,130,0.18);
             border-radius:8px;padding:7px 14px;font-family:DM Mono,monospace;font-size:12px;">
          <span style="color:var(--muted);letter-spacing:0.1em;">COST</span>&nbsp;&nbsp;
          <span style="color:var(--emerald);font-weight:600;">\u20b9{cost_inr:.4f}</span>
          <span style="color:var(--muted);font-size:10px;margin-left:4px;">(~${cost_usd:.5f})</span>
        </div>
        </div>''',
        unsafe_allow_html=True,
    )



# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sprout",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

:root {
    --bg:       #0e0e0c;
    --surface:  #141410;
    --surface2: #1c1c17;
    --border:   #2a2a22;
    --accent:   #d4a843;
    --amber:    #f59e0b;
    --rose:     #e05a4e;
    --emerald:  #4caf82;
    --text:     #e8e6dc;
    --muted:    #6a6855;
    --radius:   10px;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

#MainMenu, footer, header { visibility: hidden; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #1c1c16 !important;
    border-right: 2px solid #3a3a28 !important;
    min-width: 260px !important;
    max-width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child {
    background: #1c1c16 !important;
    padding: 0.5rem 1rem !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
button[kind="header"] {
    background: #2a2a1e !important;
    color: var(--text) !important;
    border: 1px solid #3a3a28 !important;
}
[data-testid="collapsedControl"] {
    background: #1c1c16 !important;
    border-right: 2px solid #3a3a28 !important;
}
[data-testid="stSidebar"] .stCheckbox label {
    font-size: 13px !important;
    color: var(--text) !important;
}

/* ── Inputs ── */
.stTextArea textarea, .stTextInput input {
    background: var(--surface2) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13.5px !important;
    transition: border-color 0.2s !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(212,168,67,0.10) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--accent) !important;
    color: #0e0e0c !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 0.7rem 1.5rem !important;
    transition: opacity 0.2s, transform 0.15s !important;
    font-size: 13px !important;
}
.stButton > button:hover { opacity: 0.88; transform: translateY(-1px); }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--surface2) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-radius: var(--radius) !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    border-radius: 7px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    letter-spacing: 0.02em !important;
    padding: 0.45rem 1.1rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--surface2) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
}

/* ── Metric card ── */
.metric-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem 1.4rem;
    position: relative; overflow: hidden;
    transition: border-color 0.2s, transform 0.2s;
    margin-bottom: 0.5rem;
}
.metric-card:hover { border-color: var(--accent); transform: translateY(-2px); }
.metric-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent);
}
.metric-label {
    font-size: 11px; font-weight: 600;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 8px;
}
.metric-value { font-size: 2.2rem; font-weight: 700; color: var(--text); line-height: 1; }
.metric-delta { font-family: 'DM Mono', monospace; font-size: 12px; margin-top: 8px; }
.delta-pos { color: var(--emerald); }
.delta-neg { color: var(--rose); }

/* ── Info boxes ── */
.box-info    { background:rgba(212,168,67,0.07); border-left:3px solid var(--accent); border-radius:0 var(--radius) var(--radius) 0; padding:0.9rem 1.2rem; margin:0.4rem 0; font-size:14px; line-height:1.7; }
.box-warning { background:rgba(245,158,11,0.07); border-left:3px solid var(--amber);  border-radius:0 var(--radius) var(--radius) 0; padding:0.9rem 1.2rem; margin:0.4rem 0; font-size:14px; line-height:1.7; }
.box-success { background:rgba(76,175,130,0.07); border-left:3px solid var(--emerald);border-radius:0 var(--radius) var(--radius) 0; padding:0.9rem 1.2rem; margin:0.4rem 0; font-size:14px; line-height:1.7; }

/* ── Tag ── */
.tag {
    display: inline-block;
    background: rgba(212,168,67,0.10); color: var(--accent);
    border: 1px solid rgba(212,168,67,0.22); border-radius: 20px;
    padding: 3px 12px; font-size: 12px; font-weight: 500;
    margin: 2px; letter-spacing: 0.03em;
}

/* ── Progress ── */
.prog-wrap { background: var(--surface2); border-radius: 9999px; height: 6px; overflow: hidden; margin: 4px 0; }
.prog-fill  { height: 100%; border-radius: 9999px; background: var(--accent); transition: width 0.4s ease; }

/* ── Timeline ── */
.timeline-item    { display: flex; gap: 14px; padding: 10px 0; border-bottom: 1px solid var(--border); }
.timeline-dot     { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-top: 7px; flex-shrink: 0; }
.timeline-content { flex: 1; }
.timeline-time    { font-family: 'DM Mono', monospace; font-size: 11px; color: var(--muted); }

/* ── Badges ── */
.badge-success { background:rgba(76,175,130,0.10); color:var(--emerald); border:1px solid rgba(76,175,130,0.25); border-radius:6px; padding:3px 9px; font-size:12px; font-weight:500; }
.badge-warning { background:rgba(245,158,11,0.10); color:var(--amber);   border:1px solid rgba(245,158,11,0.25); border-radius:6px; padding:3px 9px; font-size:12px; font-weight:500; }
.badge-error   { background:rgba(224,90,78,0.10);  color:var(--rose);    border:1px solid rgba(224,90,78,0.25);  border-radius:6px; padding:3px 9px; font-size:12px; font-weight:500; }

/* ── Divider ── */
.divider { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }

/* ── Section label ── */
.section-label {
    font-size: 10px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--muted); margin: 1rem 0 0.4rem;
}

/* ── Sprout header ── */
.sprout-header {
    display: flex; align-items: center; gap: 16px;
    padding: 1.6rem 0 1.3rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.8rem;
}
.sprout-logo-wrap {
    flex-shrink: 0;
}
.sprout-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.75rem; font-weight: 800;
    color: var(--text);
    letter-spacing: -0.01em;
    line-height: 1;
}
.sprout-sub {
    font-family: 'DM Mono', monospace; font-size: 10px;
    color: var(--muted); letter-spacing: 0.14em;
    margin-top: 5px;
    text-transform: uppercase;
}

/* ── Output title ── */
.output-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.3rem; font-weight: 700;
    color: var(--text);
    margin-bottom: 0.3rem;
}

/* ── Status pill ── */
.status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(76,175,130,0.08); color: var(--emerald);
    border: 1px solid rgba(76,175,130,0.18); border-radius: 20px;
    padding: 4px 12px; font-size: 12px; font-weight: 500;
}
.status-dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--emerald);
    animation: pulse 1.8s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Model badge ── */
.model-badge {
    display: inline-block;
    background: rgba(212,168,67,0.08); color: var(--accent);
    border: 1px solid rgba(212,168,67,0.18); border-radius: 6px;
    padding: 3px 10px; font-family: 'DM Mono', monospace; font-size: 11px; font-weight: 400;
}
</style>
""", unsafe_allow_html=True)

# ── Sprout logo SVG (inline, matching the uploaded icon) ───────────────────────
SPROUT_LOGO_SVG = """
<svg width="38" height="38" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- central node -->
  <circle cx="50" cy="52" r="5" fill="#e8e6dc"/>
  <!-- branches -->
  <line x1="50" y1="52" x2="50" y2="20" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="18" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="82" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="26" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="74" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <!-- branch tip nodes -->
  <circle cx="50" cy="20" r="4.5" fill="#e8e6dc"/>
  <circle cx="18" cy="52" r="4.5" fill="#e8e6dc"/>
  <circle cx="82" cy="52" r="4.5" fill="#e8e6dc"/>
  <circle cx="26" cy="76" r="4.5" fill="#e8e6dc"/>
  <circle cx="74" cy="76" r="4.5" fill="#e8e6dc"/>
  <!-- leaf (golden) attached near top branch -->
  <ellipse cx="64" cy="32" rx="11" ry="6.5" transform="rotate(-38 64 32)" fill="#d4a843" stroke="#e8e6dc" stroke-width="2"/>
</svg>
"""

SPROUT_SIDEBAR_LOGO = """
<svg width="28" height="28" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="52" r="5" fill="#e8e6dc"/>
  <line x1="50" y1="52" x2="50" y2="20" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="18" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="82" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="26" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="74" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="50" cy="20" r="4.5" fill="#e8e6dc"/>
  <circle cx="18" cy="52" r="4.5" fill="#e8e6dc"/>
  <circle cx="82" cy="52" r="4.5" fill="#e8e6dc"/>
  <circle cx="26" cy="76" r="4.5" fill="#e8e6dc"/>
  <circle cx="74" cy="76" r="4.5" fill="#e8e6dc"/>
  <ellipse cx="64" cy="32" rx="11" ry="6.5" transform="rotate(-38 64 32)" fill="#d4a843" stroke="#e8e6dc" stroke-width="2"/>
</svg>
"""

# ── Force sidebar open via JS ──────────────────────────────────────────────────
st.markdown("""
<style>
/* Force sidebar to always show — never collapse */
[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
    display: block !important;
}
section[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    width: 260px !important;
    min-width: 260px !important;
    transform: none !important;
}
/* Hide the collapse arrow button */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}
button[data-testid="baseButton-header"] {
    display: none !important;
}
</style>
<script>
(function() {
    function expandSidebar() {
        var sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        if (sidebar && sidebar.getAttribute('aria-expanded') === 'false') {
            var btn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]');
            if (btn) btn.click();
        }
    }
    setTimeout(expandSidebar, 300);
    setTimeout(expandSidebar, 800);
})();
</script>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:1rem 0 0.6rem;">'
        f'{SPROUT_SIDEBAR_LOGO}'
        f'<div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:1.2rem;font-weight:800;letter-spacing:-0.01em;">Sprout</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if core.OPENAI_API_KEY:
        st.markdown(
            '<div class="status-pill" style="margin:0.4rem 0 1rem;">'
            '<span class="status-dot"></span>Connected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.error("⚠ OPENAI_API_KEY not found in .env")

    st.markdown('<hr style="border-color:#2a2a22;margin:0.2rem 0 0.8rem;">', unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:10px;color:#6a6855;letter-spacing:0.12em;margin-bottom:0.5rem;text-transform:uppercase;">Options</div>',
        unsafe_allow_html=True,
    )
    show_raw    = st.checkbox("Show raw JSON schema", value=False)
    show_prompt = st.checkbox("Show composed prompt", value=False)

    st.markdown('<hr style="border-color:#2a2a22;margin:0.8rem 0;">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#6a6855;line-height:1.75;">'
        'Accepts <b style="color:#a09880;">text</b>, '
        '<b style="color:#a09880;">CSV / JSON</b>, '
        '<b style="color:#a09880;">code files</b>, '
        '<b style="color:#a09880;">PDFs</b>, '
        'and <b style="color:#a09880;">images</b>.'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Main header ────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="sprout-header">'
    f'<div class="sprout-logo-wrap">{SPROUT_LOGO_SVG}</div>'
    f'<div>'
    f'<div class="sprout-title">Sprout</div>'
    f'<div class="sprout-sub">Interface Generator</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

input_tab, output_tab = st.tabs(["  ◈  Input  ", "  ◈  Generated UI  "])


# ── Input tab ──────────────────────────────────────────────────────────────────
with input_tab:
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown('<div class="section-label">Prompt / Instruction</div>', unsafe_allow_html=True)
        user_text = st.text_area(
            label="",
            placeholder=(
                "Describe the interface you need, paste data, or ask a question…\n\n"
                "Examples:\n"
                "• Show Q3 sales data for 5 regions\n"
                "• Analyse this Python file and explain the architecture\n"
                "• Create a project status dashboard\n"
                "• Build an employee onboarding form\n"
                "• Analyse this CSV and visualise key trends"
            ),
            height=230,
            label_visibility="collapsed",
        )

    with col_right:
        st.markdown('<div class="section-label">File Upload (optional)</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            label="",
            type=core.SUPPORTED_TYPES,
            label_visibility="collapsed",
            help=(
                "Images → vision analysis. CSV/JSON → auto charts & stats. "
                "Code files → architecture review. PDF/TXT → summaries."
            ),
        )
        if uploaded_file:
            if uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, use_column_width=True)
            else:
                size_kb = uploaded_file.size / 1024
                st.markdown(
                    f'<div class="box-info">📎 <b>{uploaded_file.name}</b><br>'
                    f'<span style="font-family:DM Mono,monospace;font-size:11px;color:var(--muted);">'
                    f'{size_kb:.1f} KB &nbsp;·&nbsp; {uploaded_file.size:,} bytes</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    generate_btn = st.button("✴ Generate Interface", use_container_width=True)


# ── Generation ─────────────────────────────────────────────────────────────────
if generate_btn:
    if not core.OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not found. Add it to your .env file.")
        st.stop()
    if not user_text and not uploaded_file:
        st.warning("Please provide a prompt or upload a file.")
        st.stop()

    loading = st.empty()
    loading.markdown(
        '<div style="color:var(--accent);font-family:DM Mono,monospace;font-size:12px;'
        'letter-spacing:0.08em;">⏳ Analyzing…</div>',
        unsafe_allow_html=True,
    )

    content_parts = []
    file_context  = ""

    if uploaded_file:
        file_context, image_part = core.build_file_context(uploaded_file)
        if image_part:
            content_parts.append(image_part)

    loading.markdown(
        '<div style="color:var(--accent);font-family:DM Mono,monospace;font-size:12px;'
        'letter-spacing:0.08em;">⏳ Generating layout…</div>',
        unsafe_allow_html=True,
    )

    prompt_parts = []
    if user_text:
        prompt_parts.append(user_text)
    if file_context:
        prompt_parts.append(file_context)
    final_prompt = "\n\n".join(prompt_parts)

    if show_prompt:
        with st.expander("🔍 Composed prompt"):
            st.code(final_prompt, language="text")

    content_parts.append({"type": "text", "text": final_prompt})
    messages = [
        {"role": "system", "content": core.SYSTEM_PROMPT},
        {"role": "user",   "content": content_parts},
    ]

    loading.empty()

    raw_response = ""
    schema = {}

    try:
        client = openai.OpenAI(api_key=core.OPENAI_API_KEY)
        raw_response, usage = core.stream_and_collect(client, messages)

        render_status = st.empty()
        render_status.markdown(
            '<div style="color:var(--accent);font-family:DM Mono,monospace;font-size:12px;'
            'letter-spacing:0.08em;">⏳ Rendering…</div>',
            unsafe_allow_html=True,
        )

        schema = core.extract_json(raw_response)

        st.session_state["last_schema"] = schema
        st.session_state["last_raw"]    = raw_response
        st.session_state["last_usage"]  = usage

        render_status.empty()

        if show_raw:
            with st.expander("🗂 Raw JSON schema"):
                st.code(json.dumps(schema, indent=2), language="json")

        with output_tab:
            core.render_layout(schema)
            _render_token_usage(usage)

        st.success("✓ Interface generated — click the **Generated UI** tab to view it.")

    except ValueError as e:
        st.error(f"JSON extraction failed: {e}")
        if raw_response:
            with st.expander("Raw model output"):
                st.code(raw_response, language="text")
    except openai.AuthenticationError:
        st.error("Invalid API key. Check your .env file.")
    except openai.RateLimitError:
        st.error("Rate limit hit. Wait a moment and try again.")
    except openai.BadRequestError as e:
        st.error(f"Bad request: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        if raw_response:
            with st.expander("Raw model output"):
                st.code(raw_response, language="text")


# ── Output tab — persists via session state ─────────────────────────────────────
with output_tab:
    if "last_schema" in st.session_state:
        if not generate_btn:
            core.render_layout(st.session_state["last_schema"])
            _render_token_usage(st.session_state.get("last_usage"))
        if show_raw and "last_raw" in st.session_state and not generate_btn:
            with st.expander("🗂 Raw JSON schema"):
                st.code(json.dumps(st.session_state["last_schema"], indent=2), language="json")
    else:
        st.markdown(
            '<div style="text-align:center;padding:5rem 0;">'
            '<svg width="52" height="52" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="opacity:0.22;margin-bottom:1.2rem;">'
            '<circle cx="50" cy="52" r="5" fill="#e8e6dc"/>'
            '<line x1="50" y1="52" x2="50" y2="20" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>'
            '<line x1="50" y1="52" x2="18" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>'
            '<line x1="50" y1="52" x2="82" y2="52" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>'
            '<line x1="50" y1="52" x2="26" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>'
            '<line x1="50" y1="52" x2="74" y2="76" stroke="#e8e6dc" stroke-width="3.5" stroke-linecap="round"/>'
            '<circle cx="50" cy="20" r="4.5" fill="#e8e6dc"/>'
            '<circle cx="18" cy="52" r="4.5" fill="#e8e6dc"/>'
            '<circle cx="82" cy="52" r="4.5" fill="#e8e6dc"/>'
            '<circle cx="26" cy="76" r="4.5" fill="#e8e6dc"/>'
            '<circle cx="74" cy="76" r="4.5" fill="#e8e6dc"/>'
            '<ellipse cx="64" cy="32" rx="11" ry="6.5" transform="rotate(-38 64 32)" fill="#d4a843" stroke="#e8e6dc" stroke-width="2"/>'
            '</svg>'
            '<div style="font-size:1rem;font-weight:600;color:var(--muted);">Nothing here yet</div>'
            '<div style="font-size:13px;color:#3a3830;margin-top:0.4rem;">'
            'Enter a prompt and click Generate Interface</div>'
            '</div>',
            unsafe_allow_html=True,
        )