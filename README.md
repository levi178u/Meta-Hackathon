# Meta Hackathon
# 🔍 Code Review OpenEnv

> A production-grade RL environment where AI agents learn to review pull request diffs — classifying bugs, assigning severity, pinpointing line numbers, and writing actionable comments — just like senior engineers do every day.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compliant-green)](https://github.com/meta-pytorch/OpenEnv)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED)](https://docker.com)

---

## 🌍 Why Code Review?

Code review is a **high-frequency, high-stakes engineering task**:
- Engineers spend 10–20% of their time reviewing PRs
- Missed security bugs (SQL injection, XSS, hardcoded secrets) cause breaches
- Inconsistent reviews slow down teams and introduce regressions

An agent trained here could **directly automate or assist** real PR review workflows — catching security issues, flagging performance anti-patterns, and drafting review comments at scale.

---

## 🏗️ Architecture

```
code-review-env/
├── server/
│   ├── app.py           # FastAPI server (reset/step/state/grade endpoints)
│   └── environment.py   # Core logic + 12-snippet dataset + graders
├── models.py            # Pydantic models: Action, Observation, Reward, State
├── client.py            # HTTP client wrapper
├── inference.py         # Baseline inference script (OpenAI client)
├── app.py               # HF Spaces entrypoint
├── openenv.yaml         # OpenEnv manifest
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── README.md
```

---

## 🎯 Tasks

### Task 1 — Issue Classification (`task_easy`)
**Difficulty:** Easy | **Max Steps:** 20 | **Queue:** 5 snippets

Classify each code snippet into the correct issue type:

| Issue Type | Example |
|------------|---------|
| `sql_injection` | f-string interpolation inside SQL query |
| `xss` | `innerHTML = userInput` |
| `security` | Hardcoded passwords/secrets |
| `bug` | Division by zero, missing error handling |
| `performance` | N+1 queries, O(n²) algorithms |
| `style` | Single-letter names, too many parameters |
| `no_issue` | Well-written, correct code |

**Grader:** Classification accuracy — exact match = 1.0, same security family = 0.5, wrong = 0.0

**Expected Baseline Score:** ~0.80 (LLM is strong at recognising common patterns)

---

### Task 2 — Severity & Localization (`task_medium`)
**Difficulty:** Medium | **Max Steps:** 30 | **Queue:** 8 snippets

Classify issue type **+** assign severity **+** identify the exact line number:

| Severity | Meaning |
|----------|---------|
| `critical` | Exploitable vulnerability or data loss |
| `error` | Causes runtime failures for some inputs |
| `warning` | Degrades reliability or maintainability |
| `info` | Minor style improvements only |

**Grader:** 40% issue type + 35% severity + 25% line (exact = 1.0, within ±2 = 0.5)

**Expected Baseline Score:** ~0.65

---

### Task 3 — Full Code Review (`task_hard`)
**Difficulty:** Hard | **Max Steps:** 50 | **Queue:** 10 snippets

Classify, assign severity, pinpoint line **+** write a review comment:
- Comment must explain *what* the problem is
- Comment must suggest *how* to fix it
- Scored on: hint keyword matching, relevant terminology, appropriate length

**Grader:** 30% issue type + 25% severity + 20% line + 25% comment quality

**Expected Baseline Score:** ~0.55

---

## 📐 Observation Space

```python
class CodeReviewObservation(BaseModel):
    snippet_id:        str    # Unique snippet identifier
    language:          str    # python | javascript | etc.
    file_path:         str    # Simulated PR file path
    diff:              str    # The actual code to review
    description:       str    # What the code does
    queue_size:        int    # Remaining snippets in queue
    current_step:      int    # Steps taken this episode
    task_id:           str    # Active task
    snippets_reviewed: int    # Snippets handled so far
    score_so_far:      float  # Cumulative reward [0.0–1.0]
    done:              bool   # Episode ended?
    reward:            float  # Last step reward
    metadata:          dict   # reward_breakdown included after each step
```

## 🎮 Action Space

```python
class CodeReviewAction(BaseModel):
    action_type:    str  # classify | classify_and_localize | full_review
    issue_type:     str  # sql_injection | xss | security | bug | performance | style | no_issue
    severity:       str  # info | warning | error | critical
    line_number:    int  # line where the issue occurs (0 for no_issue)
    review_comment: str  # written review comment (required for task_hard)
    metadata:       dict
```

---

## 🏆 Reward Function

Rewards are **partial and per-step** — the agent receives signal on every action, not just at episode end.

| Component | task_easy | task_medium | task_hard |
|-----------|:---------:|:-----------:|:---------:|
| Issue classification | 100% | 40% | 30% |
| Severity assignment | — | 35% | 25% |
| Line localization | — | 25% | 20% |
| Comment quality | — | — | 25% |

**Partial credit rules:**
- Same issue family (e.g. `security` vs `sql_injection`) → 0.5
- Severity off by one level → 0.5
- Line number within ±2 of true line → 0.5
- Response comment with relevant keywords → proportional score

**Penalties:**
- Invalid `issue_type` string → −0.10
- Invalid `severity` string → −0.05

---

## 🚀 Setup & Usage

### Local (Python)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the environment server
uvicorn server.app:app --host 0.0.0.0 --port 7860

# 3. Use the client
python -c "
from client import CodeReviewClient
env = CodeReviewClient()
obs = env.reset('task_easy')
print('File:', obs['file_path'])
print('Diff:', obs['diff'][:80])
result = env.step(issue_type='bug', severity='error', line_number=5)
print('Reward:', result['reward'])
"
```

### Docker

```bash
docker build -t code-review-env .
docker run -p 7860:7860 code-review-env

# Test
curl http://localhost:7860/health
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task_easy"}'
```

### Inference Script

```bash
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="sk-..."

python inference.py
```

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/reset`  | Start new episode |
| `POST` | `/step`   | Submit review action |
| `GET`  | `/state`  | Get full environment state |
| `GET`  | `/grade`  | Get final episode score |
| `GET`  | `/tasks`  | List available tasks |

### Full Episode Example

```python
import requests

BASE = "http://localhost:7860"

obs = requests.post(f"{BASE}/reset", json={"task_id": "task_hard"}).json()["observation"]

while not obs["done"]:
    result = requests.post(f"{BASE}/step", json={
        "action_type":    "full_review",
        "issue_type":     "sql_injection",
        "severity":       "critical",
        "line_number":    2,
        "review_comment": (
            "This code is vulnerable to SQL injection. "
            "Use parameterized queries instead of string interpolation."
        ),
    }).json()
    obs = result["observation"]
    print(f"Reward: {result['reward']:.3f} | Breakdown: {result['info'].get('reward_breakdown', {}).get('total')}")

score = requests.get(f"{BASE}/grade").json()["score"]
print(f"Final score: {score:.3f}")
```

---

## 📈 Baseline Scores

Scores from `inference.py` using `gpt-4o-mini` on 1 episode per task:

| Task | Score | Notes |
|------|-------|-------|
| task_easy   | ~0.80 | LLM recognises common bug patterns well |
| task_medium | ~0.65 | Line localization adds meaningful difficulty |
| task_hard   | ~0.55 | Comment generation is noisy |
| **Mean**    | **~0.67** | |

Random baseline: ~0.20 mean (7-class classification chance + random priority/line).

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 🤗 HF Spaces Deployment

```yaml
---
title: Code Review OpenEnv
emoji: 🔍
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
tags:
  - openenv
---
```

The `app.py` entrypoint serves on port 7860 by default for HF Spaces.

---
## THANK YOU
