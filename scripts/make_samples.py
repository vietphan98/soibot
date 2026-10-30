"""Sinh 2 file tín hiệu mẫu (tất định) trên DỮ LIỆU GIẢ LẬP (soibot/synthetic.py), không phải giá thật.

Chạy: python scripts/make_samples.py
"""
import json, random, sys
sys.path.insert(0, '.')
import pandas as pd
from soibot.synthetic import INDEX, SYMBOLS, universe

u = {k: v.assign(date=pd.to_datetime(v["date"])).set_index("date") for k, v in universe().items()}
idx = u[INDEX]

# 1) Bot "may mắn nhờ sóng tăng": mua ngẫu nhiên, 2 tín hiệu/tuần, chốt lời +10%, cắt lỗ -15%
rnd = random.Random(2025)
rows = []
for d in idx.loc["2025-05-01":"2025-11-30"].index[::3]:
    s = rnd.choice(SYMBOLS)
    c = u[s]["close"].asof(d)
    rows.append(dict(symbol=s, date=d.date(), side="buy", target=round(c * 1.10, 2), stop=round(c * 0.85, 2)))
pd.DataFrame(rows).to_csv("samples/bot_may_man.csv", index=False)

# 2) Bot động lượng: mỗi 5 phiên mua 2 mã mạnh nhất so với chỉ số trong 20 phiên; 'sell' khi rơi khỏi top 4.
close = pd.DataFrame({s: u[s]["close"] for s in SYMBOLS})
rs = close.pct_change(20).sub(idx["close"].pct_change(20), axis=0)
rows, held = [], set()
for d in idx.loc["2025-02-01":"2025-12-31"].index[::5]:
    rank = rs.loc[d].sort_values(ascending=False)
    top2, top4 = list(rank.index[:2]), set(rank.index[:4])
    for s in sorted(held - top4):
        rows.append(dict(symbol=s, date=str(d.date()), side="sell")); held.discard(s)
    for s in top2:
        if s not in held:
            rows.append(dict(symbol=s, date=str(d.date()), side="buy")); held.add(s)
json.dump({"bot": "dong_luong", "data": "DỮ LIỆU GIẢ LẬP", "signals": rows},
          open("samples/bot_dong_luong.json", "w"), ensure_ascii=False, indent=1)
