import json

import pandas as pd

from mcqgenrator.utils import (
    get_table_data,
    quiz_dict_from_str,
    export_to_csv_bytes,
    export_to_docx_bytes,
    export_to_pdf_bytes,
    export_to_gift_bytes,
    export_to_quizlet_tsv_bytes,
    combine_texts,
    estimate_min_word_count,
)

MIXED_QUIZ = {
    "1": {
        "type": "mcq", "question": "What is 2+2?",
        "options": {"a": "3", "b": "4", "c": "5", "d": "6"},
        "correct": "b", "bloom_level": "Remember", "explanation": "2+2=4",
    },
    "2": {
        "type": "true_false", "question": "The sky is blue.",
        "correct": "True", "bloom_level": "Remember", "explanation": "Rayleigh scattering",
    },
    "3": {
        "type": "fill_blank", "question": "The capital of France is ____.",
        "correct": "Paris", "bloom_level": "Remember", "explanation": "Basic geography",
    },
    "4": {
        "type": "short_answer", "question": "Explain photosynthesis briefly.",
        "correct": "Plants convert light to energy.", "bloom_level": "Understand", "explanation": "Core bio concept",
    },
}

OLD_SCHEMA_QUIZ = {
    "1": {"mcq": "Old Q?", "options": {"a": "1", "b": "2"}, "correct": "a"},
    "2": {"statement": "Old TF", "correct": "False"},
}


def test_get_table_data_all_types():
    rows = get_table_data(json.dumps(MIXED_QUIZ))
    assert rows is not False
    assert len(rows) == 4
    types = {r["Type"] for r in rows}
    assert types == {"Mcq", "True False", "Fill Blank", "Short Answer"}


def test_get_table_data_strips_code_fences():
    fenced = "```json\n" + json.dumps(MIXED_QUIZ) + "\n```"
    rows = get_table_data(fenced)
    assert rows is not False
    assert len(rows) == 4


def test_get_table_data_backward_compat_old_schema():
    rows = get_table_data(json.dumps(OLD_SCHEMA_QUIZ))
    assert rows is not False
    assert rows[0]["Type"] == "Mcq"
    assert rows[0]["Question"] == "Old Q?"
    assert rows[1]["Type"] == "True False"
    assert rows[1]["Question"] == "Old TF"


def test_get_table_data_invalid_json_returns_false():
    assert get_table_data("not json at all {{{") is False


def test_quiz_dict_from_str_roundtrip():
    d = quiz_dict_from_str(json.dumps(MIXED_QUIZ))
    assert d == MIXED_QUIZ


def test_combine_texts_skips_empty():
    result = combine_texts(["hello", "", "  ", "world"])
    assert "hello" in result
    assert "world" in result
    assert "Source 1" in result and "Source 4" in result


def test_estimate_min_word_count_scales_with_count():
    assert estimate_min_word_count(3) >= 80
    assert estimate_min_word_count(20) > estimate_min_word_count(3)


def _df():
    rows = get_table_data(json.dumps(MIXED_QUIZ))
    df = pd.DataFrame(rows)
    df.index = df.index + 1
    return df


def test_export_csv_nonempty():
    assert len(export_to_csv_bytes(_df())) > 0


def test_export_docx_nonempty():
    out = export_to_docx_bytes(_df(), "review text", "Science", "Medium")
    assert out[:2] == b"PK"  # docx is a zip container


def test_export_pdf_nonempty():
    out = export_to_pdf_bytes(_df(), "review text", "Science", "Medium")
    assert out[:4] == b"%PDF"


def test_export_gift_format():
    out = export_to_gift_bytes(MIXED_QUIZ, "Science").decode()
    assert "::Q1::" in out
    assert "{TRUE}" in out or "{FALSE}" in out
    assert "{=Paris}" in out


def test_export_quizlet_tsv():
    out = export_to_quizlet_tsv_bytes(MIXED_QUIZ).decode()
    lines = out.strip().split("\n")
    assert len(lines) == 4
    for line in lines:
        assert "\t" in line
