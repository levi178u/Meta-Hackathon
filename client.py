from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState

class CodeReviewEnv(EnvClient[CodeReviewAction, CodeReviewObservation, CodeReviewState]):
    """Client for the Code Review Environment."""

    def _step_payload(self, action: CodeReviewAction) -> Dict:
        return {
            "issue_type": action.issue_type,
            "severity": action.severity,
            "line_number": action.line_number,
            "review_comment": action.review_comment
        }

    def _parse_result(self, payload: Dict) -> StepResult[CodeReviewObservation]:
        obs_data = payload.get("observation", {})
        observation = CodeReviewObservation(
            diff_snippet=obs_data.get("diff_snippet", ""),
            language=obs_data.get("language", ""),
            file_path=obs_data.get("file_path", ""),
            pr_description=obs_data.get("pr_description", ""),
            author_experience=obs_data.get("author_experience", ""),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> CodeReviewState:
        return CodeReviewState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_difficulty=payload.get("task_difficulty", "easy"),
            remaining_tasks=payload.get("remaining_tasks", 0),
            current_score=payload.get("current_score", 0.0)
        )
