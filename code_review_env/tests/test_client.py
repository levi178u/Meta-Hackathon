from client import CodeReviewClient

env = CodeReviewClient(base_url="http://localhost:7860")

# Check server is up
print("Server healthy:", env.health())

# ── Task Easy: just classification ──────────────────────────────
print("\n=== TASK EASY ===")
obs = env.reset(task_id="task_easy")
print(f"File: {obs['file_path']}")
print(f"Language: {obs['language']}")
print(f"Diff:\n{obs['diff']}")

total_reward = 0.0
while not obs["done"]:
    result = env.step(
        issue_type="sql_injection",
        severity="critical",
        line_number=2,
        action_type="classify",
    )
    total_reward += result["reward"]
    obs = result["observation"]
    print(f"  Reward: {result['reward']:.3f} | Done: {result['done']}")

print(f"Final grade: {env.grade():.3f}")
print(f"Total reward accumulated: {total_reward:.3f}")

# ── Task Medium: classify + severity + line ──────────────────────
print("\n=== TASK MEDIUM ===")
obs = env.reset(task_id="task_medium")

while not obs["done"]:
    result = env.step(
        issue_type="bug",
        severity="error",
        line_number=5,
        action_type="classify_and_localize",
    )
    obs = result["observation"]
    bd = result["info"].get("reward_breakdown", {})
    print(f"  issue={bd.get('issue_type', '?'):.2f}  "
          f"sev={bd.get('severity', '?'):.2f}  "
          f"line={bd.get('line', '?'):.2f}  "
          f"total={bd.get('total', '?'):.2f}")

print(f"Final grade: {env.grade():.3f}")

# ── Task Hard: full review ───────────────────────────────────────
print("\n=== TASK HARD ===")
obs = env.reset(task_id="task_hard")

while not obs["done"]:
    result = env.step(
        issue_type="bug",
        severity="error",
        line_number=3,
        review_comment=(
            "This function will throw a ZeroDivisionError when passed an empty list. "
            "Add a guard clause at the top: if not numbers: return 0.0"
        ),
        action_type="full_review",
    )
    obs = result["observation"]
    print(f"  Reward: {result['reward']:.3f}")

print(f"Final grade: {env.grade():.3f}")