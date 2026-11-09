"""
Полный пайплайн. Запуск: python main.py /task-dir
"""
import sys
from pathlib import Path
import pandas as pd

from config import load_config
from collect import load_tasks
from fs_claims import verify_claims
from features import build_features
from estimator import estimate
from strategy import compute_strategy
from knapsack import solve_knapsack
from scheduler import schedule_lpt
from output import build_output


def run(task_dir: str, config_path: str = "config.yaml"):
    cfg = load_config(config_path)
    task_dir = Path(task_dir)

    # 1. собрать
    df = load_tasks(task_dir)

    # 2. признаки (бесплатно)
    feats = build_features(df)

    # 3. feasibility
    fz_rows = []
    for _, row in df.iterrows():
        fz_rows.append(
            verify_claims(
                workspace=row["_workspace"],
                instruction=row.get("instruction", ""),
                has_workspace=bool(row["_has_workspace"]),
                max_claims=cfg.max_claims_checked,
            )
        )
    feasibility = pd.DataFrame(fz_rows, index=df.index)

    # 4. оценка стоимости/времени
    est = estimate(df, feats, cfg)

    # 5. стратегии
    strat = compute_strategy(df, feats, est, cfg)

    # 6. items для рюкзака (только task_id, weight, value)
    items = []
    for idx in df.index:
        row = df.loc[idx]
        fz = feasibility.loc[idx]
        if fz["feasibility"] == "unlikely":
            continue
        p_solved = (cfg.p_solved_likely if fz["feasibility"] == "likely"
                    else cfg.p_solved_uncertain)
        items.append({
            "task_id": row["task_id"],
            "weight": int(est.loc[idx, "cost_reason_safe"]),
            "value": float(row.get("reward", 0)) * p_solved,
        })

    # 7. рюкзак
    knap = solve_knapsack(items, cfg.budget_output_equiv, cfg.knapsack_budget_scale)
    print(f"[knapsack] выбрано {len(knap['selected'])} из {len(df)}, "
          f"стоимость {knap['total_weight']}/{cfg.budget_output_equiv}")

    # 8. планировщик — ОТДЕЛЬНЫЙ список с полем seconds
    sel_ids = set(knap["selected"])
    sched_tasks = []
    for idx in df.index:
        tid = df.loc[idx, "task_id"]
        if tid not in sel_ids:
            continue
        sched_tasks.append({
            "task_id": tid,
            "seconds": float(est.loc[idx, "seconds_reason_safe"]),
            "cost": int(est.loc[idx, "cost_reason_safe"]),
            "reward": float(df.loc[idx].get("reward", 0)),
        })
    sched = schedule_lpt(sched_tasks, cfg.n_agents, cfg.time_budget_sec)
    print(f"[scheduler] fits_in_time={sched['fits_in_time']}, "
          f"max_agent={sched['max_agent_seconds']}s")

    # 9. выход
    result = build_output(df, feats, est, strat, feasibility, knap, sched, cfg, task_dir)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python main.py /task-dir [config.yaml]")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "config.yaml")