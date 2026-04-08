from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field
from typing import Literal

IssueType = Literal["bug", "security", "style", "performance", "no-issue"]
Severity = Literal["info", "warning", "error", "critical", "none"]

class CodeReviewAction(Action):
    """Action for the Code Review Agent to submit its review."""
    issue_type: IssueType = Field(..., description="The type of the primary issue found.")
    severity: Severity = Field(..., description="The severity of the primary issue.")
    line_number: int = Field(..., description="The line number where the issue occurs. -1 if no issue.")
    review_comment: str = Field(..., description="A short actionable review comment.")

class CodeReviewObservation(Observation):
    """Observation representing a code diff for review."""
    diff_snippet: str = Field(default="", description="The code snippet or diff to review.")
    language: str = Field(default="", description="Programming language of the snippet.")
    file_path: str = Field(default="", description="Path of the file being reviewed.")
    pr_description: str = Field(default="", description="A short PR description providing context.")
    author_experience: str = Field(default="", description="Experience level of the author: junior, mid, senior.")

class CodeReviewState(State):
    """State containing metadata about the task being executed."""
    task_difficulty: str = Field(default="easy", description="Difficulty of the current task.")
    remaining_tasks: int = Field(default=0, description="Number of tasks remaining in the episode.")
    current_score: float = Field(default=0.0, description="Current accumulated score.")
