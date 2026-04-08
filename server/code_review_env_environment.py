from uuid import uuid4
from openenv.core.env_server.interfaces import Environment
try:
    from ..models import CodeReviewAction, CodeReviewObservation, CodeReviewState
except ImportError:
    from models import CodeReviewAction, CodeReviewObservation, CodeReviewState

TASKS = [
    {
        "difficulty": "easy",
        "diff_snippet": "def multiply(a, b):\n    return a + b\n",
        "language": "python",
        "file_path": "math_utils.py",
        "pr_description": "Added multiplication function.",
        "author_experience": "junior",
        "ground_truth": {
            "issue_type": "bug",
            "severity": "error",
            "line_number": 2
        }
    },
    {
        "difficulty": "medium",
        "diff_snippet": "1: from flask import request, Flask\n2: app = Flask(__name__)\n3: \n4: @app.route('/exec')\n5: def run_code():\n6:     cmd = request.args.get('cmd')\n7:     import os\n8:     os.system(cmd)\n9:     return 'OK'",
        "language": "python",
        "file_path": "server.py",
        "pr_description": "Adding an endpoint to run quick commands via query param.",
        "author_experience": "mid",
        "ground_truth": {
            "issue_type": "security",
            "severity": "critical",
            "line_number": 8
        }
    },
    {
        "difficulty": "hard",
        "diff_snippet": "1: def process_payment(amount, user):\n2:     if amount > 0:\n3:         user.balance -= amount\n4:         try:\n5:             stripe.charge(amount)\n6:         except stripe.error.CardError:\n7:             pass # Retry later invisibly\n8:     update_db(user)\n",
        "language": "python",
        "file_path": "payments.py",
        "pr_description": "Charge the user through stripe and deduct from their internal balance, ignore card errors to avoid breaking the flow.",
        "author_experience": "senior",
        "ground_truth": {
            "issue_type": "bug",
            "severity": "critical",
            "line_number": 7
        }
    }
]

SEVERITY_LEVELS = {"info": 1, "warning": 2, "error": 3, "critical": 4, "none": 0}

class CodeReviewEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = CodeReviewState(episode_id=str(uuid4()), step_count=0)
        self._task_index = 0
        self._current_task = None

    def reset(self) -> CodeReviewObservation:
        self._task_index = 0
        self._state = CodeReviewState(
            episode_id=str(uuid4()),
            step_count=0,
            task_difficulty=TASKS[self._task_index]["difficulty"],
            remaining_tasks=len(TASKS),
            current_score=0.0
        )
        self._current_task = TASKS[self._task_index]

        return CodeReviewObservation(
            diff_snippet=self._current_task["diff_snippet"],
            language=self._current_task["language"],
            file_path=self._current_task["file_path"],
            pr_description=self._current_task["pr_description"],
            author_experience=self._current_task["author_experience"],
            reward=0.0,
            done=False
        )

    def step(self, action: CodeReviewAction) -> CodeReviewObservation:  # type: ignore[override]
        self._state.step_count += 1
        gt = self._current_task["ground_truth"]
        
        reward = 0.0
        
        # 1. Issue Type Scoring (max 0.3)
        if action.issue_type == gt["issue_type"]:
            reward += 0.3
        elif action.issue_type in ["bug", "security"] and gt["issue_type"] in ["bug", "security"]:
            reward += 0.15 
            
        # 2. Severity Scoring (max 0.2)
        ag_sev_val = SEVERITY_LEVELS.get(action.severity, 0)
        gt_sev_val = SEVERITY_LEVELS.get(gt["severity"], 0)
        sev_diff = abs(ag_sev_val - gt_sev_val)
        if sev_diff == 0:
            reward += 0.2
        elif sev_diff == 1:
            reward += 0.1
            
        # 3. Line Number Scoring (max 0.3)
        line_diff = abs(action.line_number - gt["line_number"])
        if line_diff == 0:
            reward += 0.3
        elif line_diff <= 2:
            reward += 0.15
            
        # 4. Comment Actionability Scoring (max 0.2)
        comment_len = len(action.review_comment.strip())
        if comment_len > 10:
            reward += 0.1
            if any(k in action.review_comment.lower() for k in ["should", "fix", "change", "remove", "update"]):
                reward += 0.1
                
        reward = max(0.0, min(1.0, float(reward)))
        self._state.current_score += reward

        self._task_index += 1
        self._state.remaining_tasks = len(TASKS) - self._task_index
        
        done = self._task_index >= len(TASKS)
        
        if not done:
            self._current_task = TASKS[self._task_index]
            self._state.task_difficulty = self._current_task["difficulty"]

        return CodeReviewObservation(
            diff_snippet=self._current_task["diff_snippet"] if not done else "",
            language=self._current_task["language"] if not done else "",
            file_path=self._current_task["file_path"] if not done else "",
            pr_description=self._current_task["pr_description"] if not done else "",
            author_experience=self._current_task["author_experience"] if not done else "",
            reward=reward,
            done=done,
            metadata={"ground_truth": gt, "action_received": action.dict()}
        )

    @property
    def state(self) -> CodeReviewState:
        return self._state
