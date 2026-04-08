# OpenEnv RL Hackathon: Code Review Environment
![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue.svg)

## Environment Overview & Motivation
Code reviews are a highly impactful, real-world task performed by human developers millions of times every day. The `code_review_env` models this task explicitly. The goal of this environment is to provide a unified RL challenge where an agent receives partial, contextual PR information (diff snippets, file paths, author experience levels) and must intelligently analyze the code to pinpoint bugs, vulnerabilities, style issues, or confirm no issues are present. 

Unlike toy environments or simple games, finding code vulnerabilities and reasoning over logic requires actual "world knowledge" of programming nuances, making it directly relevant to training state-of-the-art LLMs for developer productivity tasks.

## Tasks and Expected Difficulty 
This environment executes **one episode containing exactly three consecutive steps**, each corresponding to a different coding scenario reflecting varying real-world difficulty:
1. **Easy**: A simple isolated logic error (e.g. arithmetic mistake in an isolated Python function). The agent simply needs to recognize the logic flow and point it out.
2. **Medium**: A highly critical security vulnerability (RCE using `os.system`) embedded inside a slightly longer standard flask endpoint format.
3. **Hard**: A complex logic or race-conditions bug masked in a try-except ignoring block. Requires understanding the implicit context that `stripe` might fail, but deducting balance beforehand causes silent data desyncs in `update_db(user)`.

## Definitions of Spaces

### Observation Space
A rich Pydantic model (`CodeReviewObservation`) presenting the context dynamically.
- `diff_snippet` (str): The code snippet being reviewed, properly line-numbered.
- `language` (str): The language of the file (e.g. "python").
- `file_path` (str): Path of the file under review.
- `pr_description` (str): Natural language context for what the original author intended.
- `author_experience` (str): Contextual hint about code reliability ("junior", "mid", "senior").

*Note: Following RL best-practices, the agent can additionally pull OpenEnv standard `.state()` to observe current episode scores, the difficulty string ("easy", "medium", "hard"), and tasks remaining.*

### Action Space
A structured JSON representation matching `CodeReviewAction`.
- `issue_type`: Literal string matching the issue category (`bug`, `security`, `style`, `performance`, `no-issue`).
- `severity`: Literal string matching severity tiers (`info`, `warning`, `error`, `critical`, `none`).
- `line_number`: Integer representing the targeted line (-1 if no issue).
- `review_comment`: A concise, actionable instruction detailing the issue and fix.

### Reward Function
The environment evaluates actions dynamically using a deterministic grader giving credit up to **1.0 points** per task:
- Correct issue tracking (+0.3) with partial credit for related families (+0.15).
- Precise severity matching (+0.2) or slightly off-by-one tolerance (+0.1).
- Pinned line numbers (+0.3) or proximity tracking up to ±2 lines (+0.15).
- NLP analysis ensuring comment is actionable / meets baseline lengths (+0.2).

The environment naturally penalizes loops or bad formatting by emitting zero reward if structure is completely broken and falls back via pydantic validation exceptions. 

## Setup and Usage Instructions

1. **Install OpenEnv Core Requirements**
```bash
pip install openenv-core
```
2. **Run Server locally** (Requires Uvicorn/FastAPI)
```bash
python server/app.py --port 8000
```
3. **Launch Docker (preferred environment constraint)**
```bash
docker build -t code_review_env:latest -f server/Dockerfile .
docker run -p 8000:8000 code_review_env:latest
```

## Baseline Performance Scores
Running `python inference.py` locally hooks up the standard `gpt-4o-mini` evaluation client.
Because the environment natively requires a standardized structure:
```bash
python inference.py
```
Outputs standard evaluation logs directly matching OpenEnv Challenge formats.
**Current baseline expectation for GPT-4o-mini:** `score >= 0.850`.
For non-instruct tuned models, zero-shot prompts struggle to pinpoint line numbers properly causing consistent point drops leading to early baseline failure `score < 0.500`.

---
This environment fully complies with Hugging Face Space constraints (2vCPU, 8GB RAM). 
