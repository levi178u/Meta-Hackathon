from typing import Any, Dict
from pydantic import BaseModel, Field

# Action Model


class CodeReviewAction(BaseModel):
    """
    Action the agent takes on the current code snippet.

    Fields
    ------
    action_type : str
        One of:
          - "classify"                       (Task Easy)
          - "classify_and_localize"          (Task Medium)
          - "full_review"                    (Task Hard)
    issue_type : str
        Type of issue found. Allowed:
          sql_injection | xss | security | bug | performance | style | no_issue
    severity : str
        Issue severity. Allowed: info | warning | error | critical
    line_number : int
        Line number where the issue occurs. Use 0 for no_issue.
    review_comment : str
        Written review comment explaining the issue and suggesting a fix.
        Required for task_hard; ignored for task_easy.
    metadata : dict
        Optional extra fields.
    """

    action_type:    str = Field(default="classify",   description="Type of review action")
    issue_type:     str = Field(default="bug",        description="Category of the code issue")
    severity:       str = Field(default="warning",    description="Severity level of the issue")
    line_number:    int = Field(default=1,            description="Line number of the issue (0 = no issue)")
    review_comment: str = Field(default="",           description="Written review comment for task_hard")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional extra metadata")

    class Config:
        extra = "allow"



# Observation Model


class CodeReviewObservation(BaseModel):
    """
    Observation returned after each step (and on reset).

    Fields
    ------
    snippet_id : str
        Unique identifier for the current code snippet.
    language : str
        Programming language (python, javascript, etc.).
    file_path : str
        Simulated file path of the snippet in a PR.
    diff : str
        The actual code diff / snippet to review.
    description : str
        Short description of what the code does.
    queue_size : int
        Number of snippets remaining in the queue (including current).
    current_step : int
        Number of steps taken in this episode.
    task_id : str
        Active task (task_easy | task_medium | task_hard).
    snippets_reviewed : int
        How many snippets have been reviewed so far.
    score_so_far : float
        Cumulative reward accumulated this episode.
    done : bool
        Whether the episode has ended.
    reward : float
        Reward for the last action (0.0 on reset).
    metadata : dict
        Extra info including reward_breakdown after each step.
    """

    snippet_id:        str   = ""
    language:          str   = ""
    file_path:         str   = ""
    diff:              str   = ""
    description:       str   = ""
    queue_size:        int   = 0
    current_step:      int   = 0
    task_id:           str   = "task_easy"
    snippets_reviewed: int   = 0
    score_so_far:      float = 0.0
    done:              bool  = False
    reward:            float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"



# Reward Model


class CodeReviewReward(BaseModel):
    """
    Structured reward breakdown for transparency and debugging.

    Fields
    ------
    total : float
        Total reward for the step (0.0–1.0).
    issue_type_score : float
        Partial credit for correct issue classification.
    severity_score : float
        Partial credit for correct severity assignment.
    line_score : float
        Partial credit for correct line number identification.
    comment_score : float
        Partial credit for review comment quality (task_hard only).
    penalty : float
        Deduction for invalid action values.
    rationale : str
        Human-readable explanation of the reward.
    """

    total:            float = 0.0
    issue_type_score: float = 0.0
    severity_score:   float = 0.0
    line_score:       float = 0.0
    comment_score:    float = 0.0
    penalty:          float = 0.0
    rationale:        str   = ""

    class Config:
        extra = "allow"



# State Model  (returned by /state endpoint)


class CodeReviewState(BaseModel):
    """
    Full internal state of the environment.

    Fields
    ------
    episode_id : str
        Unique ID for the current episode.
    task_id : str
        Active task.
    current_step : int
        Steps elapsed.
    max_steps : int
        Episode horizon.
    snippets_reviewed : int
        Snippets handled so far.
    total_snippets : int
        Total snippets in this episode's queue.
    cumulative_score : float
        Sum of rewards so far.
    done : bool
        Whether the episode is finished.
    """

    episode_id:        str   = ""
    task_id:           str   = "task_easy"
    current_step:      int   = 0
    max_steps:         int   = 20
    snippets_reviewed: int   = 0
    total_snippets:    int   = 0
    cumulative_score:  float = 0.0
    done:              bool  = False

    class Config:
        extra = "allow"