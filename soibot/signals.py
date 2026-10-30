"""Đọc file tín hiệu CSV/JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REQUIRED = ("symbol", "date", "side")


def load_signals(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("signals", [])
        df = pd.DataFrame(data)
    else:
        df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc: {missing}")
    for c in ("target", "stop"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else float("nan")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["side"] = df["side"].astype(str).str.lower().str.strip()
    bad = ~df["side"].isin(["buy", "sell"])
    if bad.any():
        raise ValueError(f"side phải là buy/sell, sai ở dòng: {list(df.index[bad] + 1)}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)[
        ["symbol", "date", "side", "target", "stop"]]
