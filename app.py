import os
import sys

# Insert (not append) an absolute path to this project's own src/ folder at
# the FRONT of sys.path. This guarantees Python finds THIS mcqgenrator
# package first, even if another copy (e.g. from an older project) is
# importable from somewhere else on the system -- append() would put ours
# last, letting a stray install shadow it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import json
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain.callbacks import get_openai_callback

from mcqgenrator.utils import (
    read_file,
    combine_texts,
    get_table_data,
    quiz_dict_from_str,
    estimate_min_word_count,
    export_to_csv_bytes,
    export_to_docx_bytes,
    export_to_pdf_bytes,
    export_to_gift_bytes,
    export_to_quizlet_tsv_bytes,
)
from mcqgenrator.MCQGenerator import (
    generate_evaluate_chain,
    regenerate_single_question,
    auto_detect_subject,
    QUESTION_TYPES,
)
from mcqgenrator.providers import MissingAPIKeyError, ProviderUnavailableError, available_providers
from mcqgenrator.youtube_source import read_youtube_transcript
from mcqgenrator import history, theme, cache, ratelimit, social

load_dotenv()

st.set_page_config(page_title="AnswerKey Studio", page_icon="🗂️", layout="wide")
theme.inject_theme()

RESPONSE_JSON_FILES = {
    "Multiple Choice": "Response_mcq.json",
    "True / False": "Response_tf.json",
    "Fill in the Blank": "Response_fib.json",
    "Short Answer": "Response_sa.json",
    "Mixed": "Response_mixed.json",
}
RESPONSE_JSONS = {}
for qtype, fname in RESPONSE_JSON_FILES.items():
    with open(fname, "r") as f:
        RESPONSE_JSONS[qtype] = json.load(f)

LANGUAGES = ["English", "Spanish", "French", "German", "Hindi", "Portuguese", "Chinese", "Japanese", "Arabic"]
STYLES = ["Concise", "Scenario-based", "Exam-style", "Conversational"]

DEFAULTS = {
    "quiz_result": None,
    "quiz_df": None,
    "quiz_meta": {},
    "answers_checked": False,
    "quizzes_this_session": 0,
    "youtube_text": None,
    "current_share_code": None,
    "last_score": None,
    "quiz_start_time": None,
    "pending_subject": None,
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# A widget's session_state value can only be set BEFORE that widget is
# instantiated in a given script run -- so the auto-detect button (further
# down) can't write st.session_state.subject_input directly after the
# text_input already exists. Instead it stashes the value in
# pending_subject and reruns; we apply it here, ahead of the widget.
if st.session_state.pending_subject is not None:
    st.session_state.subject_input = st.session_state.pending_subject
    st.session_state.pending_subject = None

# --------------------------------------------------------------------------- #
# SIDEBAR -- branding, global generation settings, live stats
# --------------------------------------------------------------------------- #
with st.sidebar:
    theme.render_sidebar_brand()
    theme.render_sidebar_steps()
    st.divider()

    with st.expander("⚙️ Generation settings", expanded=True):
        providers_list = available_providers()
        if not providers_list:
            st.error("No LLM provider packages installed. Check requirements.txt.")
            selected_provider = None
        else:
            selected_provider = st.selectbox("LLM provider", providers_list)
        language = st.selectbox("Quiz language", LANGUAGES)
        style = st.selectbox("Question style", STYLES)
        use_cache = st.checkbox("Reuse cached results", value=True)
        timed_mode = st.checkbox("⏱️ Timed mode", value=False)

    st.divider()
    all_time = history.get_history_df()
    cache_stats = cache.stats()
    s1, s2 = st.columns(2)
    s1.metric("This session", st.session_state.quizzes_this_session)
    s2.metric("All-time", len(all_time))
    st.caption(f"⚡ {cache_stats['cache_hits_served']} cache hits · {cache_stats['entries']} cached")
    if not all_time.empty:
        total_cost = all_time["total_cost"].fillna(0).sum()
        st.caption(f"💵 ${total_cost:.4f} spent all-time")

# --------------------------------------------------------------------------- #
# HERO
# --------------------------------------------------------------------------- #
theme.render_hero(
    eyebrow="FORM AK-01 · AUTOMATED QUIZ GENERATION",
    title="🗂️ AnswerKey Studio",
    subtitle="Turn a PDF, text file, pasted passage, or YouTube video into a graded answer sheet.",
)

tab_create, tab_share, tab_history = st.tabs(
    ["✨ Create Quiz", "🔗 Share & Leaderboard", "📊 History & Analytics"]
)


def render_quiz_and_selfcheck(source_text_for_regen: str = None):
    """Renders the results table, self-check, exports, and regenerate controls
    for whatever quiz is currently in session_state -- used by both the
    Create tab (just-generated quiz) and after loading a quiz from History
    or a share code."""
    df = st.session_state.quiz_df
    meta = st.session_state.quiz_meta

    st.markdown('<hr class="ak-perforation" />', unsafe_allow_html=True)
    st.subheader(f"📝 {meta['subject']} Quiz")
    st.markdown(
        theme.pill(meta["tone"], "accent")
        + theme.pill(meta["question_type"], "primary")
        + theme.pill(f"{len(df)} questions", "success"),
        unsafe_allow_html=True,
    )
    if st.session_state.current_share_code:
        st.markdown(theme.pill(f"share code: {st.session_state.current_share_code}", "danger"), unsafe_allow_html=True)
    st.write("")

    st.dataframe(df, use_container_width=True)

    with st.expander("📋 Expert Review"):
        st.write(meta.get("review", ""))

    # ---- interactive self-check quiz ------------------------------------
    st.subheader("🧪 Try it yourself")
    quiz_dict = quiz_dict_from_str(st.session_state.quiz_result) or {}

    if timed_mode and st.session_state.quiz_start_time is None:
        st.session_state.quiz_start_time = time.time()

    user_answers = {}
    for i, (qid, qdata) in enumerate(list(quiz_dict.items()), start=1):
        qtype = qdata.get("type", "mcq")
        widget_key = f"answer_{qid}_{i}_{meta['subject']}"
        already_answered = st.session_state.get(widget_key) not in (None, "")

        with st.container(border=True):
            theme.render_card_marker()
            top_col, regen_col = st.columns([6, 1])
            with top_col:
                st.markdown(
                    theme.bubble(i, filled=already_answered) + f"**{qdata.get('question', '')}**",
                    unsafe_allow_html=True,
                )
                if qdata.get("bloom_level"):
                    st.markdown(theme.pill(qdata["bloom_level"], "accent"), unsafe_allow_html=True)
            with regen_col:
                regen_disabled = source_text_for_regen is None or selected_provider is None
                if st.button("🔁", key=f"regen_{qid}_{i}", help="Regenerate this question", disabled=regen_disabled):
                    try:
                        with st.spinner("Regenerating..."):
                            new_q = regenerate_single_question(
                                text=source_text_for_regen,
                                subject=meta["subject"],
                                tone=meta["tone"],
                                old_question=qdata,
                                language=language,
                                provider=selected_provider,
                            )
                        quiz_dict[qid] = new_q
                        st.session_state.quiz_result = json.dumps(quiz_dict)
                        st.session_state.quiz_df = pd.DataFrame(get_table_data(st.session_state.quiz_result))
                        st.session_state.quiz_df.index = st.session_state.quiz_df.index + 1
                        st.rerun()
                    except (MissingAPIKeyError, ProviderUnavailableError) as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Couldn't regenerate: {e}")

            if qtype == "mcq" and "options" in qdata:
                opts = list(qdata["options"].items())
                user_answers[qid] = st.radio(
                    "Choose one", options=[o[0] for o in opts],
                    format_func=lambda k, opts=dict(opts): f"{k}) {opts[k]}",
                    key=widget_key, index=None, label_visibility="collapsed",
                )
            elif qtype == "true_false":
                user_answers[qid] = st.radio(
                    "Choose one", options=["True", "False"],
                    key=widget_key, index=None, label_visibility="collapsed",
                )
            elif qtype == "fill_blank":
                user_answers[qid] = st.text_input(
                    "Your answer", key=widget_key, label_visibility="collapsed",
                    placeholder="Type the missing word/phrase...",
                )
            else:  # short_answer -- not auto-graded, just self-compare
                user_answers[qid] = st.text_area(
                    "Your answer", key=widget_key, label_visibility="collapsed", height=80,
                    placeholder="Type your answer, then check against the model answer below...",
                )

    if st.button("Check my answers"):
        st.session_state.answers_checked = True

    if st.session_state.answers_checked:
        correct_count, gradable_total = 0, 0
        for qid, qdata in quiz_dict.items():
            qtype = qdata.get("type", "mcq")
            correct = str(qdata.get("correct", "")).strip()
            given = user_answers.get(qid)

            is_correct = None
            if qtype in ("mcq", "true_false"):
                gradable_total += 1
                is_correct = given is not None and str(given).strip().lower() == correct.lower()
            elif qtype == "fill_blank":
                gradable_total += 1
                is_correct = given is not None and str(given).strip().lower() == correct.strip().lower()

            if is_correct:
                correct_count += 1
            if is_correct is not None:
                social.log_attempt(
                    qdata.get("question", ""), is_correct, subject=meta["subject"],
                    code=st.session_state.current_share_code,
                )

            if qtype == "short_answer":
                with st.expander(f"Model answer — {qdata.get('question', '')[:50]}..."):
                    st.write(f"**Model answer:** {correct}")
                    if qdata.get("explanation"):
                        st.caption(qdata["explanation"])

        seconds_taken = None
        if timed_mode and st.session_state.quiz_start_time:
            seconds_taken = round(time.time() - st.session_state.quiz_start_time, 1)

        if gradable_total > 0 and correct_count == gradable_total:
            st.balloons()

        score_msg = f"Score: {correct_count} / {gradable_total}" if gradable_total else "No auto-graded questions in this quiz."
        if seconds_taken is not None:
            score_msg += f"  ·  ⏱️ {seconds_taken}s"
        st.success(score_msg)
        st.session_state.last_score = (correct_count, gradable_total, seconds_taken)

        with st.expander("📖 Explanations"):
            for qid, qdata in quiz_dict.items():
                if qdata.get("explanation"):
                    st.markdown(f"**{qdata.get('question','')}**  \n{qdata['explanation']}")

    # ---- exports ----------------------------------------------------------
    st.subheader("⬇️ Export")
    e1, e2, e3, e4, e5, e6 = st.columns(6)
    with e1:
        st.download_button("CSV", export_to_csv_bytes(df), file_name="quiz.csv", mime="text/csv")
    with e2:
        st.download_button(
            "Word", export_to_docx_bytes(df, meta.get("review", ""), meta["subject"], meta["tone"]),
            file_name="quiz.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with e3:
        st.download_button(
            "PDF", export_to_pdf_bytes(df, meta.get("review", ""), meta["subject"], meta["tone"]),
            file_name="quiz.pdf", mime="application/pdf",
        )
    with e4:
        st.download_button("JSON", st.session_state.quiz_result, file_name="quiz.json", mime="application/json")
    with e5:
        st.download_button(
            "GIFT", export_to_gift_bytes(quiz_dict, meta["subject"]), file_name="quiz.gift", mime="text/plain"
        )
    with e6:
        st.download_button(
            "Quizlet", export_to_quizlet_tsv_bytes(quiz_dict), file_name="quiz_quizlet.tsv", mime="text/tab-separated-values"
        )

    st.subheader("🔗 Share this quiz")
    if st.button("Get a shareable code"):
        code = social.create_share(
            meta["subject"], meta["tone"], meta["question_type"], st.session_state.quiz_result, meta.get("review", "")
        )
        st.session_state.current_share_code = code
        st.success(f"Share code: **{code}** — others can load it from the 'Share & Leaderboard' tab.")


# --------------------------------------------------------------------------- #
# CREATE QUIZ TAB
# --------------------------------------------------------------------------- #
with tab_create:
    input_mode = st.radio("Source material", ["Upload files", "Paste text", "YouTube URL"], horizontal=True)

    uploaded_files, pasted_text = None, None
    if input_mode == "Upload files":
        uploaded_files = st.file_uploader(
            "Upload one or more PDF/TXT files", type=["pdf", "txt"], accept_multiple_files=True
        )
    elif input_mode == "Paste text":
        pasted_text = st.text_area(
            "Paste your source text here", height=180,
            placeholder="Paste an article, chapter, notes, or any passage you want quiz questions generated from...",
        )
    else:
        yt_url = st.text_input("YouTube video URL")
        if st.button("📥 Fetch transcript"):
            try:
                with st.spinner("Fetching transcript..."):
                    st.session_state.youtube_text = read_youtube_transcript(yt_url)
                st.success(f"Fetched transcript (~{len(st.session_state.youtube_text.split())} words).")
            except Exception as e:
                st.error(str(e))
        if st.session_state.youtube_text:
            with st.expander("Preview fetched transcript"):
                st.write(st.session_state.youtube_text[:1500] + "...")

    source_text = None
    if input_mode == "Upload files" and uploaded_files:
        texts = []
        for f in uploaded_files:
            try:
                texts.append(read_file(f))
            except Exception as e:
                st.error(f"{f.name}: {e}")
        source_text = combine_texts(texts) if texts else None
    elif input_mode == "Paste text" and pasted_text and pasted_text.strip():
        source_text = pasted_text
    elif input_mode == "YouTube URL":
        source_text = st.session_state.youtube_text

    col1, col2, col3 = st.columns(3)
    with col1:
        mcq_count = st.number_input("No. of questions", min_value=3, max_value=50, value=5)
    with col2:
        subj_col1, subj_col2 = st.columns([3, 1])
        with subj_col1:
            subject = st.text_input("Subject", key="subject_input", max_chars=40, placeholder="e.g. Biology")
        with subj_col2:
            st.write("")
            st.write("")
            if st.button("🔍", help="Auto-detect subject from source text"):
                if source_text and selected_provider:
                    try:
                        with st.spinner("Detecting..."):
                            st.session_state.pending_subject = auto_detect_subject(source_text, provider=selected_provider)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Add source material first.")
    with col3:
        tone = st.selectbox("Difficulty", ["Simple", "Medium", "Hard"], index=0)

    question_type = st.selectbox("Question type", list(QUESTION_TYPES.keys()))

    generate_clicked = st.button("🚀 Create Quiz", type="primary", disabled=selected_provider is None)

    if generate_clicked:
        if not source_text:
            st.warning("Please add source material first (upload a file, paste text, or fetch a transcript).")
        elif not subject:
            st.warning("Please enter a subject.")
        elif len(source_text.split()) < estimate_min_word_count(mcq_count):
            st.warning(
                f"Your source text looks short for {mcq_count} questions "
                f"(~{estimate_min_word_count(mcq_count)} words recommended). You can still try, but quality may suffer."
            )
        else:
            allowed, wait = ratelimit.check_rate_limit(st.session_state, max_calls=5, window_seconds=60)
            if not allowed:
                st.warning(f"Rate limit reached — try again in {wait:.0f}s (max 5 generations/min).")
            else:
                response_json = RESPONSE_JSONS[question_type]
                cache_key = cache.make_key(
                    text=source_text, number=mcq_count, subject=subject, tone=tone,
                    question_type=question_type, language=language, style=style, provider=selected_provider,
                )
                cached = cache.get(cache_key) if use_cache else None

                start_time = time.time()
                response, from_cache, cb = None, False, None
                with st.status("Generating your quiz..." if not cached else "Found a cached result...", expanded=True) as status:
                    try:
                        if cached:
                            response = {"quiz": cached["quiz"], "review": cached["review"]}
                            from_cache = True
                            status.write("⚡ Served from cache — no API call made.")
                        else:
                            status.write("📖 Reading and preparing source text...")
                            status.write("🧠 Generating questions and expert review...")
                            with get_openai_callback() as cb:
                                response = generate_evaluate_chain(
                                    {
                                        "text": source_text, "number": mcq_count, "subject": subject,
                                        "tone": tone, "response_json": json.dumps(response_json),
                                    },
                                    question_type=question_type, provider=selected_provider,
                                    language=language, style=style,
                                )
                        elapsed = time.time() - start_time
                        status.write(f"✅ Done in {elapsed:.1f}s")
                        status.update(label="Quiz generated!", state="complete")
                    except MissingAPIKeyError as e:
                        status.update(label="Missing API key", state="error")
                        st.error(str(e))
                        response = None
                    except ProviderUnavailableError as e:
                        status.update(label="Provider unavailable", state="error")
                        st.error(str(e))
                        response = None
                    except Exception as e:
                        status.update(label="Generation failed", state="error")
                        st.error(f"Something went wrong: {e}")
                        with st.expander("Technical details"):
                            st.code(str(e))
                        response = None

                if response is not None:
                    quiz = response.get("quiz")
                    review = response.get("review", "")
                    table_data = get_table_data(quiz) if quiz else False

                    if table_data:
                        df = pd.DataFrame(table_data)
                        df.index = df.index + 1

                        st.session_state.quiz_result = quiz
                        st.session_state.quiz_df = df
                        st.session_state.answers_checked = False
                        st.session_state.quiz_start_time = None
                        st.session_state.current_share_code = None
                        st.session_state.quizzes_this_session += 1
                        st.session_state.quiz_meta = {
                            "review": review, "subject": subject, "tone": tone,
                            "question_type": question_type, "source_text": source_text,
                        }

                        if not from_cache:
                            cache.set(cache_key, quiz, review)

                        history.save_quiz_record(
                            subject=subject, tone=tone, question_type=question_type,
                            num_questions=int(mcq_count), quiz_json=quiz, review=review,
                            total_tokens=cb.total_tokens if cb else None,
                            prompt_tokens=cb.prompt_tokens if cb else None,
                            completion_tokens=cb.completion_tokens if cb else None,
                            total_cost=cb.total_cost if cb else 0.0,
                            provider=selected_provider, language=language,
                        )
                    else:
                        st.error("The model's response couldn't be parsed into a table. Try again.")

    if st.session_state.quiz_df is not None:
        render_quiz_and_selfcheck(source_text_for_regen=st.session_state.quiz_meta.get("source_text"))

# --------------------------------------------------------------------------- #
# SHARE & LEADERBOARD TAB
# --------------------------------------------------------------------------- #
with tab_share:
    st.subheader("Load a shared quiz")
    code_input = st.text_input("Enter a 6-character share code")
    if st.button("Load quiz"):
        rec = social.get_share(code_input)
        if rec is None:
            st.error("No quiz found for that code.")
        else:
            table_data = get_table_data(rec["quiz_json"])
            if table_data:
                df = pd.DataFrame(table_data)
                df.index = df.index + 1
                st.session_state.quiz_result = rec["quiz_json"]
                st.session_state.quiz_df = df
                st.session_state.answers_checked = False
                st.session_state.quiz_start_time = None
                st.session_state.current_share_code = rec["code"]
                st.session_state.quiz_meta = {
                    "review": rec["review"], "subject": rec["subject"], "tone": rec["tone"],
                    "question_type": rec["question_type"], "source_text": None,
                }
                st.success(f"Loaded quiz {rec['code']}! Scroll down or check the Create tab.")

    if st.session_state.current_share_code:
        st.divider()
        st.subheader(f"🏆 Leaderboard — {st.session_state.current_share_code}")
        if st.session_state.last_score:
            correct, total, seconds_taken = st.session_state.last_score
            with st.form("submit_score_form"):
                player_name = st.text_input("Your name")
                submitted = st.form_submit_button("Submit my score")
                if submitted and player_name:
                    social.submit_score(
                        st.session_state.current_share_code, player_name, correct, total, seconds_taken
                    )
                    st.success("Score submitted!")
        else:
            st.info("Answer the quiz in the Create tab, then come back here to submit your score.")

        lb = social.get_leaderboard(st.session_state.current_share_code)
        if lb.empty:
            st.caption("No scores submitted yet for this quiz.")
        else:
            st.dataframe(lb, use_container_width=True)

# --------------------------------------------------------------------------- #
# HISTORY & ANALYTICS TAB
# --------------------------------------------------------------------------- #
with tab_history:
    st.subheader("Past quizzes")
    hist_df = history.get_history_df()

    if hist_df.empty:
        st.info("No quizzes generated yet. Create one in the first tab!")
    else:
        h1, h2, h3 = st.columns(3)
        h1.metric("Total quizzes", len(hist_df))
        h2.metric("Total questions", int(hist_df["num_questions"].fillna(0).sum()))
        h3.metric("Total cost", f"${hist_df['total_cost'].fillna(0).sum():.4f}")

        st.dataframe(hist_df, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.caption("Token usage over time")
            st.line_chart(hist_df.set_index("created_at")[["total_tokens"]])
        with c2:
            st.caption("Cost over time")
            st.line_chart(hist_df.set_index("created_at")[["total_cost"]])

        selected_id = st.selectbox(
            "Reload a past quiz", options=hist_df["id"].tolist(),
            format_func=lambda i: f"#{i} — {hist_df.loc[hist_df['id']==i, 'subject'].values[0]}",
        )
        if st.button("Load selected quiz"):
            rec = history.get_record(int(selected_id))
            table_data = get_table_data(rec["quiz_json"])
            if table_data:
                df = pd.DataFrame(table_data)
                df.index = df.index + 1
                st.session_state.quiz_result = rec["quiz_json"]
                st.session_state.quiz_df = df
                st.session_state.answers_checked = False
                st.session_state.quiz_start_time = None
                st.session_state.current_share_code = None
                st.session_state.quiz_meta = {
                    "review": rec["review"], "subject": rec["subject"], "tone": rec["tone"],
                    "question_type": rec["question_type"], "source_text": None,
                }
                st.success("Loaded! Switch to the 'Create Quiz' tab to view it.")

        if st.button("🗑️ Clear all history", type="secondary"):
            history.clear_history()
            st.rerun()

    st.divider()
    st.subheader("🎯 Hardest questions (across every attempt, any quiz)")
    hard_df = social.hardest_questions()
    if hard_df.empty:
        st.caption("No self-check attempts logged yet.")
    else:
        st.dataframe(hard_df, use_container_width=True)