import asyncio
import os
import json
import textwrap
from typing import List, Optional

from openai import OpenAI

from client import CodeReviewEnv, CodeReviewAction

IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "code_review_env:latest")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
TASK_NAME = "code-review"
BENCHMARK = "code_review_env"
MAX_STEPS = 3
TEMPERATURE = 0.0

SUCCESS_SCORE_THRESHOLD = 0.5  # Need at least half points across 3 tasks 

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert AI code reviewer. Your task is to review the given code snippet and metadata, and identify the primary issue.
    You must output a JSON object exactly matching this schema:
    {
      "issue_type": "bug" | "security" | "style" | "performance" | "no-issue",
      "severity": "info" | "warning" | "error" | "critical" | "none",
      "line_number": <integer>,
      "review_comment": "<actionable comment>"
    }
    """
).strip()

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

def build_user_prompt(step: int, obs, state) -> str:
    return textwrap.dedent(
        f"""
        Please review the following code.
        
        File Path: {obs.file_path}
        Language: {obs.language}
        Author Experience: {obs.author_experience}
        PR Description: {obs.pr_description}
        
        Task Difficulty: {state.task_difficulty}
        Tasks Remaining: {state.remaining_tasks}
        Current Score: {state.current_score}
        
        Code Snippet:
        {obs.diff_snippet}
        """
    ).strip()

def get_model_message(client: OpenAI, step: int, obs, state) -> CodeReviewAction:
    user_prompt = build_user_prompt(step, obs, state)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
        )
        text = completion.choices[0].message.content.strip()
        data = json.loads(text)
        return CodeReviewAction(**data)
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return CodeReviewAction(
            issue_type="no-issue",
            severity="none",
            line_number=-1,
            review_comment="Failed to evaluate."
        )

async def main() -> None:
    if not API_KEY:
        print("[DEBUG] HF_TOKEN or API_KEY not set", flush=True)
        # Continue anyway assuming some endpoints might not require it for local testing
    
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY if API_KEY else "dummy")

    # Assuming we will use a docker container if applicable, but fallback to running server
    try:
        env = await CodeReviewEnv.from_docker_image(IMAGE_NAME)
    except Exception as e:
        print("[DEBUG] Docker image failed or missing. Attempting localhost fallback.", e)
        env = CodeReviewEnv(base_url="http://127.0.0.1:8000")

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset()
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break
                
            state = await env.state()

            action = get_model_message(client, step, obs, state)
            action_str = json.dumps(action.dict())

            result = await env.step(action)
            obs = result.observation

            reward = result.reward or 0.0
            done = result.done
            error = None

            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            if done:
                break

        score = sum(rewards) / float(MAX_STEPS) if MAX_STEPS > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error (container cleanup): {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

if __name__ == "__main__":
    asyncio.run(main())