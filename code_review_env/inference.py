"""gives me structured stdout logs in [START] / [STEP] / [END] format.
"""
import json
import os
import sys
import time
import subprocess
import requests
from typing import Any, Dict, Optional

from openai import OpenAI

# Config

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     os.environ.get("OPENAI_API_KEY", ""))
ENV_URL      = os.environ.get("ENV_URL",      "http://localhost:7860")

TASKS = ["task_easy", "task_medium", "task_hard"]

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)


# System prompt


SYSTEM_PROMPT = """You are a senior software engineer performing code review.

For each code snippet, output a JSON object with ONLY these fields:
- "issue_type": one of [sql_injection, xss, security, bug, performance, style, no_issue]
- "severity": one of [info, warning, error, critical]
- "line_number": integer line number where the issue occurs (0 if no_issue)
- "review_comment": 2-4 sentences explaining the problem and how to fix it

Classification rules:
- sql_injection : raw string interpolation inside SQL queries
- xss           : unsanitized user input rendered into HTML/DOM
- security      : hardcoded secrets, missing auth, insecure patterns
- bug           : incorrect logic, unhandled edge cases, missing error handling
- performance   : N+1 queries, O(n^2)+ algorithms, unbounded memory growth
- style         : poor naming, missing type hints/docstrings, too many parameters
- no_issue      : code is correct and well-written

Severity rules:
- critical : exploitable vulnerability or data loss risk
- error    : will cause runtime failures for some inputs
- warning  : degrades reliability or maintainability significantly
- info     : minor style or quality improvements only

Output ONLY valid JSON with no extra text, preamble, or markdown fences."""


# Server management


_server_process: Optional[subprocess.Popen] = None


def start_server() -> bool:
    """Launch the FastAPI server in a background process."""
    global _server_process
    env_dir = os.path.dirname(os.path.abspath(__file__))
    _server_process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "server.app:app",
            "--host", "0.0.0.0",
            "--port", "7860",
            "--log-level", "warning",
        ],
        cwd=env_dir,
        env={**os.environ, "PYTHONPATH": env_dir},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            r = requests.get(f"{ENV_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def stop_server() -> None:
    global _server_process
    if _server_process:
        _server_process.terminate()
        _server_process = None



# Agent helpers


def call_llm(diff: str, file_path: str, description: str, language: str, task_id: str) -> Dict[str, Any]:
    """Ask the LLM to review one code snippet."""
    user_msg = (
        f"Task: {task_id}\n"
        f"File: {file_path} ({language})\n"
        f"Description: {description}\n\n"
        f"Code:\n{diff}\n\n"
        "Review this code and output your assessment as JSON."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {
            "issue_type":     "bug",
            "severity":       "warning",
            "line_number":    1,
            "review_comment": "Unable to parse response. Defaulting to generic bug classification.",
        }



# Episode runner


def run_episode(task_id: str) -> Dict[str, Any]:
    """Run one full episode for a given task and return results."""
    r = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id})
    r.raise_for_status()
    obs = r.json()["observation"]

    episode_results = {
        "task_id":      task_id,
        "steps":        [],
        "total_reward": 0.0,
        "final_score":  0.0,
    }

    step_num = 0
    while not obs.get("done", False):
        diff        = obs.get("diff",        "")
        file_path   = obs.get("file_path",   "unknown")
        description = obs.get("description", "")
        language    = obs.get("language",    "python")
        snippet_id  = obs.get("snippet_id",  "?")

        action = call_llm(diff, file_path, description, language, task_id)
        issue_type     = action.get("issue_type",     "bug")
        severity       = action.get("severity",       "warning")
        line_number    = int(action.get("line_number", 1))
        review_comment = action.get("review_comment", "")

        step_resp = requests.post(
            f"{ENV_URL}/step",
            json={
                "action_type":    "full_review",
                "issue_type":     issue_type,
                "severity":       severity,
                "line_number":    line_number,
                "review_comment": review_comment,
            },
        )
        step_resp.raise_for_status()
        step_data = step_resp.json()

        reward = step_data.get("reward", 0.0)
        obs    = step_data.get("observation", {})
        done   = step_data.get("done", obs.get("done", False))

        episode_results["total_reward"] += reward
        episode_results["steps"].append({
            "step":       step_num,
            "snippet_id": snippet_id,
            "action":     {"issue_type": issue_type, "severity": severity, "line_number": line_number},
            "reward":     reward,
        })

        # ── [STEP] log ────────────────────────────────────────────────────
        print(json.dumps({
            "type":       "[STEP]",
            "task_id":    task_id,
            "step":       step_num,
            "snippet_id": snippet_id,
            "action": {
                "issue_type":  issue_type,
                "severity":    severity,
                "line_number": line_number,
            },
            "reward": round(reward, 4),
            "done":   done,
        }))
        sys.stdout.flush()

        step_num += 1
        if done:
            break

    grade_resp = requests.get(f"{ENV_URL}/grade")
    grade_resp.raise_for_status()
    episode_results["final_score"] = grade_resp.json().get("score", 0.0)
    return episode_results



# Main


def main() -> None:
    print("[START]", flush=True)
    print(json.dumps({
        "type":      "[START]",
        "model":     MODEL_NAME,
        "api_base":  API_BASE_URL,
        "tasks":     TASKS,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }))
    sys.stdout.flush()

    server_running = start_server()
    if not server_running:
        print(json.dumps({"type": "[ERROR]", "message": "Failed to start environment server"}))
        sys.exit(1)

    all_results: Dict[str, Any] = {}
    try:
        for task_id in TASKS:
            print(json.dumps({"type": "[TASK_START]", "task_id": task_id}))
            sys.stdout.flush()

            episode = run_episode(task_id)
            all_results[task_id] = episode

            print(json.dumps({
                "type":         "[TASK_END]",
                "task_id":      task_id,
                "total_reward": round(episode["total_reward"], 4),
                "final_score":  round(episode["final_score"],  4),
                "steps_taken":  len(episode["steps"]),
            }))
            sys.stdout.flush()

    finally:
        stop_server()

    scores     = [v["final_score"] for v in all_results.values()]
    mean_score = sum(scores) / len(scores) if scores else 0.0

    print(json.dumps({
        "type":        "[END]",
        "model":       MODEL_NAME,
        "task_scores": {k: round(v["final_score"], 4) for k, v in all_results.items()},
        "mean_score":  round(mean_score, 4),
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }))
    print("[END]", flush=True)
    sys.stdout.flush()


if __name__ == "__main__":
    main()