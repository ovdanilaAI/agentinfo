"""
Формула оценки стоимости и времени. Детерминированно, по признакам.
Раздельно: выход (бюджет) и вход (с курсом 9.5).

cost_noreason / cost_reason — СЫРЫЕ (без safety).
cost_*_safe — с ОДНИМ safety_margin_output.
"""
import math
import pandas as pd

from config import Config


def _n_iterations(f: dict, cfg: Config) -> int:
    n = 2
    if f.get("has_workspace"):
        if f["kb_files_count"]:
            n += math.ceil(f["kb_files_count"] / max(cfg.files_per_grep, 1))
        n += f["n_files_mentioned"]
        n += 2 * f["has_multi_step"]
    else:
        n += 1 if f["has_multi_step"] else 0
    return int(max(n, 1))


def _avg_tool_output(f: dict, cfg: Config) -> int:
    if not f.get("has_workspace"):
        return 0
    avg_bytes = f["avg_file_bytes"] or f["ref_files_bytes"] or 0
    return int(min(avg_bytes / 4, cfg.avg_tool_output_tokens_cap))


def _reasoning_per_step(row: dict, cfg: Config) -> int:
    tt = str(row.get("task_type", ""))
    if tt in ("math", "reasoning", "analysis"):
        return cfg.reasoning_tokens_per_step
    if tt == "data_analysis":
        return int(cfg.reasoning_tokens_per_step * 0.7)
    return int(cfg.reasoning_tokens_per_step * 0.3)


def estimate(df: pd.DataFrame, feats: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    rows = []
    for idx in df.index:
        f = feats.loc[idx].to_dict()
        row = df.loc[idx].to_dict()
        n_iter = _n_iterations(f, cfg)
        avg_tool_out = _avg_tool_output(f, cfg)
        reasoning_per_step = _reasoning_per_step(row, cfg)

        # --- выход (в бюджетной единице) ---
        y_out_noreason = (cfg.c_sys_out
                          + n_iter * cfg.avg_tool_call_tokens
                          + f["expected_tokens"])
        y_out_reason = (cfg.c_sys_out
                        + n_iter * (cfg.avg_tool_call_tokens + reasoning_per_step)
                        + f["expected_tokens"])

        # --- вход: ограничиваем число чтений 3 (агент читает файл 1-3 раза) ---
        n_reads = min(n_iter, 3)
        y_in = cfg.c_sys_in + f["instr_tokens"] + n_reads * avg_tool_out

        # --- сырая стоимость (без safety) ---
        cost_noreason_raw = y_out_noreason + y_in / cfg.input_to_output_ratio
        cost_reason_raw = y_out_reason + y_in / cfg.input_to_output_ratio

        # --- время ---
        sec_noreason = cfg.fixed_overhead_sec + n_iter * cfg.latency_per_step_sec
        sec_reason = (cfg.fixed_overhead_sec
                      + n_iter * (cfg.latency_per_step_sec + cfg.latency_reasoning_bonus_sec))

        rows.append({
            "n_iter_estimate": n_iter,
            "avg_tool_output": avg_tool_out,
            "y_out_noreason": int(y_out_noreason),
            "y_out_reason": int(y_out_reason),
            "y_in": int(y_in),
            "cost_noreason": int(round(cost_noreason_raw)),
            "cost_reason": int(round(cost_reason_raw)),
            "cost_noreason_safe": int(round(cost_noreason_raw * cfg.safety_margin_output)),
            "cost_reason_safe": int(round(cost_reason_raw * cfg.safety_margin_output)),
            "seconds_noreason": round(sec_noreason, 1),
            "seconds_reason": round(sec_reason, 1),
            "seconds_reason_safe": round(sec_reason * cfg.safety_margin_seconds, 1),
        })
    return pd.DataFrame(rows, index=df.index)