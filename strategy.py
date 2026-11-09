"""
Правила: нужна ли рассуждёнка, какая стратегия, какая модель, какая политика истории.
Это НЕ ML — детерминированные правила. Легко объяснить коллеге.

ВАЖНО: n_iter_estimate считается в estimator.py и лежит в est, НЕ в feats.
Поэтому compute_strategy принимает est и читает n_iter оттуда.
"""
import pandas as pd

from config import Config


_REASONING_TASK_TYPES = {"data_analysis", "math", "reasoning", "analysis"}
_REASONING_KEYWORDS = ("compute", "calculate", "how many", "prove", "derive",
                       "count", "sum", "average", "median")


def _needs_reasoning(row: dict) -> bool:
    if row.get("task_type") in _REASONING_TASK_TYPES:
        return True
    instr = str(row.get("instruction", "")).lower()
    return any(k in instr for k in _REASONING_KEYWORDS)


def _strategy(row: dict, e: dict) -> str:
    if row.get("feasibility") == "unlikely":
        return "skip"
    if _needs_reasoning(row):
        return "reasoning_single"
    n = int(e.get("n_iter_estimate", 0))
    if n <= 2:
        return "noreason_direct"
    return "noreason_grep"


def _recommended_model(row: dict) -> str:
    if _needs_reasoning(row):
        return "qwen3.8-27b"
    return "qwen3.6-35b-a3b-noreason"


def _history_policy(e: dict) -> str:
    n = int(e.get("n_iter_estimate", 0))
    if n <= 3:
        return "keep"
    if n <= 6:
        return "summarize"
    return "wipe"


def compute_strategy(df: pd.DataFrame, feats: pd.DataFrame,
                     est: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    rows = []
    for idx in df.index:
        row = df.loc[idx].to_dict()
        e = est.loc[idx].to_dict()          # ← n_iter_estimate здесь
        rows.append({
            "needs_reasoning": _needs_reasoning(row),
            "strategy": _strategy(row, e),
            "recommended_model": _recommended_model(row),
            "history_policy": _history_policy(e),
        })
    return pd.DataFrame(rows, index=df.index)