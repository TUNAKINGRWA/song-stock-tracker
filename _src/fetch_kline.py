# -*- coding: utf-8 -*-
"""仓库版行情抓取: 读 _src/stocks.json 的标的清单(不扫文章目录),
抓全部标的+ETF前复权日线, 写 /tmp 与脚本目录各一份。
供 GitHub Actions 每日收盘后刷新静态基底; 本地也可直接跑。"""
import os, json, time, datetime, ssl, urllib.request
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

stocks_meta = json.load(open(os.path.join(HERE, "stocks.json"), encoding="utf-8"))

def stk_prefix(code, ex):
    if len(code) == 5: return "hk" + code
    if code[0] == "6": return "sh" + code
    if code[0] in ("0", "3"): return "sz" + code
    return ("sh" if ex == "SH" else "sz") + code

END = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

def fetch(p):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={p},day,2026-04-01,{END},320,qfq")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://gu.qq.com/"})
    for _ in range(5):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=22, context=CTX).read().decode())["data"][p]
            k = d.get("qfqday") or d.get("day")
            nm = d["qt"][p][1] if d.get("qt", {}).get(p) else ""
            if k:
                return p, [f"{r[0]},{r[2]}" for r in k], nm
        except Exception:
            time.sleep(1.0)
    return p, None, None

stk_jobs = {}
for info in stocks_meta.values():
    for s in info["stocks"]:
        stk_jobs[stk_prefix(s["code"], s["ex"])] = (s["code"], s["ex"])
etf_jobs = {info["etf_secid"] for info in stocks_meta.values() if info.get("etf_secid")}

kline_stk, kline_etf, fails = {}, {}, []
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for p, kl, nm in ex.map(fetch, list(stk_jobs) + list(etf_jobs)):
        if not kl:
            fails.append(p); continue
        if p in etf_jobs:
            kline_etf[p] = {"name": nm, "klines": kl}
        else:
            kline_stk[stk_jobs[p][0]] = {"name": nm, "klines": kl}

for d in ("/tmp", HERE):
    json.dump(stocks_meta, open(os.path.join(d, "stocks.json"), "w"), ensure_ascii=False)
    json.dump(kline_stk, open(os.path.join(d, "kline_all.json"), "w"), ensure_ascii=False)
    json.dump(kline_etf, open(os.path.join(d, "etf_all.json"), "w"), ensure_ascii=False)
print(f"标的{len(kline_stk)} ETF{len(kline_etf)} 失败{len(fails)} {fails}")
assert len(fails) <= 3, "失败过多, 放弃本次刷新"
