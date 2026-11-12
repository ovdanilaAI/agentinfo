"""
Загрузчик конфига. Всё, что можно крутить, — в YAML.
"""
from dataclasses import dataclass, fields
from pathlib import Path
import yaml


@dataclass
class Config:
    # курс и бюджет
    input_to_output_ratio: float = 9.5
    budget_output_equiv: int = 80_000

    # агентный фреймворк
    c_sys_in: int = 1000
    c_sys_out: int = 50
    avg_tool_call_tokens: int = 60
    reasoning_tokens_per_step: int = 350
    avg_tool_output_tokens_cap: int = 2000
    files_per_grep: int = 20

    # время
    latency_per_step_sec: float = 3.0
    latency_reasoning_bonus_sec: float = 2.0
    fixed_overhead_sec: float = 5.0

    # safety margin
    safety_margin_output: float = 1.15
    safety_margin_seconds: float = 1.3

    # p_solved priors
    p_solved_likely: float = 0.90
    p_solved_uncertain: float = 0.80
    p_solved_unlikely: float = 0.15

    # рюкзак
    knapsack_algorithm: str = "dp_exact"
    knapsack_budget_scale: int = 1
    use_noreason_cost_when_possible: bool = True

    # планировщик
    n_agents: int = 5
    time_budget_sec: int = 3600

    # фичи
    max_claims_checked: int = 20
    output_csv: bool = True


def load_config(path: str | Path = "config.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        return Config()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    known = {f.name for f in fields(Config)}
    filtered = {k: v for k, v in raw.items() if k in known}
    return Config(**filtered)
