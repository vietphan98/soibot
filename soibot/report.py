"""Báo cáo terminal và HTML tự chứa (biểu đồ SVG nội tuyến, không cần internet)."""
from __future__ import annotations

import html
import math

import pandas as pd


def pct(x, sign=True):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:+.2%}" if sign else f"{x:.1%}"


def num(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


def rows(rep, bench_name):
    return [
        ("Số lệnh", str(rep.n_trades), "", ""),
        ("Tỷ lệ thắng", pct(rep.win_rate, False), pct(rep.bench_win_rate, False), ""),
        ("Lợi nhuận TB / lệnh", pct(rep.avg_ret), pct(rep.bench_avg_ret), pct(rep.alpha_avg)),
        ("Tổng lợi nhuận (đường vốn)", pct(rep.total_ret), pct(rep.bench_total_ret), pct(rep.alpha_total)),
        ("Sụt giảm tối đa (MDD)", pct(rep.max_dd), pct(rep.bench_max_dd), ""),
        ("Sharpe (năm hoá, rf=0)", num(rep.sharpe), num(rep.bench_sharpe), ""),
    ]


def terminal(rep, meta, trades) -> str:
    b = meta["bench"]
    L = []
    L.append("=" * 72)
    if "GIẢ LẬP" in meta["sources"]:
        L.append(" !!! DỮ LIỆU GIẢ LẬP, không phải giá thật — chỉ để demo !!!")
    L.append(f" SOIBOT — chấm điểm bot: {meta['name']}")
    L.append(f" Giai đoạn: {meta['start']} → {meta['end']} | Benchmark: {b} | Nguồn giá: {meta['sources']}")
    L.append(f" Quy tắc: {meta['rules']}")
    L.append("=" * 72)
    L.append(f"{'Chỉ số':<30}{'Bot':>12}{(' ' + b + ' cùng khung'):>18}{'Alpha':>12}")
    for r in rows(rep, b):
        L.append(f"{r[0]:<30}{r[1]:>12}{r[2]:>18}{r[3]:>12}")
    L.append("-" * 72)
    L.append(f"Alpha mỗi lệnh: t = {num(rep.alpha_t)}, p ≈ {num(rep.alpha_p)}, "
             f"bot thắng chỉ số ở {pct(rep.alpha_win_rate, False)} số lệnh")
    L.append(f"{b} mua & giữ cả giai đoạn: {pct(rep.index_bh_ret)}")
    L.append(f"KẾT LUẬN: {rep.verdict}")
    for w in rep.warnings:
        L.append(w)
    exits = pd.Series([t.reason for t in trades]).value_counts().to_dict() if trades else {}
    L.append(f"Lý do thoát lệnh: {exits}")
    for n in meta.get("notes", [])[:5]:
        L.append(f"  • {n}")
    L.append("Lưu ý: kết quả quá khứ, không phải khuyến nghị đầu tư.")
    return "\n".join(L)


def svg_chart(curves: pd.DataFrame, bench: str, w=760, h=300) -> str:
    pad_l, pad_r, pad_t, pad_b = 56, 16, 30, 34
    series = [("bot", "Bot", "#d6336c"), ("bench", f"{bench} cùng khung", "#1c7ed6"),
              ("index_bh", f"{bench} mua & giữ", "#adb5bd")]
    vals = pd.concat([curves[s] for s, _, _ in series])
    lo, hi = float(vals.min()), float(vals.max())
    if hi - lo < 1e-9:
        hi = lo + 0.01
    n = len(curves)
    X = lambda i: pad_l + (w - pad_l - pad_r) * i / max(n - 1, 1)
    Y = lambda v: pad_t + (h - pad_t - pad_b) * (1 - (v - lo) / (hi - lo))
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'style="width:100%;height:auto;font-family:sans-serif;font-size:11px">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#eee"/>')
        out.append(f'<text x="{pad_l - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="#666">{v - 1:+.0%}</text>')
    if lo < 1 < hi:
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{Y(1):.1f}" y2="{Y(1):.1f}" stroke="#999" stroke-dasharray="3 3"/>')
    idx = curves.index
    for k in range(0, n, max(n // 6, 1)):
        out.append(f'<text x="{X(k):.1f}" y="{h - 12}" text-anchor="middle" fill="#666">{idx[k]:%m/%Y}</text>')
    for s, label, col in reversed(series):
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(curves[s]))
        sw = 2.4 if s == "bot" else 1.8
        out.append(f'<polyline fill="none" stroke="{col}" stroke-width="{sw}" points="{pts}"/>')
    for k, (s, label, col) in enumerate(series):
        out.append(f'<rect x="{pad_l + 10 + k * 190}" y="6" width="12" height="4" fill="{col}"/>'
                   f'<text x="{pad_l + 26 + k * 190}" y="12" fill="#333">{html.escape(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def html_report(rep, meta, trades, curves) -> str:
    b = html.escape(meta["bench"])
    e = html.escape
    warn = "".join(f'<div class="warn">{e(w)}</div>' for w in rep.warnings)
    tbl = "".join(f"<tr><td>{e(a)}</td><td>{e(x)}</td><td>{e(y)}</td><td>{e(z)}</td></tr>"
                  for a, x, y, z in rows(rep, meta["bench"]))
    good = "good" if rep.verdict.startswith("CÓ ALPHA đáng") else ("bad" if rep.warnings and rep.warnings[0].startswith("⚠") else "mid")
    tr = "".join(
        f"<tr><td>{e(t.symbol)}</td><td>{'Mua' if t.direction > 0 else 'Bán'}</td>"
        f"<td>{t.entry_date:%d/%m/%Y}</td><td>{t.exit_date:%d/%m/%Y}</td><td>{e(t.reason)}</td>"
        f"<td>{t.ret:+.2%}</td><td>{t.bench_ret:+.2%}</td><td>{t.ret - t.bench_ret:+.2%}</td></tr>"
        for t in trades[:15])
    more = f"<p class='mut'>… và {len(trades) - 15} lệnh khác.</p>" if len(trades) > 15 else ""
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>soibot — {e(meta['name'])}</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:"Segoe UI",Roboto,"Noto Sans",Arial,sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#212529}}
h1{{font-size:22px;margin:0}} .mut{{color:#868e96;font-size:13px}}
.verdict{{padding:12px 14px;border-radius:8px;font-weight:700;margin:14px 0}}
.good{{background:#d3f9d8;color:#2b8a3e}} .bad{{background:#ffe3e3;color:#c92a2a}} .mid{{background:#fff3bf;color:#8a6d00}}
.fake{{background:#343a40;color:#ffd43b;font-weight:700;text-align:center;padding:8px;border-radius:6px;margin-bottom:12px}}
.warn{{background:#fff5f5;border-left:4px solid #e03131;padding:8px 12px;margin:8px 0;font-size:14px}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}} td,th{{border-bottom:1px solid #eee;padding:5px 8px;text-align:right}}
td:first-child,th:first-child{{text-align:left}} th{{background:#f8f9fa}}
</style></head><body>
{'<div class="fake">DỮ LIỆU GIẢ LẬP, không phải giá thật — chỉ để demo</div>' if 'GIẢ LẬP' in meta['sources'] else ''}
<h1>soibot · Chấm điểm bot “{e(meta['name'])}”</h1>
<p class="mut">{e(meta['start'])} → {e(meta['end'])} · Benchmark: {b} · Nguồn giá: {e(meta['sources'])}<br>Quy tắc: {e(meta['rules'])}</p>
<div class="verdict {good}">Kết luận: {e(rep.verdict)}</div>{warn}
<table><tr><th>Chỉ số</th><th>Bot</th><th>{b} cùng khung</th><th>Alpha</th></tr>{tbl}</table>
<p class="mut">Alpha mỗi lệnh: t = {num(rep.alpha_t)}, p ≈ {num(rep.alpha_p)} · Bot thắng chỉ số ở {pct(rep.alpha_win_rate, False)} số lệnh · {b} mua &amp; giữ cả giai đoạn: {pct(rep.index_bh_ret)}</p>
<h3>Đường vốn: bot so với chỉ số</h3>{svg_chart(curves, meta['bench'])}
<h3>Một số lệnh</h3><table><tr><th>Mã</th><th>Chiều</th><th>Vào</th><th>Ra</th><th>Lý do</th><th>Bot</th><th>{b}</th><th>Alpha</th></tr>{tr}</table>{more}
<p class="mut">Tạo bởi soibot · Kết quả quá khứ không đảm bảo tương lai. Đây không phải khuyến nghị đầu tư.</p>
</body></html>"""


def telegram_text(rep, meta) -> str:
    s = (f"soibot: {meta['name']} ({meta['start']}→{meta['end']})\n"
         f"Lệnh: {rep.n_trades} | Thắng: {pct(rep.win_rate, False)} vs {meta['bench']} {pct(rep.bench_win_rate, False)}\n"
         f"TB/lệnh: {pct(rep.avg_ret)} | Alpha/lệnh: {pct(rep.alpha_avg)} (t={num(rep.alpha_t)})\n"
         f"Tổng: {pct(rep.total_ret)} | MDD: {pct(rep.max_dd)} | Sharpe: {num(rep.sharpe)}\n"
         f"Kết luận: {rep.verdict}")
    if rep.warnings:
        s += "\n" + rep.warnings[0]
    return s
