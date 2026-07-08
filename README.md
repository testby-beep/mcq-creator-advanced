# AnswerKey Studio

An LLM-powered quiz generator: turn a PDF, text file, pasted passage, or
YouTube video into a graded, exportable, shareable quiz.

## Features

**Question generation**
- 5 question types: Multiple Choice, True/False, Fill-in-the-Blank, Short
  Answer, and Mixed (a blend of all four in one quiz)
- Bloom's-taxonomy tag + one-line explanation on every question
- 9 output languages, 4 question styles (Concise / Scenario-based /
  Exam-style / Conversational)
- Source material: upload multiple PDF/TXT files (combined into one quiz),
  paste raw text, or fetch a YouTube video's transcript
- Auto-detect subject from the source text (🔍 button)
- Regenerate a single question in place, without redoing the whole quiz

**Taking a quiz**
- Interactive self-check in-app: MCQ/True-False/Fill-in-Blank are
  auto-graded; Short Answer shows the model answer to compare against
- Optional timed mode (records seconds-to-answer)
- Scantron-style bubble next to each question that fills in once answered
- Per-question explanations revealed after checking

**Sharing & competing**
- Generate a 6-character share code for any quiz; anyone with the code
  (running the same app instance) can load it and take it
- Local leaderboard per share code (name, score, time)

**Export**
- CSV, Word (.docx), PDF, raw JSON
- GIFT format (Moodle-compatible import)
- Quizlet-compatible tab-separated term/definition file

**Reliability & cost control**
- Automatic retry (3x, exponential backoff) on transient LLM failures
- Response caching — identical (text, subject, tone, type, language,
  style, provider) requests are served from a local cache instead of
  re-billing the API
- Per-session rate limiting (default: 5 generations/minute)
- Multi-provider: Groq, OpenAI, or Anthropic, selectable per generation —
  whichever packages/keys you have configured

**Analytics**
- History tab: every quiz you've generated, with token/cost trend charts
- "Hardest questions" analytics: aggregated across every self-check
  attempt, any quiz, so you can see what people consistently get wrong

**Deployment**
- `Dockerfile` + `docker-compose.yml` for containerized deployment
- GitHub Actions CI (`.github/workflows/ci.yml`) running a real pytest
  suite (21 tests) on every push/PR

## What's deliberately NOT included

These need infrastructure or credentials this project doesn't assume you
have — ask if you want any of them built out:

- User accounts / login / per-user data isolation (currently single-user,
  local-first; the DB has no auth layer)
- Postgres (SQLite is used for simplicity; swap `history.py` / `cache.py`
  / `social.py` connection logic if you need concurrent multi-user writes)
- Google Classroom / Kahoot / Google Forms integrations (need OAuth app
  registration) — GIFT and Quizlet export cover the "get this into another
  tool" need without needing API credentials
- Slack/email delivery (needs SMTP/Slack tokens)
- Background job queue (Celery/Redis) — unnecessary for a Streamlit app
  at this scale

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in at least one provider's API key
streamlit run app.py
```

`.env` supports any/all of:
```
GROQ_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```
Only providers with both the package installed (already in
requirements.txt) and a key set will appear in the provider dropdown.

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

## Docker

```bash
cp .env.example .env   # fill in your key(s) first
docker compose up --build
```
App will be at http://localhost:8501. `data/` and `logs/` are mounted as
volumes so history/cache/leaderboard survive container restarts.

## Project structure

```
app.py                          # Streamlit UI
Response_*.json                 # JSON schema template per question type
src/mcqgenrator/
    utils.py                    # file reading, JSON parsing, all exports
    MCQGenerator.py              # LangChain chains: generation, regen, auto-detect subject
    providers.py                 # multi-LLM-provider factory (Groq/OpenAI/Anthropic)
    cache.py                     # response cache (sqlite)
    ratelimit.py                 # per-session rate limiter
    social.py                    # share codes, leaderboard, question-attempt analytics (sqlite)
    youtube_source.py            # YouTube transcript fetching
    history.py                   # generation history (sqlite)
    theme.py                     # visual design system (CSS + HTML helpers)
    logger.py                    # rotating file logger
tests/                          # pytest suite (21 tests, no API keys required)
.github/workflows/ci.yml        # CI: compile check + pytest on push/PR
Dockerfile / docker-compose.yml / .dockerignore
data/                            # created automatically: history.db, cache.db, social.db
logs/                            # created automatically: app.log
```

## Notes

- The Mixed question type asks the LLM to tag each question's own `type`
  field, so downstream code (table rendering, self-check grading, export)
  branches per-question rather than per-quiz.
- Regenerating a single question re-uses the *original* source text stored
  in session state at generation time — if you reload a quiz from History
  or a share code, that source text isn't available (only the finished
  quiz was saved), so regeneration is disabled for those.
- Short Answer questions aren't auto-graded (open-ended text can't be
  reliably matched against a model answer) — they show the model answer
  for self-comparison instead, and don't count toward the numeric score.
