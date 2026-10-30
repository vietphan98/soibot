import math

import numpy as np
import pandas as pd
import pytest

from soibot.backtest import Rules, simulate, bench_window_return
from soibot.metrics import (Report, daily_curves, evaluate, market_warnings, max_drawdown,
                            sharpe, t_stat, win_rate)
from soibot.signals import load_signals


def frame(closes, start="2025-01-01", spread=0.0):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.array(closes, float)
    return pd.DataFrame({"open": c, "high": c * (1 + spread), "low": c * (1 - spread), "close": c}, index=idx)


def sig(rows):
    df = pd.DataFrame(rows, columns=["symbol", "date", "side", "target", "stop"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_basic_metrics():
    assert win_rate([0.1, -0.1, 0.2, 0.0]) == 0.5
    assert max_drawdown([1, 1.2, 0.9, 1.3]) == pytest.approx(0.9 / 1.2 - 1)
    assert math.isnan(sharpe([0.01]))
    assert sharpe([0.01, 0.02, 0.0]) == pytest.approx(0.01 / 0.01 * math.sqrt(252))
    assert t_stat([0.1, 0.2, 0.3]) == pytest.approx(0.2 / (0.1 / math.sqrt(3)))


def test_hold_exit_and_alpha():
    px = frame([100, 101, 102, 103, 104, 110])
    bench = frame([1000, 1000, 1000, 1010, 1020, 1050])
    t, _ = simulate(sig([["AAA", "2025-01-01", "buy", None, None]]), {"AAA": px}, bench,
                    Rules(hold_days=3, fee=0))
    assert len(t) == 1 and t[0].reason == "hold"
    assert t[0].ret == pytest.approx(0.03)
    assert t[0].bench_ret == pytest.approx(0.01)
    assert t[0].as_dict()["alpha"] == pytest.approx(0.02)


def test_target_stop_and_opposite():
    px = frame([100, 102, 106, 90, 95, 96], spread=0.0)
    bench = frame([1] * 6)
    r = Rules(hold_days=10, fee=0)
    t, _ = simulate(sig([["A", "2025-01-01", "buy", 105, 80]]), {"A": px}, bench, r)
    assert t[0].reason == "target" and t[0].exit_price == 106  # gap qua target -> khớp giá mở
    t, _ = simulate(sig([["A", "2025-01-01", "buy", 200, 91]]), {"A": px}, bench, r)
    assert t[0].reason == "stop" and t[0].exit_price == 90
    t, _ = simulate(sig([["A", "2025-01-01", "buy", None, None], ["A", "2025-01-03", "sell", None, None]]),
                    {"A": px}, bench, r)
    assert t[0].reason == "opposite" and t[0].ret == pytest.approx(0.06)


def test_short_and_fee():
    px = frame([100, 90, 80])
    bench = frame([100, 110, 120])
    t, _ = simulate(sig([["A", "2025-01-01", "sell", None, None]]), {"A": px}, bench,
                    Rules(hold_days=2, allow_short=True, fee=0.01))
    assert t[0].direction == -1
    assert t[0].ret == pytest.approx(0.2 - 0.01)
    assert t[0].bench_ret == pytest.approx(-0.2)
    t, _ = simulate(sig([["A", "2025-01-01", "sell", None, None]]), {"A": px}, bench, Rules())
    assert t == []


def test_bench_window_holiday_uses_last_known():
    b = frame([100, 105, 110])
    assert bench_window_return(b, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-05")) == pytest.approx(0.1)


def _rep(**kw):
    base = dict(n_trades=50, win_rate=0.7, avg_ret=0.02, total_ret=0.3, max_dd=-0.1, sharpe=1.5,
                bench_win_rate=0.68, bench_avg_ret=0.02, bench_total_ret=0.3, bench_max_dd=-0.1,
                bench_sharpe=1.5, index_bh_ret=0.3, alpha_avg=0.0, alpha_total=0.0, alpha_t=0.1,
                alpha_p=0.9, alpha_win_rate=0.5)
    base.update(kw)
    return Report(**base)


def test_warning_lucky_bull_bot():
    w, v = market_warnings(_rep())
    assert w and w[0].startswith("⚠") and "THẮNG NHỜ THỊ TRƯỜNG" in v


def test_no_warning_real_alpha():
    w, v = market_warnings(_rep(win_rate=0.7, bench_win_rate=0.45, alpha_avg=0.02, alpha_t=3.5))
    assert w == [] and v.startswith("CÓ ALPHA đáng")


def test_warning_when_alpha_not_significant_even_if_wr_gap_large():
    w, v = market_warnings(_rep(win_rate=0.8, bench_win_rate=0.5, alpha_avg=0.01, alpha_t=1.2))
    assert w and "ý nghĩa thống kê" in w[0]


def test_low_winrate_no_bull_warning_but_small_sample():
    w, v = market_warnings(_rep(n_trades=5, win_rate=0.4, bench_win_rate=0.6, alpha_avg=-0.01))
    assert len(w) == 1 and "mẫu quá nhỏ" in w[0] and v == "KHÔNG VƯỢT CHỈ SỐ"


def test_evaluate_end_to_end_bull_market():
    # thị trường tăng đều; cổ phiếu y hệt chỉ số -> thắng nhiều nhưng alpha = -phí
    n = 120
    b = frame(list(1000 * 1.003 ** np.arange(n)))
    px = {"A": frame(list(10 * 1.003 ** np.arange(n)))}
    dates = b.index[:100:4]
    s = sig([["A", d, "buy", None, None] for d in dates])
    trades, _ = simulate(s, px, b, Rules(hold_days=3))
    rep = evaluate(trades, daily_curves(trades, px, b, 0.0025))
    assert rep.win_rate == 1.0 and rep.bench_win_rate == 1.0
    assert rep.alpha_avg == pytest.approx(-0.0025)
    assert rep.warnings[0].startswith("⚠")


def test_load_signals(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("Symbol,Date,Side,Target\nfpt,2025-01-02,BUY,120\nhpg,2025-01-01,sell,\n")
    df = load_signals(p)
    assert list(df.symbol) == ["HPG", "FPT"] and df.target.iloc[1] == 120 and math.isnan(df.stop.iloc[0])
    j = tmp_path / "s.json"
    j.write_text('{"signals":[{"symbol":"VCB","date":"2025-01-02","side":"buy"}]}')
    assert len(load_signals(j)) == 1
    bad = tmp_path / "b.csv"
    bad.write_text("symbol,date,side\nA,2025-01-01,hold\n")
    with pytest.raises(ValueError):
        load_signals(bad)
