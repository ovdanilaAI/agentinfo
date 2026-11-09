"""
Признаки. Файловая система считается ОТ workspace (там данные),
а не от папки задачи. Если workspace нет — фичи по FS = 0.
"""
import re
from pathlib import Path
import pandas as pd


_RE_FILE = re.compile(r"\b([\w\-/]+\.(?:csv|json|md|txt|py|yaml|yml|log))\b", re.I)
_RE_MULTI = re.compile(r"\b(first|then|after|next|finally|step)\b", re.I)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def _count_files(path: Path, ext: str | None = None) -> int:
    if not path.exists():
        return 0
    n = 0
    for f in path.rglob("*"):
        if f.is_file() and (ext is None or f.suffix.lower() == ext):
            n += 1
    return n


def _find_in_workspace(ws: Path, name: str) -> Path | None:
    """Ищет файл по имени рекурсивно внутри workspace."""
    direct = ws / name
    if direct.exists():
        return direct
    matches = list(ws.rglob(Path(name).name))
    return matches[0] if matches else None


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    feats: list[dict] = []

    for _, row in df.iterrows():
        instr = str(row.get("instruction", "") or "")
        expected = str(row.get("expected", "") or "")
        ws = Path(row["_workspace"])
        has_ws = bool(row["_has_workspace"])

        # --- текст (всегда) ---
        instr_tokens = len(instr) // 4
        expected_tokens = len(expected) // 4
        mentioned = list(dict.fromkeys(_RE_FILE.findall(instr)))
        n_files_mentioned = len(mentioned)
        has_multi_step = int(bool(_RE_MULTI.search(instr)))

        # --- файловая система (только если workspace есть) ---
        if has_ws and ws.exists():
            # все файлы внутри workspace (включая kb/, если он там)
            ws_files_count = _count_files(ws)
            ws_bytes_total = _dir_size(ws)

            # отдельно kb/ если есть — частый паттерн search-задач
            kb_dir = ws / "kb"
            if kb_dir.is_dir():
                kb_files_count = _count_files(kb_dir)
                kb_bytes_total = _dir_size(kb_dir)
            else:
                kb_files_count = ws_files_count
                kb_bytes_total = ws_bytes_total

            avg_file_bytes = (kb_bytes_total / kb_files_count) if kb_files_count else 0

            # размеры упомянутых в instruction файлов
            ref_bytes = 0
            for name in mentioned:
                p = _find_in_workspace(ws, name)
                if p and p.is_file():
                    ref_bytes += p.stat().st_size
        else:
            # нет workspace — нет файловых признаков
            ws_files_count = 0
            ws_bytes_total = 0
            kb_files_count = 0
            kb_bytes_total = 0
            avg_file_bytes = 0
            ref_bytes = 0

        feats.append({
            "instr_tokens": instr_tokens,
            "expected_tokens": expected_tokens,
            "n_files_mentioned": n_files_mentioned,
            "has_multi_step": has_multi_step,
            "has_workspace": int(has_ws),
            "ws_files_count": ws_files_count,
            "ws_bytes_total": ws_bytes_total,
            "kb_files_count": kb_files_count,
            "kb_bytes_total": kb_bytes_total,
            "avg_file_bytes": avg_file_bytes,
            "ref_files_bytes": ref_bytes,
        })

    return pd.DataFrame(feats, index=df.index)