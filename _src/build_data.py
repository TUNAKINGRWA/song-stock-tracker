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
    # 兜底：部分文章的 <h3> 是材料/分类名，个股写在卡片正文里，改从 stock-card 区块内抓
    if not stocks:
        for card in re.findall(r'<div class="stock-card">(.*?)</div>', html, re.S):
            for m in re.finditer(r'([一-龥A-Za-z0-9]{2,8})\s*[（(]\s*([0-9]{5,6})\.?(SH|SZ|HK|BJ)\s*[）)]', card):
                name, code, ex = m.group(1).strip(), m.group(2), m.group(3)
                if code in seen:
                    continue
                seen.add(code)
                stocks.append({"name": name, "code": code, "ex": ex})
    if stocks:
        title = re.sub(r'_\d{4}-\d{2}-\d{2}$', '', d)
        articles[d] = {"title": title, "date": d[-10:], "stocks": stocks}

# ---------- 2. 文章 -> 行业ETF (有序规则, 先匹配先得) ----------
ETF_RULES = [
    # 2026-09-04 新增 8 条(腾讯接口已验名);传媒须在黄金前——"AI长剧登陆黄金档"含"黄金"
    (["AIGC", "AI长剧", "传媒", "影视"],   "sh512980", "传媒ETF"),
    (["国产算力", "算力链"],              "sz159995", "芯片ETF"),
    (["宠物", "它经济"],                  "sz159825", "农业ETF"),
    (["红利", "高股息", "压舱石"],        "sh510880", "红利ETF"),
    (["黄金股", "金价"],                  "sh517400", "黄金股ETF"),  # 不能用"黄金"——会误抓"黄金赛道/黄金档"
    (["面板", "显示龙头", "OLED"],        "sz159732", "消费电子ETF"),
    (["铀", "核能", "核电", "聚变"],      "sh512400", "有色金属ETF"),
    (["铝"],                             "sh512400", "有色金属ETF"),
    (["隐形材料", "光刻胶", "靶材", "电子布"], "sh512480", "半导体ETF"),
    (["重工", "国产替代", "大国重工"],     "sz159638", "高端装备ETF"),
    (["券商", "证券"],                    "sh512880", "证券ETF"),
    (["信创", "软件", "政务"],            "sh515230", "软件ETF"),
    (["交换机", "组网"],                  "sh515880", "通信ETF"),
    (["焦煤", "煤"],                      "sh515220", "煤炭ETF"),
    (["航空", "航天", "军"],              "sh512660", "军工ETF"),
    (["电网", "电力"],                    "sh561560", "电力ETF"),
    (["化工"],                           "sz159870", "化工ETF"),
    (["医药"],                           "sh512010", "医药ETF"),
    (["游戏", "动漫", "版号"],            "sz159869", "游戏ETF"),
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

# ---------- 2.5 文章原文直链(标题→URL), 用于卡片二维码/看原文 ----------
_HERE = os.path.dirname(os.path.abspath(__file__))
_links = {}
_lf = os.path.join(_HERE, "article_links.json")
if os.path.exists(_lf):
    try:
        _links = json.load(open(_lf, encoding="utf-8"))
    except Exception as e:
        print("⚠️ article_links.json 解析失败:", e)
_linked = 0
for info in articles.values():
    t = info["title"]
    v = _links.get(t)
    if not v:  # 容错: 键是标题子串也算(标题被微调时)
        for k, val in _links.items():
            if k and (k in t or t in k):
                v = val
                break
    if isinstance(v, dict):
        info["url"] = v.get("url"); info["img"] = v.get("img")
    else:
        info["url"] = v or None; info["img"] = None
    if info["url"] or info["img"]:
        _linked += 1
print(f"原文直链: {_linked}/{len(articles)} 篇已配 URL")

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
    for attempt in range(7):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=22, context=CTX).read().decode())["data"][p]
            k = d.get("qfqday") or d.get("day")
            nm = d["qt"][p][1] if d.get("qt", {}).get(p) else ""
            if k:
                return p, [f"{r[0]},{r[2]}" for r in k], nm
        except Exception:
            pass  # 被WAF限流时返回的是HTML, json解析失败→退避重试,熬过限流窗口
        time.sleep(1.5 * (attempt + 1))   # 退避: 1.5/3/4.5/6/7.5/9/10.5s
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
with cf.ThreadPoolExecutor(max_workers=3) as ex:
    for p, kl, nm in ex.map(fetch, alljobs):
        if not kl:
            fails.append(p); continue
        if p in etf_jobs:
            kline_etf[p] = {"name": nm, "klines": kl}
        else:
            code = stk_jobs[p][0]
            kline_stk[code] = {"name": nm, "klines": kl}

HERE = os.path.dirname(os.path.abspath(__file__))
# 优雅降级: 抓失败的标的复用上次旧数据(_src/kline_all.json), 避免限流时整页缺数据
if fails:
    try: old_stk = json.load(open(os.path.join(HERE, "kline_all.json"), encoding="utf-8"))
    except Exception: old_stk = {}
    try: old_etf = json.load(open(os.path.join(HERE, "etf_all.json"), encoding="utf-8"))
    except Exception: old_etf = {}
    reused = 0
    for sid in list(fails):
        if sid in etf_jobs:
            if sid in old_etf: kline_etf[sid] = old_etf[sid]; reused += 1
        else:
            code = stk_jobs[sid][0]
            if code in old_stk: kline_stk[code] = old_stk[code]; reused += 1
    print(f"⚠️ {len(fails)} 只抓取失败(限流?), 复用旧数据 {reused} 只")

# 抓取严重失败(成功<50%)时中止, 保护线上好数据不被空数据覆盖
if len(kline_stk) < len(stk_jobs) * 0.5:
    import sys
    sys.exit(f"❌ 行情抓取严重失败(仅 {len(kline_stk)}/{len(stk_jobs)} 成功), 中止以保护线上数据。请稍后重试。")

# 归档好数据快照(供下次失败时降级复用)
json.dump(kline_stk, open(os.path.join(HERE, "kline_all.json"), "w"), ensure_ascii=False)
json.dump(kline_etf, open(os.path.join(HERE, "etf_all.json"), "w"), ensure_ascii=False)
json.dump(articles, open("/tmp/stocks.json", "w"), ensure_ascii=False)
json.dump(kline_stk, open("/tmp/kline_all.json", "w"), ensure_ascii=False)
json.dump(kline_etf, open("/tmp/etf_all.json", "w"), ensure_ascii=False)
print(f"\n文章{len(articles)} 标的{len(kline_stk)} ETF{len(kline_etf)} 失败{len(fails)} {fails}")
