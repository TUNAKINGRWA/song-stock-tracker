# -*- coding: utf-8 -*-
"""重建数据: 抽取文章标的 + 映射行业ETF + 抓取全部日线。"""
import os, re, glob, json, time, datetime, urllib.request, ssl
import concurrent.futures as cf

BASE = "/Users/apple/Desktop/CURSOR/松松"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
skip_kw = ["复盘", "私享会", "基金", "私人知识库", "cloud", ".claude", "标的跟踪"]

# ---------- 1. 抽取标的 ----------
articles = {}
for d in sorted(os.listdir(BASE)):
    full = os.path.join(BASE, d)
    if not os.path.isdir(full) or any(k in d for k in skip_kw):
        continue
    htmls = glob.glob(os.path.join(full, "*.html"))
    if not htmls:
        continue
    html = open(htmls[0], encoding="utf-8").read()
    stocks, seen = [], set()
    for m in re.finditer(r'<h3>\s*(?:\d+\.\s*)?([^（(<]+?)\s*[（(]\s*([0-9]{5,6})\.?(SH|SZ|HK|BJ)?\s*[）)]', html):
        name, code, ex = m.group(1).strip(), m.group(2), (m.group(3) or "")
        if code in seen:
            continue
        seen.add(code)
        stocks.append({"name": name, "code": code, "ex": ex})
    if stocks:
        title = re.sub(r'_\d{4}-\d{2}-\d{2}$', '', d)
        articles[d] = {"title": title, "date": d[-10:], "stocks": stocks}

# ---------- 2. 文章 -> 行业ETF (有序规则, 先匹配先得) ----------
ETF_RULES = [
    (["重工", "国产替代", "大国重工"],     "sz159638", "高端装备ETF"),
    (["券商", "证券"],                    "sh512880", "证券ETF"),
    (["信创", "软件", "政务"],            "sh515230", "软件ETF"),
    (["交换机", "组网"],                  "sh515880", "通信ETF"),
    (["焦煤", "煤"],                      "sh515220", "煤炭ETF"),
    (["航空", "航天", "军"],              "sh512660", "军工ETF"),
    (["电网", "电力"],                    "sh561560", "电力ETF"),
    (["化工"],                           "sz159870", "化工ETF"),
    (["医药"],                           "sh512010", "医药ETF"),
    (["金属", "稀缺", "稀有"],            "sh512400", "有色金属ETF"),
    (["锂"],                             "sz159755", "电池ETF"),
    (["新能源车"],                       "sh515030", "新能源车ETF"),
    (["PCB", "MLCC", "被动元件", "电容"], "sh515260", "电子ETF"),
    (["Chiplet", "封装", "功率半导体", "存储", "芯片级", "互联", "半导体"], "sh512480", "半导体ETF"),
    (["人工智能"],                       "sz159819", "人工智能ETF"),
    (["机器人", "感知", "MIM", "粉末冶金", "3D视觉"], "sh562500", "机器人ETF"),
]
def map_etf(title):
    for kws, code, name in ETF_RULES:
        if any(k in title for k in kws):
            return code, name
    return None, None

for d, info in articles.items():
    code, name = map_etf(info["title"])
    info["etf_secid"] = code      # 形如 sh515230
    info["etf_code"] = code[2:] if code else None
    info["etf_name"] = name
    print(f"{info['title'][:22]:24} -> {name}({info['etf_code']})")

_unmapped = [i["title"] for i in articles.values() if not i["etf_secid"]]
if _unmapped:
    print("\n" + "!" * 50)
    print(f"⚠️  {len(_unmapped)} 篇文章未匹配到对标ETF —— 超额(α)将缺失！")
    print("   请在 ETF_RULES 加「关键词→行业ETF」规则(代码先用腾讯接口验名)：")
    for t in _unmapped:
        print("   -", t)
    print("!" * 50 + "\n")

# ---------- 3. 抓取 (标的 + ETF) ----------
def stk_prefix(code, ex):
    # 信代码前缀, 不信文章后缀(可能笔误, 如 000400 被写成 .SH)
    if len(code) == 5: return "hk" + code
    if code[0] == "6": return "sh" + code
    if code[0] in ("0", "3"): return "sz" + code
    return ("sh" if ex == "SH" else "sz") + code

END = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
def fetch(p):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={p},day,2026-04-01,{END},300,qfq")
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

# 待抓集合
stk_jobs = {}   # secid -> (code, ex)
for info in articles.values():
    for s in info["stocks"]:
        sid = stk_prefix(s["code"], s["ex"])
        stk_jobs[sid] = (s["code"], s["ex"])
etf_jobs = {info["etf_secid"] for info in articles.values() if info["etf_secid"]}

kline_stk, kline_etf, fails = {}, {}, []
alljobs = list(stk_jobs.keys()) + list(etf_jobs)
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for p, kl, nm in ex.map(fetch, alljobs):
        if not kl:
            fails.append(p); continue
        if p in etf_jobs:
            kline_etf[p] = {"name": nm, "klines": kl}
        else:
            code = stk_jobs[p][0]
            kline_stk[code] = {"name": nm, "klines": kl}

json.dump(articles, open("/tmp/stocks.json", "w"), ensure_ascii=False)
json.dump(kline_stk, open("/tmp/kline_all.json", "w"), ensure_ascii=False)
json.dump(kline_etf, open("/tmp/etf_all.json", "w"), ensure_ascii=False)
print(f"\n文章{len(articles)} 标的{len(kline_stk)} ETF{len(kline_etf)} 失败{len(fails)} {fails}")
