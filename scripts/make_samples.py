"""Sinh file tín hiệu mẫu (tất định) từ giá thật trong cache/nguồn trực tuyến."""
import random, sys
sys.path.insert(0, '.')
import pandas as pd
from soibot.data import get_prices

SYMS = "ACB BID CTG FPT HPG MBB MSN MWG SSI STB TCB VCB VHM VIC VNM VPB HDB GAS PLX SAB".split()
S, E = "2024-12-01", "2026-01-31"
px = {s: get_prices(s, S, E)[0] for s in SYMS}
idx = get_prices("VNINDEX", S, E)[0]

# 1) Bot "may mắn nhờ sóng tăng": mua ngẫu nhiên mã VN30, 2 tín hiệu/tuần, 05/2025–11/2025
rnd = random.Random(2025)
days = idx.loc["2025-05-01":"2025-11-30"].index
rows = []
for d in days[::3]:
    s = rnd.choice(SYMS)
    c = px[s]["close"].asof(d)
    rows.append(dict(symbol=s, date=d.date(), side="buy", target=round(c * 1.05, 2), stop=round(c * 0.88, 2)))
pd.DataFrame(rows).to_csv("samples/bot_may_man.csv", index=False)

# 2) Bot động lượng tương đối: mỗi 5 phiên, mua 2 mã mạnh nhất so với VN-Index trong 20 phiên,
#    chỉ khi VN-Index nằm trên MA50; 'sell' khi mã rơi khỏi top 5. Không nhìn trước tương lai.
close = pd.DataFrame({s: px[s]["close"] for s in SYMS}).reindex(idx.index).ffill()
rs = close.pct_change(20).sub(idx["close"].pct_change(20), axis=0)
ma50 = idx["close"].rolling(50).mean()
rows, held = [], set()
for d in idx.loc["2025-03-01":"2025-12-31"].index[::5]:
    if idx["close"][d] < ma50[d]:
        for s in held:
            rows.append(dict(symbol=s, date=d.date(), side="sell"))
        held = set(); continue
    rank = rs.loc[d].sort_values(ascending=False)
    top2, top5 = list(rank.index[:2]), set(rank.index[:5])
    for s in list(held):
        if s not in top5:
            rows.append(dict(symbol=s, date=d.date(), side="sell")); held.discard(s)
    for s in top2:
        if s not in held:
            rows.append(dict(symbol=s, date=d.date(), side="buy")); held.add(s)
import json
json.dump({"bot": "dong_luong", "signals": [{**r, "date": str(r["date"])} for r in rows]},
          open("samples/bot_dong_luong.json", "w"), ensure_ascii=False, indent=1)
print(len(pd.read_csv("samples/bot_may_man.csv")), len(rows))
