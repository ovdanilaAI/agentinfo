"""
Сборка финального JSON и (опционально) CSV для коллеги.
"""
import json
from pathlib import Path
import pandas as pd


def build_output(df, feats, est, strat, feasibility, knapsack_res,
                 schedule_res, cfg, out_path: str | Path) -> dict:
    out_path = Path(out_path)

    # --- tasks ---
    tasks_out = []
    selected_set = set(knapsack_res["selected"])
    # карта task_id -> agent
    agent_of = {}
    for plan in schedule_res["per_agent_plan"]:
        for tid in plan["tasks"]:
            agent_of[tid] = plan["agent"]

    for idx in df.index:
        row = df.loc[idx].to_dict()
        e = est.loc[idx].to_dict()
        s = strat.loc[idx].to_dict()
        fz = feasibility.loc[idx].to_dict()

        p_solved = (cfg.p_solved_likely if fz["feasibility"] == "likely"
                    else cfg.p_solved_uncertain if fz["feasibility"] == "uncertain"
                    else cfg.p_solved_unlikely)

        cost = e["cost_reason_safe"]
        density = (row.get("reward", 0) * p_solved / cost) if cost > 0 else 0.0

        tasks_out.append({
            "task_id": row.get("task_id"),
            "task_type": row.get("task_type"),
            "check": row.get("check"),
            "reward": row.get("reward"),
            "feasibility": fz["feasibility"],
            "violations": fz["violations"],
            "p_solved": p_solved,
            "needs_reasoning": s["needs_reasoning"],
            "n_iter_estimate": e["n_iter_estimate"],
            "cost_noreason": e["cost_noreason"],
            "cost_reason": e["cost_reason"],
            "cost_reason_safe": e["cost_reason_safe"],
            "seconds_noreason": e["seconds_noreason"],
            "seconds_reason": e["seconds_reason"],
            "seconds_reason_safe": e["seconds_reason_safe"],
            "density": round(density, 6),
            "strategy": s["strategy"],
            "history_policy": s["history_policy"],
            "recommended_model": s["recommended_model"],
            "selected": row.get("task_id") in selected_set,
            "agent": agent_of.get(row.get("task_id")),
        })

    # --- knapsack summary ---
    knapsack_out = {
        "algorithm": cfg.knapsack_algorithm,
        "budget_output_equiv": cfg.budget_output_equiv,
        "selected": knapsack_res["selected"],
        "total_cost_safe": knapsack_res["total_weight"],
        "total_reward_expected": round(knapsack_res["total_value"], 2),
        "n_total": len(df),
        "n_selected": len(knapsack_res["selected"]),
        "n_skipped_unfeasible": int((feasibility["feasibility"] == "unlikely").sum()),
        "n_skipped_budget": max(
            0,
            len(df) - len(knapsack_res["selected"])
                    - int((feasibility["feasibility"] == "unlikely").sum())
        ),
    }

    result = {
        "meta": {
            "estimator": "deterministic_formula_v1",
            "calibrated": False,
            "constants": {
                "input_to_output_ratio": cfg.input_to_output_ratio,
                "budget_output_equiv": cfg.budget_output_equiv,
                "c_sys_in": cfg.c_sys_in,
                "avg_tool_call_tokens": cfg.avg_tool_call_tokens,
                "reasoning_tokens_per_step": cfg.reasoning_tokens_per_step,
                "latency_per_step_sec": cfg.latency_per_step_sec,
                "safety_margin_output": cfg.safety_margin_output,
                "safety_margin_seconds": cfg.safety_margin_seconds,
            },
            "note": "constants are defaults; recalibrate online after first 10-20 runs",
        },
        "tasks": tasks_out,
        "knapsack": knapsack_out,
        "schedule_hint": {
            "n_agents": cfg.n_agents,
            "time_budget_sec": cfg.time_budget_sec,
            **schedule_res,
        },
    }

    # --- запись ---
    out_json = out_path / "kpi_result.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print(f"[output] JSON → {out_json}")

    if cfg.output_csv:
        csv_df = pd.DataFrame(tasks_out)
        csv_path = out_path / "kpi.csv"
        csv_df.to_csv(csv_path, index=False)
        print(f"[output] CSV  → {csv_path}")

    return result