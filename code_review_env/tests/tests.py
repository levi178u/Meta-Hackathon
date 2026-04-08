"""
Tests for the Code Review OpenEnv environment.
Run with: pytest test/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from server.environment import (
    CodeReviewEnvironment,
    _score_issue_type,
    _score_severity,
    _score_line,
    _score_comment,
    grade_easy,
    grade_medium,
    grade_hard,
)


# ---------------------------------------------------------------------------
# Unit tests – scoring helpers
# ---------------------------------------------------------------------------

class TestScoreIssueType:
    def test_exact_match(self):
        score, _ = _score_issue_type("bug", "bug")
        assert score == 1.0

    def test_same_security_family(self):
        score, _ = _score_issue_type("security", "sql_injection")
        assert score == 0.5

    def test_xss_in_security_family(self):
        score, _ = _score_issue_type("xss", "security")
        assert score == 0.5

    def test_completely_wrong(self):
        score, _ = _score_issue_type("style", "sql_injection")
        assert score == 0.0

    def test_no_issue_exact(self):
        score, _ = _score_issue_type("no_issue", "no_issue")
        assert score == 1.0

    def test_no_issue_wrong(self):
        score, _ = _score_issue_type("bug", "no_issue")
        assert score == 0.0


class TestScoreSeverity:
    def test_exact_match(self):
        score, _ = _score_severity("critical", "critical")
        assert score == 1.0

    def test_off_by_one_up(self):
        score, _ = _score_severity("critical", "error")
        assert score == 0.5

    def test_off_by_one_down(self):
        score, _ = _score_severity("info", "warning")
        assert score == 0.5

    def test_way_off(self):
        score, _ = _score_severity("info", "critical")
        assert score == 0.0


class TestScoreLine:
    def test_exact_match(self):
        score, _ = _score_line(5, 5)
        assert score == 1.0

    def test_within_two(self):
        score, _ = _score_line(3, 5)
        assert score == 0.5

    def test_just_outside_two(self):
        score, _ = _score_line(8, 5)
        assert score == 0.0

    def test_no_issue_line_zero(self):
        score, _ = _score_line(0, 0)
        assert score == 1.0

    def test_no_issue_any_line(self):
        # When true_line == 0 (no_issue), predicted line doesn't matter
        score, _ = _score_line(99, 0)
        assert score == 1.0


class TestScoreComment:
    def test_empty_comment(self):
        score, _ = _score_comment("", {"review_hints": [], "keywords": []})
        assert score == 0.0

    def test_short_comment(self):
        score, _ = _score_comment("bad", {"review_hints": [], "keywords": []})
        assert score == 0.0

    def test_good_comment_with_hints(self):
        snippet = {
            "review_hints": ["parameterized", "sql injection", "escape"],
            "keywords": ["SQL", "query"],
        }
        comment = (
            "This code is vulnerable to SQL injection because it uses string interpolation. "
            "Use parameterized queries or prepared statements to safely escape user input."
        )
        score, _ = _score_comment(comment, snippet)
        assert score > 0.4

    def test_comment_no_hints(self):
        snippet = {"review_hints": [], "keywords": []}
        comment = "This looks fine. The code is well structured and handles edge cases properly."
        score, _ = _score_comment(comment, snippet)
        assert score > 0.0


# ---------------------------------------------------------------------------
# Unit tests – graders
# ---------------------------------------------------------------------------

class TestGraders:
    def _make_log(self, n=3, correct=True):
        snippet = {
            "review_hints": ["parameterized", "sql injection"],
            "keywords": ["SQL", "injection"],
        }
        entries = []
        for i in range(n):
            entries.append({
                "snippet_id":           f"s00{i}",
                "true_issue_type":      "sql_injection",
                "true_severity":        "critical",
                "true_line":            2,
                "predicted_issue_type": "sql_injection" if correct else "style",
                "predicted_severity":   "critical"      if correct else "info",
                "predicted_line":       2               if correct else 99,
                "review_comment": (
                    "Use parameterized queries to prevent SQL injection attacks. "
                    "Never interpolate user input directly into SQL strings."
                    if correct else ""
                ),
                "snippet": snippet,
            })
        return entries

    def test_grade_easy_perfect(self):
        assert grade_easy(self._make_log(correct=True)) == 1.0

    def test_grade_easy_zero(self):
        assert grade_easy(self._make_log(correct=False)) == 0.0

    def test_grade_easy_empty(self):
        assert grade_easy([]) == 0.0

    def test_grade_medium_perfect(self):
        assert grade_medium(self._make_log(correct=True)) == 1.0

    def test_grade_medium_zero(self):
        assert grade_medium(self._make_log(correct=False)) == 0.0

    def test_grade_hard_perfect_scores_high(self):
        score = grade_hard(self._make_log(correct=True))
        # Issue + severity + line are perfect; comment gets partial credit
        assert score > 0.5

    def test_grade_hard_empty(self):
        assert grade_hard([]) == 0.0


# ---------------------------------------------------------------------------
# Integration tests – Environment class
# ---------------------------------------------------------------------------

class TestEnvironment:
    def test_reset_returns_observation(self):
        env = CodeReviewEnvironment()
        obs = env.reset(task_id="task_easy")
        assert "snippet_id" in obs
        assert "diff" in obs
        assert obs["done"] is False
        assert obs["reward"] == 0.0

    def test_step_returns_reward_in_range(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        obs = env.step({"issue_type": "bug", "severity": "error", "line_number": 1})
        assert "reward" in obs
        assert 0.0 <= obs["reward"] <= 1.0

    def test_episode_terminates(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        action = {"issue_type": "bug", "severity": "warning", "line_number": 1, "review_comment": ""}
        done = False
        steps = 0
        while not done and steps < 50:
            obs = env.step(action)
            done = obs.get("done", False)
            steps += 1
        assert done is True

    def test_state_returns_metadata(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_medium")
        state = env.state()
        assert "episode_id" in state
        assert state["task_id"] == "task_medium"
        assert state["done"] is False

    def test_grade_in_valid_range(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        action = {"issue_type": "bug", "severity": "error", "line_number": 1}
        obs = env.step(action)
        while not obs.get("done", False):
            obs = env.step(action)
        score = env.grade()
        assert 0.0 <= score <= 1.0

    def test_invalid_issue_type_penalized_not_crashed(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        obs = env.step({"issue_type": "TOTALLY_INVALID", "severity": "error", "line_number": 1})
        assert "reward" in obs  # should not raise

    def test_invalid_severity_penalized_not_crashed(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        obs = env.step({"issue_type": "bug", "severity": "SUPER_BAD", "line_number": 1})
        assert "reward" in obs

    def test_all_three_tasks_run(self):
        for task_id in ["task_easy", "task_medium", "task_hard"]:
            env = CodeReviewEnvironment()
            obs = env.reset(task_id=task_id)
            assert obs["task_id"] == task_id
            result = env.step({
                "issue_type":     "bug",
                "severity":       "error",
                "line_number":    2,
                "review_comment": "This has a bug. You should add a guard clause for empty inputs.",
            })
            assert 0.0 <= result["reward"] <= 1.0

    def test_reward_breakdown_in_metadata(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_hard")
        obs = env.step({
            "issue_type":     "sql_injection",
            "severity":       "critical",
            "line_number":    2,
            "review_comment": "Use parameterized queries to prevent SQL injection.",
        })
        assert "reward_breakdown" in obs["metadata"]
        bd = obs["metadata"]["reward_breakdown"]
        assert "issue_type" in bd
        assert "severity"   in bd
        assert "line"       in bd
        assert "comment"    in bd
        assert "total"      in bd

    def test_step_after_done_returns_safely(self):
        env = CodeReviewEnvironment()
        env.reset(task_id="task_easy")
        action = {"issue_type": "bug", "severity": "warning", "line_number": 1}
        for _ in range(30):
            obs = env.step(action)
            if obs.get("done"):
                break
        # Step again after done — should not crash
        obs2 = env.step(action)
        assert obs2 is not None