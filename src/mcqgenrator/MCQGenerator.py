import json

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain, SequentialChain
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from mcqgenrator.logger import logger
from mcqgenrator.providers import get_llm, MissingAPIKeyError, ProviderUnavailableError

DEFAULT_PROVIDER = "Groq (Llama 3.3)"

###############################################################################
# Generation templates -- one per question type, plus a "mixed" template.
# Every template asks for the same unified per-question schema: type,
# question, (options for mcq), correct, bloom_level, explanation.
###############################################################################

_COMMON_INSTRUCTIONS = """
Write the quiz in {language}. Use a {style} question style.
Every question must include a "bloom_level" (one of: Remember, Understand,
Apply, Analyze, Evaluate, Create) reflecting the cognitive skill it tests,
and a one-sentence "explanation" of why the correct answer is correct.

Format your response EXACTLY like RESPONSE_JSON below. Return ONLY the JSON,
no extra commentary and no markdown code fences.

### RESPONSE_JSON
{response_json}
"""

_MCQ_GEN_TEMPLATE = (
    """
Text:
{text}

You are an expert MCQ maker. Given the above text, create {number} multiple
choice questions (4 options each) for {subject} students in {tone} tone.
Make sure questions are not repeated and conform strictly to the text.
"""
    + _COMMON_INSTRUCTIONS
)

_TF_GEN_TEMPLATE = (
    """
Text:
{text}

You are an expert quiz maker. Given the above text, create {number}
True/False statements for {subject} students in {tone} tone, testing
understanding of the material. Statements must not be repeated and must be
clearly True or False based strictly on the text.
"""
    + _COMMON_INSTRUCTIONS
)

_FIB_GEN_TEMPLATE = (
    """
Text:
{text}

You are an expert quiz maker. Given the above text, create {number}
fill-in-the-blank questions for {subject} students in {tone} tone. Each
question is a sentence adapted from the text with one key term or short
phrase replaced by "____". The blanked term must be inferable from context.
"""
    + _COMMON_INSTRUCTIONS
)

_SA_GEN_TEMPLATE = (
    """
Text:
{text}

You are an expert quiz maker. Given the above text, create {number}
open-ended short-answer questions for {subject} students in {tone} tone.
Each should be answerable in 1-2 sentences using only the text, with a
concise model answer provided.
"""
    + _COMMON_INSTRUCTIONS
)

_MIXED_GEN_TEMPLATE = (
    """
Text:
{text}

You are an expert quiz maker. Given the above text, create {number}
questions for {subject} students in {tone} tone, using a MIX of question
types roughly evenly split across: multiple choice (4 options), true/false,
fill-in-the-blank, and short answer. Tag each question's "type" field
accordingly ("mcq", "true_false", "fill_blank", or "short_answer"), and
only include an "options" object for "mcq" questions.
"""
    + _COMMON_INSTRUCTIONS
)

_REVIEW_TEMPLATE = """
You are an expert English grammarian and writer.

Given a quiz for {subject} students:

{quiz}

Evaluate the complexity of the questions in at most 50 words, and note
whether they suit the cognitive/analytical level of the students.

Expert Review:
"""

QUESTION_TYPES = {
    "Multiple Choice": _MCQ_GEN_TEMPLATE,
    "True / False": _TF_GEN_TEMPLATE,
    "Fill in the Blank": _FIB_GEN_TEMPLATE,
    "Short Answer": _SA_GEN_TEMPLATE,
    "Mixed": _MIXED_GEN_TEMPLATE,
}

_GEN_INPUT_VARS = ["text", "number", "subject", "tone", "response_json", "language", "style"]


def _build_chain(gen_template: str, provider: str) -> SequentialChain:
    llm = get_llm(provider)

    quiz_prompt = PromptTemplate(input_variables=_GEN_INPUT_VARS, template=gen_template)
    quiz_chain = LLMChain(llm=llm, prompt=quiz_prompt, output_key="quiz")

    review_prompt = PromptTemplate(input_variables=["subject", "quiz"], template=_REVIEW_TEMPLATE)
    review_chain = LLMChain(llm=llm, prompt=review_prompt, output_key="review")

    return SequentialChain(
        chains=[quiz_chain, review_chain],
        input_variables=_GEN_INPUT_VARS,
        output_variables=["quiz", "review"],
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
)
def _invoke(chain, inputs: dict) -> dict:
    logger.info("Invoking LLM chain (subject=%s, tone=%s)", inputs.get("subject"), inputs.get("tone"))
    return chain.invoke(inputs)


def generate_evaluate_chain(
    inputs: dict,
    question_type: str = "Multiple Choice",
    provider: str = DEFAULT_PROVIDER,
    language: str = "English",
    style: str = "Concise",
) -> dict:
    """
    Generate + evaluate a quiz. Raises MissingAPIKeyError / ProviderUnavailableError
    for configuration issues, and retries transient failures up to 3 times.
    """
    template = QUESTION_TYPES.get(question_type, _MCQ_GEN_TEMPLATE)
    chain = _build_chain(template, provider)

    full_inputs = dict(inputs)
    full_inputs["language"] = language
    full_inputs["style"] = style

    try:
        return _invoke(chain, full_inputs)
    except (MissingAPIKeyError, ProviderUnavailableError):
        raise
    except Exception as e:
        logger.exception("Quiz generation failed after retries")
        raise Exception(f"Quiz generation failed after retries: {e}")


###############################################################################
# Single-question regeneration
###############################################################################

_REGEN_TEMPLATE = """
Text:
{text}

You previously wrote this quiz question for {subject} students in {tone} tone,
but the user wants a fresh replacement covering different material from the
same text (same question type: {qtype}):

Old question: {old_question}

Write ONE new question of the same type, in {language}, as a JSON object with
the same shape as this example:
{example_json}

Return ONLY the JSON object, no commentary, no markdown fences.
"""


def regenerate_single_question(
    text: str,
    subject: str,
    tone: str,
    old_question: dict,
    language: str = "English",
    provider: str = DEFAULT_PROVIDER,
) -> dict:
    llm = get_llm(provider)
    qtype = old_question.get("type", "mcq")
    prompt = PromptTemplate(
        input_variables=["text", "subject", "tone", "qtype", "old_question", "language", "example_json"],
        template=_REGEN_TEMPLATE,
    )
    chain = LLMChain(llm=llm, prompt=prompt, output_key="question")

    result = _invoke(
        chain,
        {
            "text": text,
            "subject": subject,
            "tone": tone,
            "qtype": qtype,
            "old_question": json.dumps(old_question),
            "language": language,
            "example_json": json.dumps(old_question),
        },
    )
    raw = result["question"].strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


###############################################################################
# Subject auto-detection
###############################################################################

_SUBJECT_TEMPLATE = """
Text:
{text}

In 2-4 words, name the academic subject or topic this text is about
(e.g. "Cell Biology", "World War II", "Python Programming"). Respond with
ONLY those words, nothing else.
"""


def auto_detect_subject(text: str, provider: str = DEFAULT_PROVIDER) -> str:
    llm = get_llm(provider)
    prompt = PromptTemplate(input_variables=["text"], template=_SUBJECT_TEMPLATE)
    chain = LLMChain(llm=llm, prompt=prompt, output_key="subject")
    result = _invoke(chain, {"text": text[:4000]})
    return result["subject"].strip().strip('"')
