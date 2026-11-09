"""
LPT-распаковка выбранных задач по агентам.
Каждый агент ≤ time_budget_sec (с safety margin).
"""
def schedule_lpt(tasks: list[dict], n_agents: int, time_budget: int) -> dict:
    """
    tasks: [{"task_id", "seconds", "cost", "reward"}, ...]
    Возвращает per_agent_plan и признак влезли ли.
    """
    # LPT: сортируем по убыванию времени
    tasks_sorted = sorted(tasks, key=lambda t: t["seconds"], reverse=True)
    bins = [{"tasks": [], "seconds": 0.0, "cost": 0, "reward": 0.0}
            for _ in range(n_agents)]

    for t in tasks_sorted:
        # кладём в агента с минимальной загрузкой
        i = min(range(n_agents), key=lambda k: bins[k]["seconds"])
        bins[i]["tasks"].append(t["task_id"])
        bins[i]["seconds"] += t["seconds"]
        bins[i]["cost"] += t["cost"]
        bins[i]["reward"] += t["reward"]

    fits = all(b["seconds"] <= time_budget for b in bins)
    return {
        "per_agent_plan": [
            {
                "agent": i + 1,
                "tasks": b["tasks"],
                "est_seconds_safe": round(b["seconds"], 1),
                "est_cost_safe": b["cost"],
                "est_reward": round(b["reward"], 2),
            }
            for i, b in enumerate(bins)
        ],
        "fits_in_time": fits,
        "max_agent_seconds": round(max(b["seconds"] for b in bins), 1),
    }