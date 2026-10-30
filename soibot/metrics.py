"""Chỉ số hiệu quả, alpha so với chỉ số và logic cảnh báo 'thắng nhờ thị trường'."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def win_rate(rets) -> float:
    r = np.asarray(rets, dtype=float)
    return float((r > 0).mean()) if len(r) else float("nan")


def max_drawdown(equity) -> float:
    e = np.asarray(equity, dtype=float)
    if len(e) == 0:
        return 0.0
    peak = np.maximum.accumulate(e)
    return float((e / peak - 1).min())


def sharpe(daily_rets, periods: int = 252) -> float:
    r = np.asarray(daily_rets, dtype=float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods))


def t_stat(x) -> float:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def p_value_from_t(t: float, n: int) -> float:
    """p-value hai phía (xấp xỉ chuẩn; n nhỏ sẽ hơi lạc quan)."""
    if math.isnan(t):
        return float("nan")
    return float(math.erfc(abs(t) / math.sqrt(2)))


def daily_curves(trades, prices: dict, bench: pd.DataFrame, fee: float) -> pd.DataFrame:
    """Đường vốn danh mục chia đều cho các lệnh đang mở mỗi phiên, và đường vốn
    của 'cùng mức phơi nhiễm vào chỉ số' (giữ chỉ số đúng các khoảng thời gian đó)."""
    if not trades:
        return pd.DataFrame(columns=["bot", "bench"])
    cal = bench.index
    bot = {}
    bmk = {}
    bclose = bench["close"]
    for t in trades:
        px = prices[t.symbol]["close"].loc[t.entry_date:t.exit_date].copy()
        px.iloc[-1] = t.exit_price
        r = t.direction * px.pct_change().iloc[1:]
        r.iloc[-1] = (1 + r.iloc[-1]) * (1 - fee) - 1
        br = t.direction * bclose.loc[t.entry_date:t.exit_date].pct_change().iloc[1:]
        for d, v in r.items():
            bot.setdefault(d, []).append(v)
        for d, v in br.items():
            bmk.setdefault(d, []).append(v)
    start = min(t.entry_date for t in trades)
    end = max(t.exit_date for t in trades)
    days = cal[(cal >= start) & (cal <= end)].union(pd.DatetimeIndex(list(bot)))
    df = pd.DataFrame(index=days)
    df["bot_r"] = [np.mean(bot[d]) if d in bot else 0.0 for d in days]
    df["bench_r"] = [np.mean(bmk[d]) if d in bmk else 0.0 for d in days]
    df["bot"] = (1 + df["bot_r"]).cumprod()
    df["bench"] = (1 + df["bench_r"]).cumprod()
    bh = bclose.reindex(days).ffill()
    df["index_bh"] = bh / bh.iloc[0]
    return df


@dataclass
class Report:
    n_trades: int
    win_rate: float
    avg_ret: float
    total_ret: float
    max_dd: float
    sharpe: float
    bench_win_rate: float
    bench_avg_ret: float
    bench_total_ret: float
    bench_max_dd: float
    bench_sharpe: float
    index_bh_ret: float
    alpha_avg: float
    alpha_total: float
    alpha_t: float
    alpha_p: float
    alpha_win_rate: float
    warnings: list = field(default_factory=list)
    verdict: str = ""


def evaluate(trades, curves: pd.DataFrame, high_wr: float = 0.55, wr_gap: float = 0.10,
             min_trades: int = 20, t_crit: float = 2.0) -> Report:
    r = np.array([t.ret for t in trades], dtype=float)
    b = np.array([t.bench_ret for t in trades], dtype=float)
    a = r - b
    n = len(r)
    tot = float(curves["bot"].iloc[-1] - 1) if n else 0.0
    btot = float(curves["bench"].iloc[-1] - 1) if n else 0.0
    t = t_stat(a)
    rep = Report(
        n_trades=n, win_rate=win_rate(r), avg_ret=float(r.mean()) if n else float("nan"),
        total_ret=tot, max_dd=max_drawdown(curves["bot"]) if n else 0.0,
        sharpe=sharpe(curves["bot_r"]) if n else float("nan"),
        bench_win_rate=win_rate(b), bench_avg_ret=float(np.nanmean(b)) if n else float("nan"),
        bench_total_ret=btot, bench_max_dd=max_drawdown(curves["bench"]) if n else 0.0,
        bench_sharpe=sharpe(curves["bench_r"]) if n else float("nan"),
        index_bh_ret=float(curves["index_bh"].iloc[-1] - 1) if n else float("nan"),
        alpha_avg=float(np.nanmean(a)) if n else float("nan"), alpha_total=tot - btot,
        alpha_t=t, alpha_p=p_value_from_t(t, n), alpha_win_rate=win_rate(a),
    )
    rep.warnings, rep.verdict = market_warnings(rep, high_wr, wr_gap, min_trades, t_crit)
    return rep


def market_warnings(rep: Report, high_wr=0.55, wr_gap=0.10, min_trades=20, t_crit=2.0):
    """Trả về (danh sách cảnh báo, kết luận ngắn)."""
    w = []
    if rep.n_trades == 0:
        return ["Không có lệnh nào được mô phỏng."], "KHÔNG ĐÁNH GIÁ ĐƯỢC"
    if rep.n_trades < min_trades:
        w.append(f"Chỉ có {rep.n_trades} lệnh (< {min_trades}): mẫu quá nhỏ, kết quả dễ do may mắn.")
    reasons = []
    if not math.isnan(rep.bench_win_rate) and rep.bench_win_rate >= rep.win_rate - wr_gap:
        reasons.append(f"chỉ số cũng thắng {rep.bench_win_rate:.0%} số khung thời gian giống hệt "
                       f"(bot {rep.win_rate:.0%}; bot không hơn chỉ số quá {wr_gap * 100:.0f} điểm %)")
    if not (rep.alpha_avg > 0):
        reasons.append(f"alpha trung bình mỗi lệnh ≤ 0 ({rep.alpha_avg:+.2%})")
    elif math.isnan(rep.alpha_t) or rep.alpha_t < t_crit:
        reasons.append(f"alpha dương nhưng không có ý nghĩa thống kê (t = {rep.alpha_t:.2f} < {t_crit})")
    if rep.win_rate >= high_wr and reasons:
        w.insert(0, "⚠ CẢNH BÁO: Tỷ lệ thắng cao ({:.0%}) chủ yếu được giải thích bởi thị trường đi lên: "
                 .format(rep.win_rate) + "; ".join(reasons) + ".")
        verdict = "THẮNG NHỜ THỊ TRƯỜNG — chưa chứng minh được kỹ năng"
    elif reasons and rep.alpha_avg <= 0:
        verdict = "KHÔNG VƯỢT CHỈ SỐ"
    elif reasons:
        verdict = "CÓ THỂ CÓ ALPHA — chưa đủ bằng chứng thống kê"
    else:
        verdict = "CÓ ALPHA đáng kể so với chỉ số (trong mẫu đã kiểm tra)"
    return w, verdict
