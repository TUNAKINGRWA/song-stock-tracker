# -*- coding: utf-8 -*-
"""计算: 每只标的 & 每篇对标ETF 自推荐日起累计涨跌幅 + 超额收益。"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    for d in ("/tmp", HERE):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError(name)

stocks_meta = _load("stocks.json")
kline = _load("kline_all.json")     # code -> {name, klines}
etf = _load("etf_all.json")         # secid -> {name, klines}

TODAY = datetime.date.today().isoformat()
# CUTOFF 自动取 A股序列末日的众数(=全市场共同的最后已收盘交易日)。
# 不能用 max: 科创板等品种盘中就返回当日实时bar, max 会把横截面拉歪。
from collections import Counter as _Counter
_last_days = _Counter(v["klines"][-1].split(",")[0]
                      for c, v in kline.items() if len(c) == 6 and v["klines"])
CUTOFF = _last_days.most_common(1)[0][0]
print(f"CUTOFF={CUTOFF} (A股末日分布 {dict(_last_days)})")

THEME_RULES = [
    ("重工", "高端制造"), ("国产替代", "高端制造"),
    ("机器人", "机器人"), ("感知", "机器人"), ("MIM", "机器人"), ("谐波", "机器人"), ("3D视觉", "机器人"),
    ("锂", "新能源"), ("新能源车", "新能源"), ("热管理", "新能源"),
    ("电网", "电力设备"), ("航空", "军工"), ("航天", "军工"), ("商业航天", "军工"),
    ("AI算力", "AI算力"), ("PCB", "AI算力"), ("交换机", "AI算力"), ("互联", "AI算力"),
    ("人工智能", "AI算力"), ("Chiplet", "半导体"), ("封装", "半导体"), ("存储", "半导体"),
    ("功率半导体", "半导体"), ("软件", "软件"), ("信创", "软件"), ("医药", "医药"),
    ("券商", "金融"), ("证券", "金融"),
    ("MLCC", "电子"), ("被动元件", "电子"), ("电容", "电子"),
    ("焦煤", "周期"), ("化工", "周期"), ("金属", "周期"), ("稀缺", "周期"),
]
def theme_of(title):
    for k, v in THEME_RULES:
        if k in title:
            return v
    return "其他"

def parse(klines):
    pts = []
    for ln in klines:
        a = ln.split(",")
        pts.append((a[0], float(a[1])))
    pts.sort()
    return pts

def cum_from(pts, pub_date):
    """基准 = 发布日(含)后第一个交易日收盘; 截止 CUTOFF。返回 (series, base, last_close, base_date)。"""
    base, sub, last = None, [], None
    for d, c in pts:
        if d > CUTOFF:
            continue
        if d >= pub_date:
            if base is None:
                base = c
            sub.append((d, round((c / base - 1) * 100, 2)))
            last = c
    if base is None or not sub:
        return None
    return sub, base, last, sub[0][0]

stk_pts = {code: parse(v["klines"]) for code, v in kline.items()}
etf_pts = {sid: parse(v["klines"]) for sid, v in etf.items()}

articles = []
for folder, info in stocks_meta.items():
    pub = info["date"]
    # ETF 对标
    etf_block = None
    sid = info.get("etf_secid")
    if sid and sid in etf_pts:
        r = cum_from(etf_pts[sid], pub)
        if r:
            sub, base, last, bd = r
            etf_block = {"code": info["etf_code"], "name": info["etf_name"],
                         "api_name": etf.get(sid, {}).get("name", ""),
                         "base_date": bd, "base_close": round(base, 3),
                         "last_close": round(last, 3), "cum": sub[-1][1], "series": sub}
    etf_cum = etf_block["cum"] if etf_block else None

    # 发布日晚于最后收盘 = 今日新推, 尚无交易日(待收盘), 而非真缺失
    pending = pub > CUTOFF
    rows = []
    for s in info["stocks"]:
        code = s["code"]
        ex = "HK" if len(code) == 5 else ("SH" if code[0] == "6" else "SZ")
        miss = {"name": s["name"], "code": code, "ex": ex, "ok": False,
                "status": "pending" if pending else "missing"}
        if code not in stk_pts:
            rows.append(miss)
            continue
        r = cum_from(stk_pts[code], pub)
        if not r:
            rows.append(miss)
            continue
        sub, base, last, bd = r
        cum = sub[-1][1]
        vals = [v for _, v in sub]
        rows.append({
            "name": s["name"], "code": code, "ex": ex, "ok": True,
            "base_date": bd, "base_close": round(base, 2), "last_close": round(last, 2),
            "cum": cum, "max": round(max(vals), 2), "min": round(min(vals), 2),
            "excess": (round(cum - etf_cum, 2) if etf_cum is not None else None),
            "series": sub,
        })

    ok = [r for r in rows if r["ok"]]
    avg = round(sum(r["cum"] for r in ok) / len(ok), 2) if ok else 0
    avg_ex = round(avg - etf_cum, 2) if (ok and etf_cum is not None) else None
    articles.append({
        "title": info["title"], "date": pub, "folder": folder,
        "theme": theme_of(info["title"]), "etf": etf_block,
        "url": info.get("url"), "img": info.get("img"),
        "rows": rows, "avg_cum": avg, "avg_excess": avg_ex,
    })

articles.sort(key=lambda a: a["date"], reverse=True)

all_ok = [r for a in articles for r in a["rows"] if r["ok"]]
all_ex = [r for r in all_ok if r["excess"] is not None]
n_stocks = len(all_ok)
avg_cum = round(sum(r["cum"] for r in all_ok) / n_stocks, 2)
win = sum(1 for r in all_ok if r["cum"] > 0)
beat = sum(1 for r in all_ex if r["excess"] > 0)
avg_excess = round(sum(r["excess"] for r in all_ex) / len(all_ex), 2)
best = max(all_ok, key=lambda r: r["cum"])
worst = min(all_ok, key=lambda r: r["cum"])
best_ex = max(all_ex, key=lambda r: r["excess"])

ash_last = max((r["series"][-1][0] for r in all_ok if len(r["code"]) == 6), default=CUTOFF)

stats = {"n_articles": len(articles), "n_stocks": n_stocks, "avg_cum": avg_cum,
         "win": win, "win_rate": round(win / n_stocks * 100, 1),
         "beat": beat, "beat_rate": round(beat / len(all_ex) * 100, 1),
         "avg_excess": avg_excess, "n_etf": len({a["etf"]["code"] for a in articles if a["etf"]}),
         "best": {"name": best["name"], "cum": best["cum"]},
         "worst": {"name": worst["name"], "cum": worst["cum"]},
         "best_ex": {"name": best_ex["name"], "ex": best_ex["excess"]},
         "today": TODAY, "ash_last": ash_last}

print(f"文章{stats['n_articles']} 标的{n_stocks} 平均{avg_cum}% 胜率{stats['win_rate']}%")
print(f"跑赢对标ETF {beat}/{len(all_ex)} ({stats['beat_rate']}%) 平均超额{avg_excess}%")
print(f"最佳 {best['name']} {best['cum']}% | 超额王 {best_ex['name']} {best_ex['excess']}%")
json.dump({"articles": articles, "stats": stats}, open("/tmp/tracking_data.json", "w"), ensure_ascii=False)
print("已保存 tracking_data.json")
