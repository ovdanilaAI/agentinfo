"""
Сборка финального JSON и CSV. Использует effective_weight для рюкзака.
"""
import json
from pathlib import Path
import pandas as pd


def _p_solved(feasibility: str, cfg) -> float:
    if feasibility == "likely":
        return cfg.p_solved_likely
    if feasibility == "uncertain":
        return cfg.p_solved_uncertain
    return cfg.p_solved_unlikely


def _effective_weight(idx, est, strat, cfg) -> int:
    needs_reasoning = bool(strat.loc[idx, "needs_reasoning"])
    if cfg.use_noreason_cost_when_possible and not needs_reasoning:
        return int(est.loc[idx, "cost_noreason_safe"])
    return int(est.loc[idx, "cost_reason_safe"])


def build_output(df, feats, est, strat, feasibility, knapsack_res,
                 schedule_res, cfg, out_path: str | Path) -> dict:
    out_path = Path(out_path)
    selected_set = set(knapsack_res["selected"])

    agent_of = {}
    for plan in schedule_res["per_agent_plan"]:
        for tid in plan["tasks"]:
            agent_of[tid] = plan["agent"]

    tasks_out = []
    for idx in df.index:
        row = df.loc[idx].to_dict()
        e = est.loc[idx].to_dict()
        s = strat.loc[idx].to_dict()
        fz = feasibility.loc[idx].to_dict()

        p_solved = _p_solved(fz["feasibility"], cfg)
        eff_weight = _effective_weight(idx, est, strat, cfg)
        density = (row.get("reward", 0) * p_solved / eff_weight) if eff_weight > 0 else 0.0

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
            "cost_noreason_safe": e["cost_noreason_safe"],
            "cost_reason_safe": e["cost_reason_safe"],
            "effective_cost_for_knapsack": eff_weight,
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

    n_unfeasible = int((feasibility["feasibility"] == "unlikely").sum())
    knapsack_out = {
        "algorithm": cfg.knapsack_algorithm,
        "budget_output_equiv": cfg.budget_output_equiv,
        "selected": knapsack_res["selected"],
        "total_cost_safe": knapsack_res["total_weight"],
        "total_reward_expected": round(knapsack_res["total_value"], 2),
        "n_total": len(df),
        "n_selected": len(knapsack_res["selected"]),
        "n_skipped_unfeasible": n_unfeasible,
        "n_skipped_budget": max(0, len(df) - len(knapsack_res["selected"]) - n_unfeasible),
    }

    result = {
        "meta": {
            "estimator": "deterministic_formula_v1_soft",
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
                "p_solved_likely": cfg.p_solved_likely,
                "p_solved_uncertain": cfg.p_solved_uncertain,
                "p_solved_unlikely": cfg.p_solved_unlikely,
                "use_noreason_cost_when_possible": cfg.use_noreason_cost_when_possible,
            },
            "note": "soft knapsack: unlikely included with low p_solved; noreason cost used when possible",
        },
        "tasks": tasks_out,
        "knapsack": knapsack_out,
        "schedule_hint": {
            "n_agents": cfg.n_agents,
            "time_budget_sec": cfg.time_budget_sec,
            **schedule_res,
        },
    }

    out_json = out_path / "kpi_result.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print(f"[output] JSON → {out_json}")

    if cfg.output_csv:
        pd.DataFrame(tasks_out).to_csv(out_path / "kpi.csv", index=False)
        print(f"[output] CSV  → {out_path / 'kpi.csv'}")

    return result
