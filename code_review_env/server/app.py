"""
FastAPI server for the Code Review OpenEnv environment.
Exposes /reset, /step, /state, /grade, /health, /tasks endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.environment import CodeReviewEnvironment

app = FastAPI(
    title="Code Review OpenEnv",
    description=(
        "A real-world code review RL environment. "
        "The agent learns to classify bugs, assign severity, "
        "pinpoint line numbers, and write actionable review comments."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = CodeReviewEnvironment()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_id: str = "task_easy"


class StepRequest(BaseModel):
    action_type:    str = "classify"
    issue_type:     str = "bug"
    severity:       str = "warning"
    line_number:    int = 1
    review_comment: str = ""
    metadata: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "Welcome to the Code Review OpenEnv API! Visit /docs for API documentation."}
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "environment": "code-review-env"}


@app.post("/reset")
def reset(request: ResetRequest = ResetRequest()) -> Dict[str, Any]:
    """
    Start a new episode.

    Parameters
    ----------
    task_id : str
        One of: task_easy | task_medium | task_hard
    """
    obs = env.reset(task_id=request.task_id)
    return {
        "observation": obs,
        "reward": 0.0,
        "done": False,
        "info": {"task_id": request.task_id},
    }


@app.post("/step")
def step(request: StepRequest) -> Dict[str, Any]:
    """
    Submit a review action for the current code snippet.

    Returns observation, reward, done, info.
    """
    action = {
        "action_type":    request.action_type,
        "issue_type":     request.issue_type,
        "severity":       request.severity,
        "line_number":    request.line_number,
        "review_comment": request.review_comment,
        "metadata":       request.metadata,
    }
    obs = env.step(action)
    return {
        "observation": obs,
        "reward":      obs.get("reward", 0.0),
        "done":        obs.get("done", False),
        "info":        obs.get("metadata", {}),
    }


@app.get("/state")
def state() -> Dict[str, Any]:
    """Return the full internal state of the environment."""
    return env.state()


@app.get("/grade")
def grade() -> Dict[str, Any]:
    """Return the final grade for the current (or last completed) episode."""
    score = env.grade()
    return {
        "score":      score,
        "task_id":    env._task_id,
        "episode_id": env._episode_id,
    }


@app.get("/tasks")
def list_tasks() -> Dict[str, Any]:
    """List available tasks with descriptions."""
    return {
        "tasks": [
            {
                "id":          "task_easy",
                "name":        "Issue Classification",
                "description": "Classify the issue type in isolated code snippets",
                "difficulty":  "easy",
                "max_steps":   20,
            },
            {
                "id":          "task_medium",
                "name":        "Severity & Localization",
                "description": "Classify issue type + assign severity + identify line number",
                "difficulty":  "medium",
                "max_steps":   30,
            },
            {
                "id":          "task_hard",
                "name":        "Full Code Review",
                "description": "Classify, assign severity, pinpoint line, write review comment",
                "difficulty":  "hard",
                "max_steps":   50,
            },
        ]
    }