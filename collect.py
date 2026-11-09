"""
Сбор task.json. К каждой строке:
  _path       — путь к task.json
  _dir        — папка задачи (например, task-dir/coding_0003)
  _workspace  — _dir/workspace если существует, иначе _dir
                (данные для работы; math-задачи живут без workspace)
  _has_workspace — флаг: был ли workspace реально
"""
from pathlib import Path
import json
import pandas as pd


def load_tasks(task_dir: str | Path) -> pd.DataFrame:
    task_dir = Path(task_dir)
    if not task_dir.exists():
        raise FileNotFoundError(f"task-dir не найден: {task_dir}")

    rows: list[dict] = []
    skipped = 0

    for f in task_dir.rglob("task.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[collect] skip {f}: {e}")
            skipped += 1
            continue

        task_dir_path = f.parent
        ws = task_dir_path / "workspace"
        has_ws = ws.is_dir()

        data["_path"] = str(f)
        data["_dir"] = str(task_dir_path)
        data["_workspace"] = str(ws if has_ws else task_dir_path)
        data["_has_workspace"] = has_ws
        rows.append(data)

    if not rows:
        raise RuntimeError(
            f"Не найдено ни одного task.json в {task_dir}. "
            f"Проверь структуру: task-dir/<name_NNNN>/task.json"
        )

    df = pd.DataFrame(rows)
    print(f"[collect] загружено {len(df)} задач, пропущено {skipped}")
    print(f"[collect] с workspace: {int(df['_has_workspace'].sum())}, "
          f"без: {int((~df['_has_workspace']).sum())}")
    return df