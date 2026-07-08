"""
Visual theme for AnswerKey Studio.

Design concept: an exam answer-sheet / scantron aesthetic. Question numbers
render as scantron-style bubbles that fill in once answered; the hero reads
like the cover sheet of a test booklet; cards have a dashed "tear-off stub"
edge. Palette avoids cream+terracotta / near-black+neon defaults in favor of
a blueprint-paper background with deep exam-navy and a brass-seal gold.
"""

import streamlit as st

# ---- design tokens --------------------------------------------------------
COLORS = {
    "bg": "#EEF2F6",
    "surface": "#FFFFFF",
    "ink": "#1E2A3A",
    "muted": "#5B6B7F",
    "primary": "#1F3A5F",   # exam-navy
    "accent": "#D9A441",    # brass seal gold
    "success": "#3F7D58",   # green pen
    "danger": "#C1443C",    # red pen
    "border": "#D8DFE7",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
    --bg: {COLORS['bg']};
    --surface: {COLORS['surface']};
    --ink: {COLORS['ink']};
    --muted: {COLORS['muted']};
    --primary: {COLORS['primary']};
    --accent: {COLORS['accent']};
    --success: {COLORS['success']};
    --danger: {COLORS['danger']};
    --border: {COLORS['border']};
}}

.stApp {{
    background: var(--bg);
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--ink);
}}

h1, h2, h3 {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: var(--primary) !important;
    letter-spacing: -0.01em;
}}

footer {{ visibility: hidden; }}

/* ---- hero ------------------------------------------------------------ */
.ak-hero {{
    background: var(--primary);
    background-image: radial-gradient(circle at 92% 15%, rgba(217,164,65,0.25), transparent 45%);
    border-radius: 14px;
    padding: 28px 32px;
    margin-bottom: 6px;
    animation: ak-fade-up 0.5s ease-out;
}}
.ak-hero .ak-eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--accent);
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.ak-hero h1 {{
    color: #FFFFFF !important;
    font-size: 2.1rem !important;
    margin: 0 0 6px 0 !important;
}}
.ak-hero p {{
    color: #D9E1EC;
    margin: 0;
    font-size: 0.98rem;
}}
.ak-perforation {{
    border: none;
    border-top: 2px dashed var(--border);
    margin: 18px 0 22px 0;
}}

@keyframes ak-fade-up {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
    .ak-hero {{ animation: none; }}
}}

/* ---- badges / pills ---------------------------------------------------*/
.ak-pill {{
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    margin-right: 6px;
}}
.ak-pill.accent {{ border-color: var(--accent); color: #8A6316; background: #FBF3E1; }}
.ak-pill.success {{ border-color: var(--success); color: var(--success); background: #EAF5EE; }}
.ak-pill.danger {{ border-color: var(--danger); color: var(--danger); background: #FBEAE8; }}
.ak-pill.primary {{ border-color: var(--primary); color: var(--primary); background: #EAF0F7; }}

/* scantron bubble question number */
.ak-bubble {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 2px solid var(--primary);
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
    font-size: 0.8rem;
    margin-right: 10px;
    vertical-align: middle;
}}
.ak-bubble.filled {{
    background: var(--primary);
    color: #FFFFFF;
}}
.ak-bubble.empty {{
    background: transparent;
    color: var(--primary);
}}

/* ---- question cards ---------------------------------------------------*/
/* IMPORTANT: Streamlit reuses the SAME data-testid for several internal
   wrappers (not just our intentional st.container(border=True) cards) --
   styling that selector globally leaked a boxed/bordered look onto plain
   st.columns() groups elsewhere in the app. We scope it to only wrappers
   that contain our own .ak-card-marker element (inserted as the first
   thing inside each real question card), so nothing else is affected. */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ak-card-marker) {{
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
    border-left: 4px solid var(--accent) !important;
    background: var(--surface) !important;
    box-shadow: 0 1px 2px rgba(30,42,58,0.06);
    transition: box-shadow 0.15s ease;
    padding-top: 4px;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ak-card-marker):hover {{
    box-shadow: 0 4px 14px rgba(30,42,58,0.10);
}}
.ak-card-marker {{ display: none; }}

/* ---- buttons -----------------------------------------------------------*/
.stButton > button, .stDownloadButton > button {{
    border-radius: 8px;
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    border: 1px solid var(--border);
}}
.stButton > button[kind="primary"] {{
    background: var(--primary);
    border: none;
}}
.stButton > button[kind="primary"]:hover {{
    background: #16283F;
}}

/* ---- form inputs ---------------------------------------------------------*/
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
div[data-baseweb="select"] > div {{
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
    font-family: 'IBM Plex Sans', sans-serif;
}}
.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}}
.stTextArea textarea {{
    min-height: 130px;
}}
label[data-testid="stWidgetLabel"] p {{
    font-weight: 500;
    color: var(--muted);
    font-size: 0.85rem;
}}

/* Segmented look for the top-level "source material" style radio groups:
   flatter, no per-option shadow, tighter padding than the self-check radios. */
.stRadio [role="radiogroup"] {{
    gap: 6px;
}}
.stRadio [role="radiogroup"] label {{
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 4px 12px;
    background: #FAFBFC;
    transition: background 0.15s ease, border-color 0.15s ease;
}}
.stRadio [role="radiogroup"] label:has(input:checked) {{
    border-color: var(--primary);
    background: #EAF0F7;
}}

/* ---- tabs ---------------------------------------------------------------*/
.stTabs [data-baseweb="tab"] {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: var(--muted);
}}
.stTabs [aria-selected="true"] {{
    color: var(--primary) !important;
}}

/* ---- metrics -------------------------------------------------------------*/
[data-testid="stMetricValue"] {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--primary);
}}

/* ---- sidebar --------------------------------------------------------------*/
[data-testid="stSidebar"] {{
    background: var(--surface);
    border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] [data-testid="stExpander"] {{
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #FAFBFC;
}}
.ak-sidebar-brand {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.25rem;
    color: var(--primary);
    margin-bottom: 2px;
}}
.ak-sidebar-tag {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: var(--muted);
    margin-bottom: 18px;
}}
.ak-step {{
    display: flex;
    gap: 10px;
    margin-bottom: 14px;
}}
.ak-step-num {{
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
    color: var(--accent);
    min-width: 18px;
}}
.ak-step-text {{
    font-size: 0.85rem;
    color: var(--muted);
}}

/* ---- misc polish ----------------------------------------------------------*/
[data-testid="stAppDeployButton"] {{ display: none; }}
.block-container {{ padding-top: 2rem; }}
</style>
"""


def inject_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def render_card_marker():
    """Call this as the FIRST thing inside a `with st.container(border=True):`
    block that should get the AnswerKey card look (left accent border,
    shadow). Containers without this marker keep Streamlit's plain default
    appearance, so unrelated bordered wrappers elsewhere aren't affected."""
    st.markdown('<div class="ak-card-marker"></div>', unsafe_allow_html=True)


def render_hero(eyebrow: str, title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="ak-hero">
            <div class="ak-eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        <hr class="ak-perforation" />
        """,
        unsafe_allow_html=True,
    )


def pill(text: str, kind: str = "primary") -> str:
    return f'<span class="ak-pill {kind}">{text}</span>'


def bubble(n, filled: bool) -> str:
    state = "filled" if filled else "empty"
    return f'<span class="ak-bubble {state}">{n}</span>'


def render_sidebar_brand():
    st.markdown(
        """
        <div class="ak-sidebar-brand">🗂️ AnswerKey Studio</div>
        <div class="ak-sidebar-tag">quiz generation &amp; grading, on demand</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_steps():
    steps = [
        ("1", "Add source material — upload a file or paste text"),
        ("2", "Configure difficulty, count, and question type"),
        ("3", "Generate, self-check, export, or revisit in History"),
    ]
    html = ""
    for num, text in steps:
        html += (
            f'<div class="ak-step"><div class="ak-step-num">{num}</div>'
            f'<div class="ak-step-text">{text}</div></div>'
        )
    st.markdown(html, unsafe_allow_html=True)