"""
Точный 0/1-рюкзак через ДП. n<=100, B<=80000 → мгновенно.
Ценность предмета = reward * p_solved.
Вес = cost_reason_safe (worst-case: гарантируем влезание при любом выборе модели).
"""
import numpy as np


def solve_knapsack(items: list[dict], budget: int, scale: int = 1) -> dict:
    """
    items: [{"task_id", "weight", "value"}, ...]
    budget: целое
    scale: огрубление весов (1 = точно; 10 = до десятков)
    Возвращает: selected_ids, total_weight, total_value
    """
    if scale < 1:
        scale = 1
    w = [(it["weight"] + scale - 1) // scale for it in items]  # ceil
    v = [it["value"] for it in items]
    B = budget // scale

    n = len(items)
    # dp[j] = max value at weight j
    dp = np.zeros(B + 1, dtype=np.float64)
    take = np.zeros((n, B + 1), dtype=bool)

    for i in range(n):
        wi, vi = w[i], v[i]
        if wi > B:
            continue
        # идём с конца, чтобы не переиспользовать предмет
        for j in range(B, wi - 1, -1):
            new_val = dp[j - wi] + vi
            if new_val > dp[j]:
                dp[j] = new_val
                take[i, j] = True

    # восстанавливаем набор
    selected = []
    j = B
    for i in range(n - 1, -1, -1):
        if take[i, j]:
            selected.append(items[i]["task_id"])
            j -= w[i]
    selected.reverse()

    total_w = sum(it["weight"] for it in items if it["task_id"] in set(selected))
    total_v = sum(it["value"] for it in items if it["task_id"] in set(selected))
    return {
        "selected": selected,
        "total_weight": int(total_w),
        "total_value": float(total_v),
    }