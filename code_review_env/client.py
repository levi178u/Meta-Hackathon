"""
HTTP Client for the Code Review OpenEnv environment.

Usage
-----
    from client import CodeReviewClient

    client = CodeReviewClient(base_url="http://localhost:7860")
    obs    = client.reset(task_id="task_easy")
    result = client.step(issue_type="bug", severity="error", line_number=5)
    state  = client.state()
    score  = client.grade()
"""

import requests
from typing import Any, Dict, Optional


class CodeReviewClient:
    """
    Thin HTTP wrapper around the Code Review environment server.
    Mirrors the step() / reset() / state() OpenEnv interface.
    """

    def __init__(self, base_url: str = "http://localhost:7860") -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    # ── Core OpenEnv interface ─────────────────────────────────────────────

    def reset(self, task_id: str = "task_easy") -> Dict[str, Any]:
        """Start a new episode and return the initial observation."""
        resp = self._session.post(
            f"{self.base_url}/reset",
            json={"task_id": task_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["observation"]

    def step(
        self,
        issue_type:     str = "bug",
        severity:       str = "warning",
        line_number:    int = 1,
        review_comment: str = "",
        action_type:    str = "classify",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a review action for the current snippet.

        Returns a dict with keys:
            observation, reward, done, info
        """
        payload = {
            "action_type":    action_type,
            "issue_type":     issue_type,
            "severity":       severity,
            "line_number":    line_number,
            "review_comment": review_comment,
            "metadata":       metadata or {},
        }
        resp = self._session.post(
            f"{self.base_url}/step",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def state(self) -> Dict[str, Any]:
        """Return the full internal state of the environment."""
        resp = self._session.get(f"{self.base_url}/state", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def grade(self) -> float:
        """Return the final grade score for the current episode (0.0–1.0)."""
        resp = self._session.get(f"{self.base_url}/grade", timeout=10)
        resp.raise_for_status()
        return resp.json()["score"]

    def health(self) -> bool:
        """Return True if the server is reachable."""
        try:
            resp = self._session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_tasks(self) -> Dict[str, Any]:
        """Return available tasks from the server."""
        resp = self._session.get(f"{self.base_url}/tasks", timeout=10)
        resp.raise_for_status()
        return resp.json()