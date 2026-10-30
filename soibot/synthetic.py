"""DỮ LIỆU GIẢ LẬP, không phải giá thật.

Sinh giá ngày tất định (seed cố định) cho một chỉ số giả `GLINDEX` và 12 mã giả `GL01`…`GL12`
để chạy demo khi không có mạng. Chỉ số giả có xu hướng tăng (mô phỏng "sóng tăng");
mỗi mã = beta × chỉ số + nhiễu riêng + một xu hướng riêng đổi chế độ chậm (để động lượng có ý nghĩa).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

INDEX = "GLINDEX"
SYMBOLS = [f"GL{i:02d}" for i in range(1, 13)]
LABEL = "DỮ LIỆU GIẢ LẬP, không phải giá thật"


@lru_cache(maxsize=1)
def universe(seed: int = 2026) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-12-02", "2026-01-30")
    n = len(days)
    idx_r = rng.normal(0.0016, 0.009, n)  # thị trường giả tăng ~ +40%/năm
    out = {INDEX: _ohlc(1000 * np.cumprod(1 + idx_r), days, rng)}
    for s in SYMBOLS:
        beta = rng.uniform(0.8, 1.3)
        drift = np.zeros(n)
        d = 0.0
        for i in range(n):  # xu hướng riêng đổi chế độ, duy trì vài tuần
            if i % 30 == 0:
                d = rng.normal(0, 0.003)
            drift[i] = d
        r = beta * idx_r + drift + rng.normal(0, 0.012, n)
        out[s] = _ohlc(rng.uniform(15, 80) * np.cumprod(1 + r), days, rng)
    return out


def _ohlc(close, days, rng):
    prev = np.r_[close[0], close[:-1]]
    op = prev * (1 + rng.normal(0, 0.003, len(close)))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.006, len(close))))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.006, len(close))))
    return pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "open": op, "high": hi,
                         "low": lo, "close": close}).round(3)


def prices(symbol: str) -> pd.DataFrame:
    u = universe()
    if symbol not in u:
        raise KeyError(f"không có mã giả lập {symbol} (chỉ có {INDEX}, {SYMBOLS[0]}…{SYMBOLS[-1]})")
    return u[symbol]
