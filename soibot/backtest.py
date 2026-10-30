"""Mô phỏng lệnh theo quy tắc thoát lệnh rõ ràng.

Quy tắc (xem README):
- Vào lệnh tại giá đóng cửa của phiên có tín hiệu (nếu ngày đó nghỉ: phiên kế tiếp).
- buy = mở vị thế mua. sell = đóng vị thế mua đang mở (tín hiệu ngược chiều);
  nếu bật allow_short thì sell không có vị thế mua sẽ mở vị thế bán khống.
- Mỗi phiên sau ngày vào, kiểm tra theo thứ tự: cắt lỗ (stop) -> chốt lời (target)
  -> tín hiệu ngược chiều -> hết số phiên nắm giữ tối đa (thoát ở giá đóng cửa).
  Nếu cùng phiên chạm cả stop và target, giả định chạm stop trước (bảo thủ).
  Nếu giá mở cửa đã vượt qua stop/target thì khớp tại giá mở cửa.
- Lệnh còn mở ở cuối dữ liệu được đóng tại giá đóng cửa cuối cùng (đánh dấu "end").
- Benchmark: cùng ngày vào/ra, lấy % thay đổi giá đóng cửa của chỉ số (đổi dấu nếu bán khống).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class Rules:
    hold_days: int = 10
    use_target: bool = True
    use_stop: bool = True
    opposite_exit: bool = True
    allow_short: bool = False
    fee: float = 0.0025  # tổng phí + thuế khứ hồi (tỷ lệ), trừ vào mỗi lệnh


@dataclass
class Trade:
    symbol: str
    direction: int  # +1 mua, -1 bán khống
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    reason: str
    ret: float = 0.0
    bench_ret: float = 0.0

    def as_dict(self):
        d = asdict(self)
        d["alpha"] = self.ret - self.bench_ret
        return d


def _bar_index(prices: pd.DataFrame, date) -> int | None:
    i = prices.index.searchsorted(pd.Timestamp(date))
    return int(i) if i < len(prices) else None


def simulate(signals: pd.DataFrame, prices: dict[str, pd.DataFrame], bench: pd.DataFrame,
             rules: Rules) -> tuple[list[Trade], list[str]]:
    trades: list[Trade] = []
    notes: list[str] = []
    for sym, sigs in signals.groupby("symbol", sort=False):
        px = prices.get(sym)
        if px is None or px.empty:
            notes.append(f"Bỏ qua {sym}: không có giá")
            continue
        sigs = sigs.sort_values("date")
        sig_dates = {pd.Timestamp(d): s for d, s in zip(sigs["date"], sigs["side"])}
        busy_until = None  # một vị thế mỗi mã tại một thời điểm
        for row in sigs.itertuples():
            if busy_until is not None and row.date <= busy_until:
                continue  # tín hiệu trùng khi đang có vị thế -> dùng làm tín hiệu thoát, không vào thêm
            direction = 1 if row.side == "buy" else (-1 if rules.allow_short else 0)
            if direction == 0:
                continue
            i0 = _bar_index(px, row.date)
            if i0 is None:
                notes.append(f"Bỏ qua {sym} {row.date.date()}: sau ngày dữ liệu cuối")
                continue
            entry = float(px["close"].iloc[i0])
            tgt = _f(row.target) if rules.use_target else np.nan
            stp = _f(row.stop) if rules.use_stop else np.nan
            exit_i, exit_px, reason = None, None, None
            last = min(i0 + rules.hold_days, len(px) - 1)
            for i in range(i0 + 1, last + 1):
                o, h, l, c = px.iloc[i][["open", "high", "low", "close"]]
                if direction == 1:
                    if not np.isnan(stp) and l <= stp:
                        exit_px, reason = (min(o, stp), "stop")
                    elif not np.isnan(tgt) and h >= tgt:
                        exit_px, reason = (max(o, tgt), "target")
                else:
                    if not np.isnan(stp) and h >= stp:
                        exit_px, reason = (max(o, stp), "stop")
                    elif not np.isnan(tgt) and l <= tgt:
                        exit_px, reason = (min(o, tgt), "target")
                if reason is None and rules.opposite_exit:
                    s = sig_dates.get(px.index[i])
                    if s and ((direction == 1 and s == "sell") or (direction == -1 and s == "buy")):
                        exit_px, reason = c, "opposite"
                if reason is None and i == i0 + rules.hold_days:
                    exit_px, reason = c, "hold"
                if reason:
                    exit_i = i
                    break
            if exit_i is None:
                exit_i, exit_px, reason = last, float(px["close"].iloc[last]), "end"
            if exit_i == i0:
                notes.append(f"Bỏ qua {sym} {row.date.date()}: không còn phiên sau ngày vào")
                continue
            t = Trade(sym, direction, px.index[i0], entry, px.index[exit_i], float(exit_px), reason)
            t.ret = direction * (t.exit_price / t.entry_price - 1) - rules.fee
            t.bench_ret = direction * bench_window_return(bench, t.entry_date, t.exit_date)
            trades.append(t)
            busy_until = t.exit_date
    trades.sort(key=lambda t: (t.entry_date, t.symbol))
    return trades, notes


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def bench_window_return(bench: pd.DataFrame, d0, d1) -> float:
    c = bench["close"]
    a = c.loc[:d0]
    b = c.loc[:d1]
    if a.empty or b.empty:
        return float("nan")
    return float(b.iloc[-1] / a.iloc[-1] - 1)
