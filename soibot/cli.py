"""Giao diện dòng lệnh: soibot <file tín hiệu> [tùy chọn]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .backtest import Rules, simulate
from .data import INDEXES, get_prices
from .synthetic import INDEX as GL_INDEX, LABEL as GL_LABEL
from .metrics import daily_curves, evaluate
from .report import html_report, telegram_text, terminal
from .signals import load_signals
from .telegram import send_summary


def build_parser():
    p = argparse.ArgumentParser(prog="soibot", description="Chấm điểm bot tín hiệu chứng khoán bằng backtest và so với chỉ số.")
    p.add_argument("signals", help="file tín hiệu .csv hoặc .json")
    p.add_argument("--bench", default="VNINDEX", help="chỉ số so sánh (VNINDEX, VN30, HNXINDEX, hoặc một mã CP) [VNINDEX]")
    p.add_argument("--hold", type=int, default=10, help="số phiên nắm giữ tối đa [10]")
    p.add_argument("--no-target", action="store_true", help="bỏ qua giá chốt lời")
    p.add_argument("--no-stop", action="store_true", help="bỏ qua giá cắt lỗ")
    p.add_argument("--no-opposite", action="store_true", help="không thoát khi có tín hiệu ngược chiều")
    p.add_argument("--short", action="store_true", help="cho phép 'sell' mở vị thế bán khống")
    p.add_argument("--fee", type=float, default=0.0025, help="phí + thuế khứ hồi mỗi lệnh, tỷ lệ [0.0025]")
    p.add_argument("--source", choices=["auto", "vndirect", "yahoo", "gialap"], default="auto",
                   help="nguồn giá: auto = VNDirect → Yahoo; yahoo = cổ phiếu từ Yahoo, chỉ số từ VNDirect; "
                        "gialap = DỮ LIỆU GIẢ LẬP để demo offline [auto]")
    p.add_argument("--no-cache", action="store_true", help="không dùng cache giá")
    p.add_argument("--html", default=None, help="đường dẫn file HTML báo cáo (mặc định: <tên>_report.html)")
    p.add_argument("--name", default=None, help="tên bot hiển thị")
    p.add_argument("--trades-csv", default=None, help="xuất danh sách lệnh ra CSV")
    p.add_argument("--telegram", action="store_true", help="gửi tóm tắt Telegram (cần TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    p.add_argument("--telegram-dry-run", action="store_true", help="in nội dung Telegram, không gửi")
    p.add_argument("--version", action="version", version=f"soibot {__version__}")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    sig = load_signals(a.signals)
    if sig.empty:
        sys.exit("File tín hiệu rỗng.")
    start = (sig["date"].min() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    end = (sig["date"].max() + pd.Timedelta(days=int(a.hold * 1.6) + 15)).strftime("%Y-%m-%d")
    end = min(end, pd.Timestamp.today().strftime("%Y-%m-%d"))
    srcs = {"auto": ("vndirect", "yahoo"), "vndirect": ("vndirect",),
            "yahoo": ("yahoo",), "gialap": ("gialap",)}[a.source]
    bname = a.bench.upper()
    if a.source == "gialap" and bname == "VNINDEX":
        bname = GL_INDEX  # chỉ số giả lập thay cho VN-Index
    bsrcs = srcs
    if bname in INDEXES and a.source in ("auto", "yahoo"):
        bsrcs = ("vndirect",)  # Yahoo không có lịch sử chỉ số VN -> luôn lấy chỉ số từ VNDirect
    used = {}
    try:
        bench, used[bname] = get_prices(bname, start, end, bsrcs, not a.no_cache)
    except RuntimeError as e:
        sys.exit(f"Lỗi: không tải được chỉ số {bname} ({e}). Yahoo Finance không có lịch sử chỉ số VN, "
                 "nên chỉ số luôn lấy từ VNDirect. Không có mạng? Thử demo với --source gialap.")
    prices = {}
    notes = []
    for s in sig["symbol"].unique():
        try:
            prices[s], used[s] = get_prices(s, start, end, srcs, not a.no_cache)
        except RuntimeError as e:
            notes.append(str(e))
    rules = Rules(hold_days=a.hold, use_target=not a.no_target, use_stop=not a.no_stop,
                  opposite_exit=not a.no_opposite, allow_short=a.short, fee=a.fee)
    trades, n2 = simulate(sig, prices, bench, rules)
    notes += n2
    curves = daily_curves(trades, prices, bench, rules.fee)
    rep = evaluate(trades, curves)
    src_summary = ", ".join(sorted({v.replace(" (cache)", "") for v in used.values()}))
    if "gialap" in src_summary:
        src_summary += f" — {GL_LABEL.upper()}"
    rule_txt = (f"giữ tối đa {rules.hold_days} phiên; target {'bật' if rules.use_target else 'tắt'}; "
                f"stop {'bật' if rules.use_stop else 'tắt'}; tín hiệu ngược {'bật' if rules.opposite_exit else 'tắt'}; "
                f"bán khống {'bật' if rules.allow_short else 'tắt'}; phí khứ hồi {rules.fee:.2%}")
    meta = {"name": a.name or Path(a.signals).stem, "bench": bname, "sources": src_summary,
            "start": str(sig['date'].min().date()), "end": str(curves.index.max().date()) if len(curves) else end,
            "rules": rule_txt, "notes": notes}
    print(terminal(rep, meta, trades))
    if trades:
        out = Path(a.html or f"{Path(a.signals).stem}_report.html")
        out.write_text(html_report(rep, meta, trades, curves), encoding="utf-8")
        print(f"Báo cáo HTML: {out}")
    if a.trades_csv:
        pd.DataFrame([t.as_dict() for t in trades]).to_csv(a.trades_csv, index=False)
    if a.telegram or a.telegram_dry_run:
        print(send_summary(telegram_text(rep, meta), dry_run=a.telegram_dry_run))
    return rep


if __name__ == "__main__":
    main()
