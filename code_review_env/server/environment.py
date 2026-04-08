"""
Code Review Environment – Core Logic
=====================================
Simulates a senior engineer reviewing pull request diffs.
Tasks:
  task_easy   – classify the issue type in a code snippet
  task_medium – classify + assign severity + identify line number
  task_hard   – full review: classify, severity, line, write comment
"""

import uuid
import random
from typing import Any, Dict, List, Tuple, Optional

# ---------------------------------------------------------------------------
# Synthetic code review dataset
# ---------------------------------------------------------------------------

CODE_DATASET: List[Dict[str, Any]] = [

    # ── Security Issues ──────────────────────────────────────────────────────
    {
        "snippet_id": "s001",
        "language": "python",
        "file_path": "auth/login.py",
        "diff": (
            "def login(request):\n"
            "    user = db.query(f\"SELECT * FROM users WHERE name='{request.username}'\")\n"
            "    if user and user.password == request.password:\n"
            "        return grant_access(user)\n"
            "    return deny()\n"
        ),
        "description": "User login handler",
        "true_issue_type": "sql_injection",
        "true_severity": "critical",
        "true_line": 2,
        "issue_explanation": "Raw string interpolation in SQL query allows SQL injection",
        "review_hints": ["parameterized", "prepared statement", "sql injection", "escape"],
        "keywords": ["SQL", "injection", "f-string", "query", "parameterized"],
    },
    {
        "snippet_id": "s002",
        "language": "javascript",
        "file_path": "frontend/comment.js",
        "diff": (
            "function renderComment(userInput) {\n"
            "    document.getElementById('output').innerHTML = userInput;\n"
            "}\n"
        ),
        "description": "Comment renderer component",
        "true_issue_type": "xss",
        "true_severity": "critical",
        "true_line": 2,
        "issue_explanation": "Directly setting innerHTML with user input enables XSS attacks",
        "review_hints": ["innerHTML", "textContent", "sanitize", "XSS", "DOMPurify"],
        "keywords": ["innerHTML", "XSS", "sanitize", "user input"],
    },
    {
        "snippet_id": "s003",
        "language": "python",
        "file_path": "config/settings.py",
        "diff": (
            "DATABASE_URL = 'postgresql://admin:SuperSecret123@prod-db:5432/app'\n"
            "SECRET_KEY = 'hardcoded-jwt-secret-do-not-share'\n"
            "DEBUG = True\n"
        ),
        "description": "Application settings file",
        "true_issue_type": "security",
        "true_severity": "critical",
        "true_line": 1,
        "issue_explanation": "Hardcoded credentials and secrets in source code",
        "review_hints": ["environment variable", "secrets manager", "dotenv", "vault", "never hardcode"],
        "keywords": ["hardcoded", "credentials", "secret", "environment variable"],
    },

    # ── Bugs ─────────────────────────────────────────────────────────────────
    {
        "snippet_id": "s004",
        "language": "python",
        "file_path": "utils/math_helpers.py",
        "diff": (
            "def average(numbers):\n"
            "    total = 0\n"
            "    for n in numbers:\n"
            "        total += n\n"
            "    return total / len(numbers)\n"
        ),
        "description": "Average calculation utility",
        "true_issue_type": "bug",
        "true_severity": "error",
        "true_line": 5,
        "issue_explanation": "ZeroDivisionError when numbers list is empty",
        "review_hints": ["empty list", "ZeroDivisionError", "guard clause", "len check"],
        "keywords": ["division", "empty", "ZeroDivisionError", "guard"],
    },
    {
        "snippet_id": "s005",
        "language": "python",
        "file_path": "api/cache.py",
        "diff": (
            "cache = {}\n"
            "\n"
            "def get_cached(key):\n"
            "    if key in cache:\n"
            "        return cache[key]\n"
            "    result = expensive_query(key)\n"
            "    cache[key] = result\n"
            "    return result\n"
        ),
        "description": "In-memory cache for API responses",
        "true_issue_type": "bug",
        "true_severity": "warning",
        "true_line": 1,
        "issue_explanation": "Module-level mutable dict is shared across all requests — not thread-safe and grows unbounded",
        "review_hints": ["thread-safe", "TTL", "LRU", "unbounded memory", "race condition"],
        "keywords": ["global", "mutable", "thread-safe", "cache", "unbounded"],
    },
    {
        "snippet_id": "s006",
        "language": "javascript",
        "file_path": "api/fetchUser.js",
        "diff": (
            "async function fetchUser(id) {\n"
            "    const response = await fetch(`/api/users/${id}`);\n"
            "    const data = await response.json();\n"
            "    return data.user;\n"
            "}\n"
        ),
        "description": "User fetch function",
        "true_issue_type": "bug",
        "true_severity": "error",
        "true_line": 2,
        "issue_explanation": "No error handling for failed HTTP requests or non-OK status codes",
        "review_hints": ["response.ok", "try/catch", "error handling", "status code", "throw"],
        "keywords": ["error handling", "response.ok", "status", "try catch"],
    },

    # ── Performance ───────────────────────────────────────────────────────────
    {
        "snippet_id": "s007",
        "language": "python",
        "file_path": "db/reports.py",
        "diff": (
            "def get_user_orders(user_ids):\n"
            "    results = []\n"
            "    for uid in user_ids:\n"
            "        orders = db.query('SELECT * FROM orders WHERE user_id = ?', uid)\n"
            "        results.extend(orders)\n"
            "    return results\n"
        ),
        "description": "Fetch orders for a list of users",
        "true_issue_type": "performance",
        "true_severity": "error",
        "true_line": 3,
        "issue_explanation": "N+1 query problem — one DB query per user instead of a single batch query",
        "review_hints": ["N+1", "batch query", "IN clause", "bulk fetch", "single query"],
        "keywords": ["N+1", "loop query", "batch", "IN clause", "performance"],
    },
    {
        "snippet_id": "s008",
        "language": "python",
        "file_path": "search/indexer.py",
        "diff": (
            "def find_duplicates(items):\n"
            "    duplicates = []\n"
            "    for i in range(len(items)):\n"
            "        for j in range(len(items)):\n"
            "            if i != j and items[i] == items[j]:\n"
            "                if items[i] not in duplicates:\n"
            "                    duplicates.append(items[i])\n"
            "    return duplicates\n"
        ),
        "description": "Find duplicate items in a list",
        "true_issue_type": "performance",
        "true_severity": "warning",
        "true_line": 3,
        "issue_explanation": "O(n^3) complexity — nested loops plus linear search. Use a set for O(n).",
        "review_hints": ["O(n)", "set", "Counter", "seen", "nested loop", "complexity"],
        "keywords": ["O(n^2)", "nested loop", "set", "complexity", "efficient"],
    },

    # ── Style / Maintainability ───────────────────────────────────────────────
    {
        "snippet_id": "s009",
        "language": "python",
        "file_path": "utils/processor.py",
        "diff": (
            "def p(x, y, z, a, b):\n"
            "    r = x*y + z\n"
            "    if r > a:\n"
            "        return r - b\n"
            "    return r\n"
        ),
        "description": "Data processing utility function",
        "true_issue_type": "style",
        "true_severity": "warning",
        "true_line": 1,
        "issue_explanation": "Single-letter names are unreadable — no docstring, no type hints",
        "review_hints": ["naming", "descriptive", "docstring", "type hints", "readability"],
        "keywords": ["naming", "readability", "docstring", "type hints"],
    },
    {
        "snippet_id": "s010",
        "language": "python",
        "file_path": "services/payment.py",
        "diff": (
            "def process_payment(amount, card, user, retry=True, log=True, notify=True,\n"
            "                    currency='USD', tax=0.0, discount=0.0, ref=None,\n"
            "                    dry_run=False, urgent=False):\n"
            "    pass\n"
        ),
        "description": "Payment processing function",
        "true_issue_type": "style",
        "true_severity": "info",
        "true_line": 1,
        "issue_explanation": "Too many parameters (12) — use a dataclass or config object",
        "review_hints": ["dataclass", "config object", "too many parameters", "single responsibility"],
        "keywords": ["parameters", "dataclass", "refactor", "single responsibility"],
    },

    # ── No Issue ──────────────────────────────────────────────────────────────
    {
        "snippet_id": "s011",
        "language": "python",
        "file_path": "utils/validators.py",
        "diff": (
            "import re\n"
            "\n"
            "EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$')\n"
            "\n"
            "def is_valid_email(email: str) -> bool:\n"
            "    \"\"\"Return True if email matches standard format.\"\"\"\n"
            "    return bool(EMAIL_REGEX.match(email))\n"
        ),
        "description": "Email validation utility",
        "true_issue_type": "no_issue",
        "true_severity": "info",
        "true_line": 0,
        "issue_explanation": "Code is correct — compiled regex, type hints, docstring present",
        "review_hints": ["looks good", "approve", "no issues", "LGTM"],
        "keywords": ["correct", "type hint", "docstring", "compiled"],
    },
    {
        "snippet_id": "s012",
        "language": "python",
        "file_path": "models/user.py",
        "diff": (
            "from dataclasses import dataclass, field\n"
            "from typing import List\n"
            "\n"
            "@dataclass\n"
            "class User:\n"
            "    \"\"\"Represents an application user.\"\"\"\n"
            "    id: int\n"
            "    name: str\n"
            "    email: str\n"
            "    roles: List[str] = field(default_factory=list)\n"
        ),
        "description": "User data model",
        "true_issue_type": "no_issue",
        "true_severity": "info",
        "true_line": 0,
        "issue_explanation": "Well-structured dataclass with correct use of default_factory",
        "review_hints": ["looks good", "approve", "LGTM", "well structured"],
        "keywords": ["dataclass", "type hints", "default_factory", "correct"],
    },
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ISSUE_TYPES = {
    "sql_injection", "xss", "security",
    "bug", "performance", "style", "no_issue",
}

VALID_SEVERITIES = {"info", "warning", "error", "critical"}

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}

ISSUE_FAMILIES = {
    "sql_injection": ["sql_injection", "security"],
    "xss":           ["xss", "security"],
    "security":      ["security", "sql_injection", "xss"],
    "bug":           ["bug"],
    "performance":   ["performance"],
    "style":         ["style"],
    "no_issue":      ["no_issue"],
}

MAX_STEPS  = {"task_easy": 20, "task_medium": 30, "task_hard": 50}
QUEUE_SIZE = {"task_easy": 5,  "task_medium": 8,  "task_hard": 10}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_issue_type(predicted: str, true: str) -> Tuple[float, str]:
    if predicted == true:
        return 1.0, f"Exact match: {true}"
    family = ISSUE_FAMILIES.get(true, [true])
    if predicted in family:
        return 0.5, f"Same family as {true}"
    return 0.0, f"Wrong: predicted {predicted}, true {true}"


def _score_severity(predicted: str, true: str) -> Tuple[float, str]:
    if predicted == true:
        return 1.0, f"Exact: {true}"
    pred_r = SEVERITY_ORDER.get(predicted, -1)
    true_r = SEVERITY_ORDER.get(true, -1)
    if abs(pred_r - true_r) == 1:
        return 0.5, f"Off by one (predicted {predicted}, true {true})"
    return 0.0, f"Wrong severity (predicted {predicted}, true {true})"


def _score_line(predicted: int, true: int) -> Tuple[float, str]:
    if true == 0:
        return 1.0, "No issue — line irrelevant"
    if predicted == true:
        return 1.0, f"Exact line: {true}"
    if abs(predicted - true) <= 2:
        return 0.5, f"Within +-2 lines (predicted {predicted}, true {true})"
    return 0.0, f"Wrong line (predicted {predicted}, true {true})"


def _score_comment(comment: str, snippet: Dict[str, Any]) -> Tuple[float, str]:
    if not comment or len(comment.strip()) < 10:
        return 0.0, "Empty or too short"
    comment_lower = comment.lower()
    hints    = snippet.get("review_hints", [])
    keywords = snippet.get("keywords", [])
    matched_hints    = sum(1 for h in hints    if h.lower() in comment_lower)
    matched_keywords = sum(1 for k in keywords if k.lower() in comment_lower)
    hint_score    = (matched_hints / max(len(hints), 1)) if hints else 0.5
    length_bonus  = min(len(comment) / 150, 0.2)
    keyword_bonus = matched_keywords * 0.03
    score = min(hint_score * 0.7 + length_bonus + keyword_bonus, 1.0)
    return round(score, 3), (
        f"Comment quality: {matched_hints}/{len(hints)} hints, "
        f"{matched_keywords} keywords, length {len(comment)}"
    )


# ---------------------------------------------------------------------------
# Graders (one per task)
# ---------------------------------------------------------------------------

def grade_easy(log: List[Dict]) -> float:
    if not log:
        return 0.0
    total = sum(
        _score_issue_type(e["predicted_issue_type"], e["true_issue_type"])[0]
        for e in log
    )
    return round(total / len(log), 4)


def grade_medium(log: List[Dict]) -> float:
    if not log:
        return 0.0
    total = 0.0
    for e in log:
        issue, _ = _score_issue_type(e["predicted_issue_type"], e["true_issue_type"])
        sev,   _ = _score_severity(e["predicted_severity"], e["true_severity"])
        line,  _ = _score_line(e.get("predicted_line", 0), e["true_line"])
        total += 0.40 * issue + 0.35 * sev + 0.25 * line
    return round(total / len(log), 4)


def grade_hard(log: List[Dict]) -> float:
    if not log:
        return 0.0
    total = 0.0
    for e in log:
        issue,   _ = _score_issue_type(e["predicted_issue_type"], e["true_issue_type"])
        sev,     _ = _score_severity(e["predicted_severity"], e["true_severity"])
        line,    _ = _score_line(e.get("predicted_line", 0), e["true_line"])
        comment, _ = _score_comment(e.get("review_comment", ""), e["snippet"])
        total += 0.30 * issue + 0.25 * sev + 0.20 * line + 0.25 * comment
    return round(total / len(log), 4)


GRADERS = {
    "task_easy":   grade_easy,
    "task_medium": grade_medium,
    "task_hard":   grade_hard,
}


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------

class CodeReviewEnvironment:

    def __init__(self) -> None:
        self._episode_id: str = ""
        self._task_id: str = "task_easy"
        self._queue: List[Dict[str, Any]] = []
        self._queue_index: int = 0
        self._step_count: int = 0
        self._max_steps: int = MAX_STEPS["task_easy"]
        self._action_log: List[Dict[str, Any]] = []
        self._cumulative_score: float = 0.0
        self._done: bool = False

    def reset(self, task_id: str = "task_easy") -> Dict[str, Any]:
        self._episode_id   = str(uuid.uuid4())[:8]
        self._task_id      = task_id if task_id in MAX_STEPS else "task_easy"
        self._max_steps    = MAX_STEPS[self._task_id]
        self._step_count   = 0
        self._action_log   = []
        self._cumulative_score = 0.0
        self._done         = False
        n = QUEUE_SIZE[self._task_id]
        self._queue        = random.sample(CODE_DATASET, min(n, len(CODE_DATASET)))
        self._queue_index  = 0
        return self._make_observation(reward=0.0)

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if self._done:
            return self._make_observation(reward=0.0)

        issue_type     = action.get("issue_type",     "bug")
        severity       = action.get("severity",       "warning")
        line_number    = int(action.get("line_number", 1))
        review_comment = action.get("review_comment", "")

        penalty = 0.0
        if issue_type not in VALID_ISSUE_TYPES:
            issue_type = "bug"
            penalty += 0.1
        if severity not in VALID_SEVERITIES:
            severity = "warning"
            penalty += 0.05

        snippet = self._queue[self._queue_index]
        reward, breakdown = self._compute_reward(
            snippet, issue_type, severity, line_number, review_comment, penalty
        )
        self._cumulative_score += reward

        self._action_log.append({
            "snippet_id":           snippet["snippet_id"],
            "true_issue_type":      snippet["true_issue_type"],
            "true_severity":        snippet["true_severity"],
            "true_line":            snippet["true_line"],
            "predicted_issue_type": issue_type,
            "predicted_severity":   severity,
            "predicted_line":       line_number,
            "review_comment":       review_comment,
            "snippet":              snippet,
            "reward":               reward,
        })

        self._step_count  += 1
        self._queue_index += 1

        if self._queue_index >= len(self._queue) or self._step_count >= self._max_steps:
            self._done = True

        obs = self._make_observation(reward=reward)
        obs["metadata"]["reward_breakdown"] = breakdown
        return obs

    def state(self) -> Dict[str, Any]:
        return {
            "episode_id":        self._episode_id,
            "task_id":           self._task_id,
            "current_step":      self._step_count,
            "max_steps":         self._max_steps,
            "snippets_reviewed": self._queue_index,
            "total_snippets":    len(self._queue),
            "cumulative_score":  round(self._cumulative_score, 4),
            "done":              self._done,
        }

    def grade(self) -> float:
        return GRADERS[self._task_id](self._action_log)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _compute_reward(
        self,
        snippet: Dict[str, Any],
        issue_type: str,
        severity: str,
        line_number: int,
        review_comment: str,
        penalty: float,
    ) -> Tuple[float, Dict[str, Any]]:
        issue_s,   issue_r   = _score_issue_type(issue_type,   snippet["true_issue_type"])
        sev_s,     sev_r     = _score_severity(severity,       snippet["true_severity"])
        line_s,    line_r    = _score_line(line_number,         snippet["true_line"])
        comment_s, comment_r = 0.0, "N/A"

        if self._task_id == "task_easy":
            raw = issue_s
        elif self._task_id == "task_medium":
            raw = 0.40 * issue_s + 0.35 * sev_s + 0.25 * line_s
        else:
            comment_s, comment_r = _score_comment(review_comment, snippet)
            raw = 0.30 * issue_s + 0.25 * sev_s + 0.20 * line_s + 0.25 * comment_s

        total = max(0.0, round(raw - penalty, 4))
        return total, {
            "issue_type":         issue_s, "issue_rationale":    issue_r,
            "severity":           sev_s,   "severity_rationale": sev_r,
            "line":               line_s,  "line_rationale":     line_r,
            "comment":            comment_s,"comment_rationale": comment_r,
            "penalty":            penalty,  "total":             total,
        }

    def _make_observation(self, reward: float) -> Dict[str, Any]:
        if self._done or self._queue_index >= len(self._queue):
            return {
                "snippet_id":        "",
                "language":          "",
                "file_path":         "[Queue Empty]",
                "diff":              "",
                "description":       "",
                "queue_size":        0,
                "current_step":      self._step_count,
                "task_id":           self._task_id,
                "snippets_reviewed": self._queue_index,
                "score_so_far":      round(self._cumulative_score, 4),
                "done":              True,
                "reward":            reward,
                "metadata":          {"episode_id": self._episode_id},
            }
        s = self._queue[self._queue_index]
        return {
            "snippet_id":        s["snippet_id"],
            "language":          s["language"],
            "file_path":         s["file_path"],
            "diff":              s["diff"],
            "description":       s["description"],
            "queue_size":        len(self._queue) - self._queue_index,
            "current_step":      self._step_count,
            "task_id":           self._task_id,
            "snippets_reviewed": self._queue_index,
            "score_so_far":      round(self._cumulative_score, 4),
            "done":              False,
            "reward":            reward,
            "metadata":          {"episode_id": self._episode_id},
        }