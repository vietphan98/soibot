"""Tải giá lịch sử ngày (đã điều chỉnh) từ nguồn miễn phí, có cache cục bộ.

Thứ tự nguồn: VNDirect (finfo API) -> Yahoo Finance (<MÃ>.VN) -> dữ liệu mẫu offline.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (soibot)"}
INDEXES = {"VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPCOMINDEX", "VN100"}
PKG_DIR = Path(__file__).resolve().parent
OFFLINE_DIR = PKG_DIR.parent / "samples" / "offline_prices"


def cache_dir() -> Path:
    d = Path(os.environ.get("SOIBOT_CACHE", Path.home() / ".cache" / "soibot"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vndirect(symbol: str, start: str, end: str) -> pd.DataFrame:
    is_index = symbol in INDEXES
    path = "vnmarket_prices" if is_index else "stock_prices"
    url = f"https://api-finfo.vndirect.com.vn/v4/{path}"
    q = f"code:{symbol}~date:gte:{start}~date:lte:{end}"
    r = requests.get(url, params={"sort": "date", "q": q, "size": 9999}, headers=UA, timeout=20)
    r.raise_for_status()
    rows = r.json().get("data", [])
    if not rows:
        raise ValueError("không có dữ liệu")
    df = pd.DataFrame(rows)
    if is_index:
        out = df[["date", "open", "high", "low", "close"]].copy()
    else:  # dùng giá đã điều chỉnh (cổ tức, chia tách)
        out = df[["date", "adOpen", "adHigh", "adLow", "adClose"]].copy()
        out.columns = ["date", "open", "high", "low", "close"]
    return out


def _yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    ysym = "^VNINDEX.VN" if symbol == "VNINDEX" else f"{symbol}.VN"
    p1 = int(dt.datetime.fromisoformat(start).timestamp())
    p2 = int((dt.datetime.fromisoformat(end) + dt.timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
    r = requests.get(url, params={"period1": p1, "period2": p2, "interval": "1d",
                                  "events": "div,splits"}, headers=UA, timeout=20)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    if "timestamp" not in res:
        raise ValueError("Yahoo không có lịch sử cho mã này")
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    df = pd.DataFrame({"date": pd.to_datetime(res["timestamp"], unit="s") + pd.Timedelta(hours=7),
                       "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
                       "adj": adj}).dropna()
    f = df["adj"] / df["close"]
    for c in ("open", "high", "low"):
        df[c] = df[c] * f
    df["close"] = df["adj"]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[["date", "open", "high", "low", "close"]]


def _offline(symbol: str, start: str, end: str) -> pd.DataFrame:
    f = OFFLINE_DIR / f"{symbol}.csv"
    if not f.exists():
        raise FileNotFoundError(f"không có dữ liệu mẫu offline cho {symbol}")
    return pd.read_csv(f, dtype={"date": str})


SOURCES = {"vndirect": _vndirect, "yahoo": _yahoo, "offline": _offline}


def _clean(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date").sort_values("date").set_index("date")
    df = df[["open", "high", "low", "close"]].astype(float)
    return df.loc[start:end]


def get_prices(symbol: str, start: str, end: str, sources=("vndirect", "yahoo"),
               use_cache: bool = True, log=print) -> tuple[pd.DataFrame, str]:
    """Trả về (DataFrame OHLC theo ngày, tên nguồn)."""
    symbol = symbol.upper().strip()
    errors = []
    for src in sources:
        cf = cache_dir() / f"{src}_{symbol}_{start}_{end}.csv"
        if use_cache and src != "offline" and cf.exists():
            return _clean(pd.read_csv(cf), start, end), f"{src} (cache)"
        try:
            df = SOURCES[src](symbol, start, end)
            if df.empty:
                raise ValueError("rỗng")
            if src != "offline":
                df.to_csv(cf, index=False)
            out = _clean(df, start, end)
            if out.empty:
                raise ValueError("không có dữ liệu trong khoảng ngày")
            return out, src
        except Exception as e:  # thử nguồn kế tiếp
            errors.append(f"{src}: {e}")
    raise RuntimeError(f"Không lấy được giá {symbol}: " + "; ".join(errors))
