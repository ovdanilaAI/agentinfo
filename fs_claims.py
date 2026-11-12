"""
Детектор невыполнимых задач. Проверяем утверждения из instruction
против реальной файловой системы ВНУТРИ workspace.

МЯГКАЯ ВЕРСИЯ:
  - выходные файлы (answer.txt) не проверяются
  - нет workspace + 1-2 упомянутых файла → uncertain (не unlikely)
  - отсутствие неключевой директории → мягкое (uncertain), не hard
  - hard violations оставляют unlikely, но p_solved для unlikely = 0.15 (не 0.05)
"""
import csv
import re
from pathlib import Path


_RE_FILE = re.compile(r"\b([\w\-/]+\.(?:csv|json|md|txt|py|yaml|yml|log))\b", re.I)
_RE_ROWS = re.compile(r"\b(\d{1,7})\s+rows?\b", re.I)
_RE_COLUMNS = re.compile(r"columns?\s*[:=]?\s*([\w,\s]+)", re.I)
_RE_DIR = re.compile(r"\b([\w\-]+)/\b")


# --- выходные файлы (НЕ проверять существование) ---
_RE_OUTPUT_CONTEXT = re.compile(
    r"(?:write|save|create|store|put|output|echo|>|>>)"
    r"[^\n]{0,80}?"
    r"\b([\w\-/]+\.(?:txt|json|csv|md|py|yaml|yml))\b",
    re.I,
)
_OUTPUT_NAME_WHITELIST = {
    "answer.txt", "output.txt", "result.txt", "solution.txt",
    "out.txt", "answer.json", "output.json", "result.json",
}


def _extract_output_files(instruction: str) -> set[str]:
    found = {m.lower() for m in _RE_OUTPUT_CONTEXT.findall(instruction)}
    found |= _OUTPUT_NAME_WHITELIST
    return found


def _extract_claims(instruction: str, max_claims: int) -> dict:
    raw_files = list(dict.fromkeys(_RE_FILE.findall(instruction)))
    output_files = _extract_output_files(instruction)
    files = [
        f for f in raw_files
        if Path(f).name.lower() not in output_files and f.lower() not in output_files
    ][:max_claims]

    dirs = list(dict.fromkeys(_RE_DIR.findall(instruction)))[:max_claims]

    rows: list[tuple[str, int]] = []
    for n_str in _RE_ROWS.findall(instruction):
        if files:
            rows.append((files[0], int(n_str)))

    columns: list[tuple[str, list[str]]] = []
    for m in _RE_COLUMNS.finditer(instruction):
        cols = [c.strip() for c in re.split(r"[,\s]+", m.group(1)) if c.strip()]
        cols = [c for c in cols if re.fullmatch(r"[A-Za-z_]\w*", c)]
        if cols and files:
            columns.append((files[0], cols))

    return {"files": files, "dirs": dirs, "rows": rows, "columns": columns}


def _find_in_workspace(ws: Path, name: str) -> Path | None:
    direct = ws / name
    if direct.exists():
        return direct
    matches = list(ws.rglob(Path(name).name))
    return matches[0] if matches else None


def _csv_rows_and_columns(path: Path) -> tuple[int, list[str]] | None:
    try:
        with path.open(newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return 0, []
            n = sum(1 for _ in reader)
            return n, [c.strip() for c in header]
    except Exception:
        return None


def verify_claims(workspace: str | Path, instruction: str,
                  has_workspace: bool, max_claims: int = 20) -> dict:
    ws = Path(workspace)
    claims = _extract_claims(instruction, max_claims)
    violations: list[str] = []
    checked = 0
    hard_violated = 0

    # нет workspace, но упомянуты > 2 входных файлов — скорее ловушка.
    # 1-2 файла — может быть, файл лежит в другом месте или это описание, не приговор.
    if not has_workspace and len(claims["files"]) > 2:
        return {
            "feasibility": "unlikely",
            "violations": [f"no_workspace_but_files_mentioned:{','.join(claims['files'])}"],
            "n_claims": len(claims["files"]),
            "n_violated": len(claims["files"]),
        }

    # 1. файлы
    for name in claims["files"]:
        checked += 1
        if _find_in_workspace(ws, name) is None:
            violations.append(f"file_missing:{name}")
            hard_violated += 1

    # 2. директории — ключевые жёстко, остальные мягко
    _KEY_DIRS = {"kb", "data", "docs"}
    for d in claims["dirs"]:
        if d.lower() in {"current", "the", "a", "in"}:
            continue
        checked += 1
        dd = ws / d
        if not dd.exists() or not dd.is_dir():
            violations.append(f"dir_missing:{d}")
            if d.lower() in _KEY_DIRS:
                hard_violated += 1
            # неключевая директория — мягкое нарушение (просто в violations)
        elif not any(dd.iterdir()):
            violations.append(f"dir_empty:{d}")
            hard_violated += 1

    # 3. число строк CSV
    for fname, expected_n in claims["rows"]:
        path = _find_in_workspace(ws, fname)
        if path is None or path.suffix.lower() != ".csv":
            continue
        checked += 1
        got = _csv_rows_and_columns(path)
        if got is None:
            violations.append(f"rows_unreadable:{fname}")
            continue
        n_actual, _ = got
        if abs(n_actual - expected_n) > max(1, expected_n * 0.05):
            violations.append(f"rows_mismatch:{fname}:{n_actual}!={expected_n}")
            hard_violated += 1

    # 4. колонки CSV
    for fname, expected_cols in claims["columns"]:
        path = _find_in_workspace(ws, fname)
        if path is None or path.suffix.lower() != ".csv":
            continue
        checked += 1
        got = _csv_rows_and_columns(path)
        if got is None:
            continue
        _, actual_cols = got
        actual_low = {c.lower() for c in actual_cols}
        missing = [c for c in expected_cols if c.lower() not in actual_low]
        if missing:
            violations.append(f"columns_missing:{fname}:{','.join(missing)}")
            hard_violated += 1

    # --- итог ---
    if hard_violated > 0:
        feasibility = "unlikely"
    elif checked == 0:
        feasibility = "likely" if not has_workspace else "uncertain"
    elif violations:
        feasibility = "uncertain"
    else:
        feasibility = "likely"

    return {
        "feasibility": feasibility,
        "violations": violations,
        "n_claims": checked,
        "n_violated": hard_violated,
    }
