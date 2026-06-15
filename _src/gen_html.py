# -*- coding: utf-8 -*-
"""热点先锋·标的跟踪看板 生成器 v2
读 tracking_data.json → 输出 /tmp/tracking.html
v2: 洞察卡 / 走势图双模式(绝对·超额) / 双口径排行 / 主题聚合 / 涨跌分布 /
    明细筛选·排序·搜索 / 锚点导航 / 批注反馈系统(兼容旧反馈链接)
"""
import json, html, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
def load(name):
    for d in ("/tmp", HERE):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError(name)

D = load("tracking_data.json")
articles = D["articles"]
st = D["stats"]
PAGE_UPDATE = st.get("today", "")

THEME_COLORS = {
    "机器人": "#7c3aed", "新能源": "#0891b2", "电力设备": "#2563eb",
    "军工": "#475569", "AI算力": "#2c5aa0", "半导体": "#c2410c",
    "软件": "#0d9488", "医药": "#be123c", "周期": "#a16207",
    "高端制造": "#0e7490", "金融": "#0369a1", "电子": "#a21caf", "其他": "#64748b",
}

def esc(s):
    return html.escape(str(s))

def pct(v):
    return f"{v:+.2f}%"

def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")

def sparkline(series, w=120, h=34, force=None):
    vals = [v for _, v in series]
    if len(vals) < 2:
        return '<span class="nodata">—</span>'
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    n = len(vals)
    X = lambda i: i / (n - 1) * (w - 4) + 2
    Y = lambda v: h - 3 - (v - lo) / (hi - lo) * (h - 6)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    last = vals[-1]
    color = force or ("#d9342b" if last > 0 else ("#15883e" if last < 0 else "#888"))
    zero = ""
    if lo <= 0 <= hi:
        zy = Y(0)
        zero = (f'<line x1="2" y1="{zy:.1f}" x2="{w-2}" y2="{zy:.1f}" '
                f'stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2.5,2.5"/>')
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'preserveAspectRatio="none">{zero}'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{X(n-1):.1f}" cy="{Y(last):.1f}" r="1.9" fill="{color}"/></svg>')

# ============ 头部标签：仅指定文章 ============
HEAD_BADGES = [
    (("焦煤",), "红利", "dv"),
    (("商业航天", "大国重工", "航空主机厂", "建军百年"), "主线", "ml"),
]
def head_badge_for(title):
    for kws, label, kind in HEAD_BADGES:
        if any(k in title for k in kws):
            return f'<span class="head-badge badge-{kind}">{label}</span>'
    return ""

# ============ 衍生数据 ============
flat = [{**r, "article": a["title"], "theme": a["theme"], "date": a["date"]}
        for a in articles for r in a["rows"] if r["ok"]]
rank_abs = sorted(flat, key=lambda r: r["cum"], reverse=True)
exc_flat = [r for r in flat if r.get("excess") is not None]
rank_exc = sorted(exc_flat, key=lambda r: r["excess"], reverse=True)
max_abs = max(abs(rank_abs[0]["cum"]), abs(rank_abs[-1]["cum"]), 1)
max_exc = max(abs(rank_exc[0]["excess"]), abs(rank_exc[-1]["excess"]), 1) if rank_exc else 1

# 主题聚合
th_map = defaultdict(lambda: {"rows": [], "arts": set()})
for a in articles:
    for r in a["rows"]:
        if r["ok"]:
            th_map[a["theme"]]["rows"].append(r)
            th_map[a["theme"]]["arts"].add(a["title"])
theme_stats = []
for name, v in th_map.items():
    rows = v["rows"]
    exs = [r["excess"] for r in rows if r.get("excess") is not None]
    theme_stats.append({
        "name": name, "n": len(rows), "na": len(v["arts"]),
        "cum": round(sum(r["cum"] for r in rows) / len(rows), 2),
        "exc": round(sum(exs) / len(exs), 2) if exs else None,
    })
theme_stats.sort(key=lambda t: (t["exc"] if t["exc"] is not None else -999), reverse=True)

# 洞察
elig = [a for a in articles if a.get("avg_excess") is not None
        and sum(1 for r in a["rows"] if r["ok"]) >= 2]
best_a = max(elig, key=lambda a: a["avg_excess"])
worst_a = min(elig, key=lambda a: a["avg_excess"])
best_t = next((t for t in theme_stats if t["exc"] is not None and t["n"] >= 3), theme_stats[0])

# ============ KPI ============
kpi_html = f"""
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">跟踪文章</div><div class="kpi-val">{st['n_articles']}<span class="u">篇</span></div></div>
  <div class="kpi"><div class="kpi-label">跟踪标的</div><div class="kpi-val">{st['n_stocks']}<span class="u">只</span></div></div>
  <div class="kpi"><div class="kpi-label">对标行业ETF</div><div class="kpi-val">{st['n_etf']}<span class="u">只</span></div></div>
  <div class="kpi"><div class="kpi-label">平均累计涨跌幅</div><div class="kpi-val {cls(st['avg_cum'])}" id="kvAvg">{pct(st['avg_cum'])}</div></div>
  <div class="kpi"><div class="kpi-label">上涨标的占比</div><div class="kpi-val" id="kvWin">{st['win_rate']}<span class="u">%</span> <span class="kpi-sub">{st['win']}/{st['n_stocks']}</span></div></div>
  <div class="kpi hl"><div class="kpi-label">跑赢对标ETF占比</div><div class="kpi-val {cls(st['beat_rate']-50)}" id="kvBeat">{st['beat_rate']}<span class="u">%</span> <span class="kpi-sub">{st['beat']}/{st['n_stocks']}</span></div></div>
  <div class="kpi hl"><div class="kpi-label">平均超额收益</div><div class="kpi-val {cls(st['avg_excess'])}" id="kvExc">{pct(st['avg_excess'])}</div></div>
  <div class="kpi"><div class="kpi-label">超额王 · α最高</div><div class="kpi-val up sm" id="kvKing">{esc(st['best_ex']['name'])}<br><span class="b">{pct(st['best_ex']['ex'])}</span></div></div>
</div>"""

# ============ 洞察卡 ============
s_avg = f'<b class="{cls(st["avg_excess"])}">{pct(st["avg_excess"])}</b>'
s_best = f'<b class="{cls(best_a["avg_excess"])}">{pct(best_a["avg_excess"])}</b>'
s_worst = f'<b class="{cls(worst_a["avg_excess"])}">{pct(worst_a["avg_excess"])}</b>'
s_bt = f'<b class="{cls(best_t["exc"])}">{pct(best_t["exc"])}</b>' if best_t["exc"] is not None else "—"
king = st["best_ex"]
ins_cards = [
    ("💡", "整体选股α为正",
     f"{st['n_stocks']}只标的平均跑赢对标行业ETF {s_avg}，{st['beat_rate']}% 的标的强于行业基准——板块普跌中选股相对抗跌"),
    ("🏆", "最强一篇",
     f"《{esc(best_a['title'])}》篇均超额 {s_best}（发布 {best_a['date']}）"),
    ("⚠️", "最弱一篇",
     f"《{esc(worst_a['title'])}》篇均超额 {s_worst}（发布 {worst_a['date']}）"),
    ("👑", "双指标领跑",
     f"{esc(king['name'])} 超额 <b class=\"up\">{pct(king['ex'])}</b>；最强主题：{esc(best_t['name'])}（{best_t['n']}只平均超额 {s_bt}）"),
]
INS_KEYS = ["alpha", "best", "worst", "king"]
ins_html = '<div class="ins-grid">' + "".join(
    f'<div class="ins-card" data-ins="{k}"><div class="ins-i">{i}</div><div class="ins-bd">'
    f'<div class="ins-t">{t}</div><div class="ins-d">{d}</div></div></div>'
    for k, (i, t, d) in zip(INS_KEYS, ins_cards)) + '</div>'

# ============ 排行（双口径） ============
def bars(items, val_key, sub_key, maxabs):
    out = []
    for r in items:
        v = r[val_key]
        w = abs(v) / maxabs * 100 if maxabs else 0
        c = cls(v)
        sub = ""
        sv = r.get(sub_key)
        if sv is not None:
            prefix = "α" if sub_key == "excess" else ""
            sub = f'<span class="bar-ex {cls(sv)}">{prefix}{pct(sv)}</span>'
        out.append(
            f'<div class="bar-row"><div class="bar-name" title="{esc(r["article"])}">{esc(r["name"])}'
            f'<span class="bar-code">{r["code"]}</span></div>'
            f'<div class="bar-track"><div class="bar-fill {c}" style="width:{w:.1f}%"></div></div>'
            f'<div class="bar-val {c}">{pct(v)}{sub}</div></div>')
    return "".join(out)

rank_abs_html = (f'<div class="rank-wrap"><div class="rank-col"><h3>📈 涨幅榜 Top 8</h3>'
                 f'{bars(rank_abs[:8], "cum", "excess", max_abs)}</div>'
                 f'<div class="rank-col"><h3>📉 跌幅榜 Top 8</h3>'
                 f'{bars(rank_abs[-8:][::-1], "cum", "excess", max_abs)}</div></div>')
rank_exc_html = (f'<div class="rank-wrap"><div class="rank-col"><h3>🚀 超额榜 Top 8</h3>'
                 f'{bars(rank_exc[:8], "excess", "cum", max_exc)}</div>'
                 f'<div class="rank-col"><h3>🪨 落后榜 Top 8</h3>'
                 f'{bars(rank_exc[-8:][::-1], "excess", "cum", max_exc)}</div></div>')

# ============ 主题聚合 ============
tmax = max((abs(t["exc"]) for t in theme_stats if t["exc"] is not None), default=1) or 1
tc_cards = []
for t in theme_stats:
    color = THEME_COLORS.get(t["name"], "#64748b")
    cum_c = cls(t["cum"])
    if t["exc"] is not None:
        exc_c = cls(t["exc"])
        exc_txt = pct(t["exc"])
        barw = abs(t["exc"]) / tmax * 100
        bar = f'<div class="tc-bar"><i class="{exc_c}" style="width:{barw:.0f}%"></i></div>'
    else:
        exc_c, exc_txt, bar = "flat", "—", ""
    tc_cards.append(
        f'<div class="theme-card"><div class="tc-head"><span class="tc-dot" style="background:{color}"></span>'
        f'<span class="tc-name">{esc(t["name"])}</span><span class="tc-n">{t["na"]}篇·{t["n"]}只</span></div>'
        f'<div class="tc-rows"><div>平均涨跌 <b class="{cum_c}">{pct(t["cum"])}</b></div>'
        f'<div>平均超额 <b class="{exc_c}">{exc_txt}</b></div></div>{bar}</div>')
themes_html = '<div class="theme-grid" id="themeGrid">' + "".join(tc_cards) + '</div>'

# ============ 涨跌分布直方图 ============
vals = [r["cum"] for r in flat]
edges = [(-10**9, -20), (-20, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 20), (20, 10**9)]
labels = ["≤-20", "-20~-10", "-10~-5", "-5~0", "0~5", "5~10", "10~20", ">20"]
counts = [sum(1 for v in vals if lo <= v < hi) for lo, hi in edges]
maxc = max(counts) or 1
W, Hh = 640, 176
slot = (W - 24) / 8
hist_parts = []
for i, c in enumerate(counts):
    bw = slot * 0.6
    cx = 12 + slot * i + slot / 2
    hpx = 0 if c == 0 else max(4, c / maxc * 104)
    y = Hh - 34 - hpx
    col = "#15883e" if edges[i][1] <= 0 else "#d9342b"
    hist_parts.append(f'<rect x="{cx-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hpx:.1f}" rx="4" fill="{col}" opacity="0.82"/>')
    hist_parts.append(f'<text x="{cx:.1f}" y="{y-6:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="#475569">{c}</text>')
    hist_parts.append(f'<text x="{cx:.1f}" y="{Hh-16:.1f}" text-anchor="middle" font-size="10" fill="#8a97a8">{labels[i]}</text>')
hist_svg = (f'<svg viewBox="0 0 {W} {Hh}" width="100%" style="max-width:680px;display:block;margin:0 auto">'
            + "".join(hist_parts)
            + f'<line x1="8" y1="{Hh-32}" x2="{W-8}" y2="{Hh-32}" stroke="#dde4ee"/></svg>')
hist_html = (f'<div class="hist-card card"><div class="hist-t">全部 {len(vals)} 只标的累计涨跌幅分布（%）</div>{hist_svg}</div>')

# ============ 主题筛选 chips ============
tcnt = Counter(a["theme"] for a in articles)
chips = [f'<button class="chip-f on" data-t="全部">全部 <i>{len(articles)}</i></button>']
for t, c in sorted(tcnt.items(), key=lambda x: -x[1]):
    chips.append(f'<button class="chip-f" data-t="{esc(t)}">{esc(t)} <i>{c}</i></button>')
chips_html = "".join(chips)

# ============ 分文章明细 ============
arts_html = []
for a in articles:
    tc = THEME_COLORS.get(a["theme"], "#64748b")
    etf = a["etf"]
    hb = head_badge_for(a["title"])
    art_pending = bool(a["rows"]) and all(not r["ok"] for r in a["rows"]) \
        and any(r.get("status") == "pending" for r in a["rows"])
    if art_pending:
        avg_html = '<span class="art-avg dim">📅 今日新推 · 待首个交易日</span>'
        avg_ex_html = ""
    else:
        avg_html = f'<span class="art-avg {cls(a["avg_cum"])}">篇均 {pct(a["avg_cum"])}</span>'
        avg_ex_html = (f'<span class="art-ex {cls(a["avg_excess"])}">篇均超额 {pct(a["avg_excess"])}</span>'
                       if a.get("avg_excess") is not None else "")
    link_html = (f'<button class="art-link" data-url="{esc(a["url"])}" data-title="{esc(a["title"])}">📄 看原文</button>'
                 if a.get("url") else "")
    search_blob = (a["title"] + " " + " ".join(r["name"] + r["code"] for r in a["rows"])).lower()
    trs = []
    for r in a["rows"]:
        if not r["ok"]:
            if r.get("status") == "pending":
                # 今日新推, 尚无交易日; 给完整结构 + data-code, 收盘后实时引擎自动填
                rsearch = esc((r["name"] + r["code"]).lower())
                trs.append(f"""<tr class="pending" data-search="{rsearch}" data-code="{r['code']}">
          <td class="tname">{esc(r['name'])}</td>
          <td class="mono">{r['code']}.{r['ex']}</td>
          <td class="mono dim">{a['date'][5:]}</td>
          <td class="mono dim">—</td>
          <td class="mono dim">—</td>
          <td class="cum dim">待收盘</td>
          <td class="dim">—</td>
          <td class="sp dim">—</td>
        </tr>""")
            else:
                trs.append(f'<tr class="miss"><td class="tname">{esc(r["name"])}</td>'
                           f'<td class="mono">{r["code"]}</td><td colspan="6">数据缺失（停牌/未匹配）</td></tr>')
            continue
        rsearch = esc((r["name"] + r["code"]).lower())
        exc_td = (f'<td class="exc {cls(r["excess"])}">{pct(r["excess"])}</td>'
                  if r.get("excess") is not None else '<td class="dim">—</td>')
        trs.append(f"""<tr data-search="{rsearch}" data-code="{r['code']}">
          <td class="tname">{esc(r['name'])}</td>
          <td class="mono">{r['code']}.{r['ex']}</td>
          <td class="mono dim">{r['base_date'][5:]}</td>
          <td class="mono">{r['base_close']}</td>
          <td class="mono">{r['last_close']}</td>
          <td class="cum {cls(r['cum'])}">{pct(r['cum'])}</td>
          {exc_td}
          <td class="sp">{sparkline(r['series'])}</td>
        </tr>""")
    bench_tr = ""
    if etf:
        bench_tr = f"""<tr class="bench-row" data-search="{esc((etf['name']+etf['code']).lower())}" data-code="{etf['code']}">
          <td class="tname">📊 对标 · {esc(etf['name'])}</td>
          <td class="mono">{etf['code']}</td>
          <td class="mono dim">{etf['base_date'][5:]}</td>
          <td class="mono">{etf['base_close']}</td>
          <td class="mono">{etf['last_close']}</td>
          <td class="cum {cls(etf['cum'])}">{pct(etf['cum'])}</td>
          <td class="dim sm2">行业基准</td>
          <td class="sp">{sparkline(etf['series'], force='#1d4ed8')}</td>
        </tr>"""
    avgex_attr = a["avg_excess"] if a.get("avg_excess") is not None else ""
    arts_html.append(f"""
    <div class="art-card" data-theme="{esc(a['theme'])}" data-date="{a['date']}" data-avgcum="{a['avg_cum']}" data-avgex="{avgex_attr}" data-search="{esc(search_blob)}">
      <div class="art-head">
        <div class="art-title-wrap">
          <span class="theme-tag" style="background:{tc}1a;color:{tc};border-color:{tc}40">{esc(a['theme'])}</span>
          <span class="art-title">{esc(a['title'])}</span>
          {hb}
        </div>
        <div class="art-meta">
          <span class="art-date">发布 {a['date']}</span>
          {avg_html}
          {avg_ex_html}
          {link_html}
        </div>
      </div>
      <div class="tbl-wrap"><table class="stock-tbl">
        <thead><tr>
          <th>标的</th><th>代码</th><th>推荐日</th><th>推荐价</th><th>现价</th>
          <th>累计涨跌</th><th>超额<span class="th-sub">vs行业ETF</span></th><th>走势</th>
        </tr></thead>
        <tbody>{''.join(trs)}{bench_tr}</tbody>
      </table></div>
    </div>""")

# ============ ECharts 数据 + 实时引擎配置(CFG) ============
def secid_of(code):
    if len(code) == 5:
        return "hk" + code
    if code[0] == "6" or code[0] == "5":
        return "sh" + code
    return "sz" + code

chart_articles = []
for a in articles:
    series = []
    for r in a["rows"]:
        if r["ok"]:
            series.append({"name": r["name"], "code": r["code"], "secid": secid_of(r["code"]),
                           "scum": r["cum"], "sexc": r.get("excess"),
                           "data": [[d, v] for d, v in r["series"]]})
        elif r.get("status") == "pending":
            # 今日新推: 进 DATA 但无静态数据, 待收盘后实时引擎补算
            series.append({"name": r["name"], "code": r["code"], "secid": secid_of(r["code"]),
                           "scum": None, "sexc": None, "data": []})
    if not series:
        continue
    obj = {"title": a["title"], "date": a["date"], "theme": a["theme"], "series": series}
    if a["etf"]:
        obj["etf"] = {"name": a["etf"]["name"], "code": a["etf"]["code"],
                      "secid": secid_of(a["etf"]["code"]), "scum": a["etf"]["cum"],
                      "data": [[d, v] for d, v in a["etf"]["series"]]}
    chart_articles.append(obj)
chart_json = json.dumps(chart_articles, ensure_ascii=False)

# ============ 模板 ============
TEMPLATE = """<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>热点先锋 · 标的跟踪看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js"></script>
<style>
:root{--blue:#2c5aa0;--blue-d:#1e3f73;--up:#d9342b;--down:#15883e;--bench:#1d4ed8;
--bg:#f3f6fa;--card:#fff;--ink:#16243a;--dim:#5b6b81;--line:#e3e9f1;
--sh1:0 1px 2px rgba(16,40,80,.06);--sh2:0 10px 28px -14px rgba(16,40,80,.16)}
*{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}
html{scroll-behavior:smooth}
body{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}
.up{color:var(--up)!important}.down{color:var(--down)!important}.flat{color:#64748b!important}
header{background:linear-gradient(118deg,#1d3e72,#2c5aa0 52%,#3f70ba);color:#fff;padding:30px 32px 24px;position:relative;overflow:hidden}
header::after{content:"";position:absolute;inset:0;background:repeating-linear-gradient(115deg,rgba(255,255,255,.04) 0 2px,transparent 2px 56px);pointer-events:none}
header .wrap{max-width:1180px;margin:0 auto;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px;position:relative}
header h1{font-size:24px;font-weight:760;letter-spacing:.5px}
header h1 .dot{color:#9fc1f0}
header .sub{font-size:12.5px;color:#cfe0f7;margin-top:6px}
header .legend{font-size:12px;color:#dce8f8;display:flex;gap:15px;align-items:center;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:5px}
.chip i{width:10px;height:10px;border-radius:2px;display:inline-block}
.chip .dash{width:16px;height:0;border-top:2px dashed #8fb4ff}
.hnav{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.88);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hnav .wrap{max-width:1180px;margin:0 auto;display:flex;gap:4px;padding:8px 24px;overflow-x:auto}
.hnav a{padding:6px 13px;border-radius:8px;font-size:13px;font-weight:600;color:#42526b;text-decoration:none;white-space:nowrap}
.hnav a:hover{background:#eef2f8;color:var(--blue-d)}
main{max-width:1180px;margin:0 auto;padding:24px 24px 40px}
section{margin-bottom:32px;scroll-margin-top:64px}
.sec-title{font-size:16px;font-weight:740;color:var(--blue);margin:0 0 14px;padding-left:11px;border-left:4px solid var(--blue);line-height:1.25}
.sec-title small{font-weight:500;color:var(--dim);font-size:12.5px;margin-left:8px}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px 17px;box-shadow:var(--sh1);transition:transform .15s,box-shadow .15s}
.kpi:hover{transform:translateY(-1px);box-shadow:var(--sh2)}
.kpi.hl{background:linear-gradient(180deg,#fbfdff,#eef5ff);border-color:#b9d2f0}
.kpi-label{font-size:12px;color:var(--dim);margin-bottom:7px}
.kpi-val{font-size:25px;font-weight:780;letter-spacing:-.5px;font-variant-numeric:tabular-nums}
.kpi-val .u{font-size:14px;font-weight:500;color:var(--dim);margin-left:2px}
.kpi-val.sm{font-size:14px;font-weight:700;line-height:1.35}
.kpi-val .b{font-size:18px}
.kpi-sub{font-size:12px;color:var(--dim);font-weight:500}
.ins-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:14px}
.ins-card{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px 16px;box-shadow:var(--sh1)}
.ins-i{font-size:21px;line-height:1.2;flex-shrink:0;filter:saturate(1.1)}
.ins-t{font-size:13px;font-weight:740;color:var(--blue-d);margin-bottom:3px}
.ins-d{font-size:12.8px;color:#3c4d66;line-height:1.62}
.ins-d b{font-weight:760}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;box-shadow:var(--sh1)}
.chart-controls{display:flex;gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.chart-controls label{font-size:13px;color:var(--dim)}
select,input[type=search]{font-family:inherit;font-size:13.5px;padding:7px 12px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;color:var(--ink)}
select{cursor:pointer;min-width:240px}
#mainChart{width:100%;height:440px}
.seg{display:inline-flex;background:#eaeff6;border-radius:10px;padding:3px;gap:2px}
.seg button{border:none;background:transparent;padding:6px 14px;border-radius:8px;font-family:inherit;font-size:12.5px;font-weight:650;color:#5b6b81;cursor:pointer;white-space:nowrap}
.seg button.on{background:#fff;color:var(--blue-d);box-shadow:0 1px 3px rgba(16,40,80,.18)}
.seg button.off{opacity:.38;cursor:not-allowed}
.rank-wrap{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.rank-col h3{font-size:14px;margin-bottom:12px}
.bar-row{display:grid;grid-template-columns:128px 1fr 132px;align-items:center;gap:10px;margin-bottom:8px}
.bar-name{font-size:13px;font-weight:620;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-code{font-size:11px;color:var(--dim);margin-left:6px;font-weight:400}
.bar-track{background:#edf1f7;border-radius:5px;height:16px;overflow:hidden}
.bar-fill{height:100%;border-radius:5px}
.bar-fill.up{background:linear-gradient(90deg,#f0938b,#d9342b)}
.bar-fill.down{background:linear-gradient(90deg,#74c697,#15883e)}
.bar-val{font-size:13px;font-weight:720;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bar-ex{font-size:10.5px;font-weight:620;margin-left:5px;opacity:.85}
.theme-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(196px,1fr));gap:13px}
.theme-card{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 15px;box-shadow:var(--sh1)}
.tc-head{display:flex;align-items:center;gap:7px;margin-bottom:8px}
.tc-dot{width:9px;height:9px;border-radius:3px;flex-shrink:0}
.tc-name{font-size:13.5px;font-weight:720}
.tc-n{font-size:11px;color:var(--dim);margin-left:auto;white-space:nowrap}
.tc-rows{font-size:12.3px;color:var(--dim);display:flex;flex-direction:column;gap:3px}
.tc-rows b{font-weight:740;font-variant-numeric:tabular-nums;float:right}
.tc-bar{height:5px;background:#edf1f7;border-radius:3px;margin-top:9px;overflow:hidden}
.tc-bar i{display:block;height:100%;border-radius:3px}
.tc-bar i.up{background:var(--up)}.tc-bar i.down{background:var(--down)}.tc-bar i.flat{background:#94a3b8}
.hist-card{margin-top:14px}
.hist-t{font-size:13px;font-weight:700;color:#3c4d66;margin-bottom:6px;text-align:center}
.detail-tools{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px;background:var(--card);border:1px solid var(--line);border-radius:13px;padding:12px 16px;box-shadow:var(--sh1)}
.chips{display:flex;gap:7px;flex-wrap:wrap;flex:1;min-width:240px}
.chip-f{font-family:inherit;border:1px solid #d6deea;background:#fff;border-radius:18px;padding:4.5px 12px;font-size:12.4px;font-weight:600;color:#42526b;cursor:pointer;white-space:nowrap}
.chip-f i{font-style:normal;font-size:10.5px;opacity:.65;margin-left:2px}
.chip-f:hover{border-color:#9fb4d2}
.chip-f.on{background:var(--blue);color:#fff;border-color:var(--blue)}
.dt-right{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.dt-right select{min-width:170px}
.dt-right input{width:172px}
.art-card{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:16px;overflow:hidden;box-shadow:var(--sh1)}
.art-head{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;padding:14px 20px;background:linear-gradient(0deg,#fafbfd,#fff);border-bottom:1px solid var(--line)}
.art-title-wrap{display:flex;align-items:center;gap:10px;min-width:0}
.theme-tag{font-size:11.5px;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid;white-space:nowrap}
.head-badge{display:inline-flex;align-items:center;gap:3px;font-size:11.5px;font-weight:800;color:#fff;padding:3px 12px;border-radius:20px;letter-spacing:1.5px;white-space:nowrap;flex-shrink:0}
.badge-ml{background:linear-gradient(135deg,#fb923c,#ea580c);box-shadow:0 2px 6px rgba(234,88,12,.42)}
.badge-ml::before{content:"\\2605";font-size:10px;margin-top:-1px}
.badge-dv{background:linear-gradient(135deg,#e11d48,#9f1239);box-shadow:0 2px 6px rgba(159,18,57,.4)}
.art-title{font-size:15.5px;font-weight:720;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.art-link{font-family:inherit;font-size:12px;font-weight:600;color:#2c5aa0;background:#eef4fc;border:1px solid #c9ddf5;border-radius:16px;padding:4px 12px;cursor:pointer;white-space:nowrap;transition:.15s}
.art-link:hover{background:#2c5aa0;color:#fff;border-color:#2c5aa0}
.qr-mask{display:none;position:fixed;inset:0;background:rgba(15,30,60,.55);z-index:1100;align-items:center;justify-content:center;padding:20px}
.qr-box{background:#fff;border-radius:16px;padding:22px 24px 18px;max-width:340px;width:100%;text-align:center;box-shadow:0 18px 50px rgba(10,30,70,.3)}
.qr-title{font-size:14.5px;font-weight:700;color:#1e293b;line-height:1.45;margin-bottom:14px}
.qr-svg{width:216px;height:216px;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;border:1px solid #eef1f5;border-radius:10px;padding:8px}
.qr-svg svg{width:100%;height:100%;display:block}
.qr-tip{font-size:11.5px;color:#94a3b8;margin-bottom:12px}
.qr-url{font-size:11px;color:#64748b;word-break:break-all;background:#f6f8fb;border-radius:7px;padding:7px 9px;margin-bottom:12px;font-family:ui-monospace,Menlo,monospace}
.qr-btns{display:flex;gap:8px}
.qr-btns button,.qr-btns a{flex:1;font-family:inherit;font-size:12.5px;font-weight:600;padding:9px 6px;border-radius:8px;border:1px solid #cbd5e1;background:#fff;color:#475569;cursor:pointer;text-decoration:none;text-align:center}
.qr-btns .qr-open{background:#2c5aa0;color:#fff;border-color:#2c5aa0}
.qr-btns .qr-copy:hover,.qr-btns button:hover{border-color:#94a3b8}
.art-meta{display:flex;align-items:center;gap:13px;font-size:12.5px;white-space:nowrap}
.art-date{color:var(--dim)}.art-avg{font-weight:700}
.art-ex{font-weight:700;padding:2px 9px;border-radius:6px;background:#f1f5fb;font-size:12px}
.tbl-wrap{overflow-x:auto}
.stock-tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.stock-tbl th{background:#f7f9fc;color:#5a6b85;font-weight:600;font-size:12px;text-align:right;padding:9px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
.stock-tbl th:first-child{text-align:left}
.th-sub{display:block;font-size:10px;color:#9fb0c8;font-weight:400}
.stock-tbl td{padding:10px 14px;border-bottom:1px solid #f1f4f8;text-align:right;vertical-align:middle}
.stock-tbl tbody tr:hover{background:#f8fafd}
.stock-tbl tbody tr.hitrow{background:#fff8e6}
.tname{text-align:left!important;font-weight:620;white-space:nowrap}
.mono{font-variant-numeric:tabular-nums;font-family:"SF Mono",ui-monospace,Menlo,monospace;font-size:12.5px}
.dim{color:var(--dim)}.sm2{font-size:11px}
.cum{font-weight:760;font-size:14px;font-variant-numeric:tabular-nums}
.exc{font-weight:700;font-size:13px;font-variant-numeric:tabular-nums}
.sp{width:130px;text-align:center!important}.spark{display:block;margin:0 auto}
.nodata{color:#cbd5e1}.miss td{color:#94a3b8;font-style:italic;text-align:left}
.pending td{color:#a3aec0}.pending .tname{color:#475569;font-weight:600}.pending .cum{font-weight:600;color:#b0892b}.pending:hover{background:#fffdf5}
.bench-row{background:#eff5ff}.bench-row td{border-top:1.5px solid #cdddf5;border-bottom:none}
.bench-row .tname{color:var(--bench)}
footer{max-width:1180px;margin:0 auto;padding:0 24px 50px;color:var(--dim);font-size:12px;line-height:1.9}
footer .disc{background:#fff;border:1px solid var(--line);border-radius:13px;padding:16px 20px}
footer b{color:#475569}
@media print{header::after{display:none}.hnav,.detail-tools{display:none!important}.card,.art-card,.kpi,.ins-card,.theme-card{box-shadow:none;break-inside:avoid}section{margin-bottom:16px}#mainChart{height:380px}body{background:#fff}.kpi-grid{grid-template-columns:repeat(4,1fr)!important;gap:10px}.kpi-val{font-size:21px}.seg{display:none}}
@media(max-width:920px){.kpi-grid,.ins-grid{grid-template-columns:repeat(2,1fr)}.rank-wrap{grid-template-columns:1fr}select{min-width:170px}}
@media(max-width:640px){.kpi-grid{grid-template-columns:repeat(2,1fr)}.ins-grid{grid-template-columns:1fr}.art-title{max-width:150px}.bar-row{grid-template-columns:106px 1fr 116px}
/* 明细表窄屏:隐藏推荐日/推荐价/现价三列,保留 标的·代码·累计涨跌·超额·走势,铺满不横滚 */
.tbl-wrap{overflow-x:visible}.stock-tbl{min-width:0;width:100%}
.stock-tbl th,.stock-tbl td{padding:9px 5px}
.stock-tbl th:nth-child(3),.stock-tbl td:nth-child(3),.stock-tbl th:nth-child(4),.stock-tbl td:nth-child(4),.stock-tbl th:nth-child(5),.stock-tbl td:nth-child(5){display:none}
.th-sub{display:none}.sp{width:88px}.spark{width:88px;height:30px}.cum,.exc{font-size:12.5px}.tname{font-size:13px}.mono{font-size:11px}}
__ANNOCSS__
</style></head>
<body>
<header><div class="wrap">
  <div>
    <h1>热点先锋<span class="dot"> · </span>标的跟踪看板</h1>
    <div class="sub">每篇文章推荐标的 · 自推荐日起累计涨跌幅 + 对标行业ETF超额收益 · 静态基底截至 __ASHLAST__ 收盘（前复权 · 数据源：腾讯财经）</div>
    <div class="sub" id="liveStat" style="margin-top:4px;font-weight:600;color:#ffe2b8">⏳ 正在拉取实时行情…</div>
  </div>
  <div class="legend">
    <span class="chip"><i style="background:#ff6b61"></i>红=上涨</span>
    <span class="chip"><i style="background:#37b46f"></i>绿=下跌</span>
    <span class="chip"><span class="dash"></span>蓝虚线=对标ETF</span>
  </div>
</div></header>
<nav class="hnav"><div class="wrap">
  <a href="#sec-ov">总览</a><a href="#sec-chart">走势</a><a href="#sec-rank">排行</a><a href="#sec-theme">主题</a><a href="#sec-detail">明细</a>
</div></nav>
<main>
  <section id="sec-ov">__KPI____INS__</section>
  <section id="sec-chart">
    <h2 class="sec-title">累计涨跌幅走势 <small>「超额模式」展示个股相对对标行业ETF的逐日α</small></h2>
    <div class="card">
      <div class="chart-controls">
        <label>选择文章：</label><select id="artSel"></select>
        <span class="seg"><button id="mAbs" class="on">绝对收益</button><button id="mExc">超额 vs 行业ETF</button></span>
        <span id="chartHint" style="font-size:12px;color:#94a3b8"></span>
      </div>
      <div id="mainChart"></div>
    </div>
  </section>
  <section id="sec-rank">
    <h2 class="sec-title">区间排行 <small>可切换「绝对涨跌」与「超额α」两套口径</small></h2>
    <div class="card">
      <div style="margin-bottom:14px"><span class="seg"><button id="rkA" class="on">按累计涨跌</button><button id="rkE">按超额α</button></span></div>
      <div id="rankAbsBlk">__RANKABS__</div>
      <div id="rankExcBlk" style="display:none">__RANKEXC__</div>
    </div>
  </section>
  <section id="sec-theme">
    <h2 class="sec-title">主题表现 <small>按平均超额降序 · 下方为全部标的涨跌分布</small></h2>
    __THEMES__
    __HIST__
  </section>
  <section id="sec-detail">
    <h2 class="sec-title">分文章明细 <small>每篇末行为对标行业ETF基准 · 支持筛选 / 排序 / 搜索</small></h2>
    <div class="detail-tools">
      <div class="chips" id="themeChips">__CHIPS__</div>
      <div class="dt-right">
        <select id="sortSel">
          <option value="new">排序：最新发布</option>
          <option value="exc">排序：篇均超额 高→低</option>
          <option value="cum">排序：篇均涨跌 高→低</option>
          <option value="old">排序：最早发布</option>
        </select>
        <input type="search" id="sQ" placeholder="搜标的名 / 代码">
      </div>
    </div>
    <div id="artList">__ARTS__</div>
  </section>
</main>
<footer><div class="disc">
  <b>口径说明：</b>累计涨跌幅 = 以文章发布日（或其后第一个交易日）收盘价为基准，至 __ASHLAST__ 收盘的前复权累计涨跌（统一截止到最后一个全市场已收盘交易日）。<b>超额收益（α）</b> = 标的累计涨跌幅 − 同期同起点的对标行业ETF累计涨跌幅，&gt;0 表示跑赢行业；走势图「超额模式」展示逐日α曲线（0% 即行业基准）。每篇对标的行业ETF按文章主题就近选取（见各表末"对标"行），仅作行业基准参考。<br>
  <b>数据来源：</b>腾讯财经 / 东方财富（行情）。标的、推荐日取自本工作目录各文章 HTML 成稿；个别证券现用简称可能变更（如 300919 行情端现示"中伟新材"），看板沿用文章原名；000400 许继电气为深市（文章后缀笔误已校正）。<br>
  <b>风险提示：</b>本看板仅为历史业绩跟踪，不构成任何投资建议；历史表现不代表未来收益，市场有风险，投资需谨慎。
</div></footer>
<script>
var DATA=__CHART__;
var chart=echarts.init(document.getElementById('mainChart'),null,{renderer:'svg'});
var PAL=['#2c5aa0','#d9342b','#0891b2','#7c3aed','#c2410c','#15883e','#be123c','#a16207'];
var mode='abs',cur=0;
function render(){
  var a=DATA[cur];
  var em=null;
  if(a.etf){em={};a.etf.data.forEach(function(p){em[p[0]]=p[1];});}
  var useExc=(mode==='exc'&&em);
  var mE=document.getElementById('mExc');
  mE.classList.toggle('off',!em);
  var hint='共 '+a.series.length+' 只 · 发布 '+a.date;
  if(a.etf)hint+=useExc?(' · 超额 = 个股 − '+a.etf.name):(' · 对标 '+a.etf.name+'('+a.etf.code+')');
  else hint+=' · 该篇无对标ETF';
  document.getElementById('chartHint').textContent=hint;
  var series=a.series.map(function(s,i){
    var d=useExc? s.data.filter(function(p){return em[p[0]]!==undefined;}).map(function(p){return [p[0],+(p[1]-em[p[0]]).toFixed(2)];}) : s.data;
    var o={name:s.name+'('+s.code+')',type:'line',showSymbol:false,smooth:true,lineStyle:{width:2},emphasis:{focus:'series',lineStyle:{width:3.5}},data:d,color:PAL[i%PAL.length]};
    if(i===0){o.markLine={silent:true,symbol:'none',lineStyle:{color:'#94a3b8',type:'dashed',width:1},label:{formatter:useExc?'行业基准':'0%',fontSize:10,color:'#94a3b8',position:'end'},data:[{yAxis:0}]};}
    return o;});
  if(!useExc&&a.etf){series.push({name:'对标·'+a.etf.name+'('+a.etf.code+')',type:'line',showSymbol:false,smooth:true,z:10,data:a.etf.data,color:'#1d4ed8',lineStyle:{width:3,type:'dashed'},emphasis:{focus:'series',lineStyle:{width:4}}});}
  chart.setOption({animation:false,
    tooltip:{trigger:'axis',valueFormatter:function(v){return (v>0?'+':'')+v+'%';},textStyle:{fontSize:12},axisPointer:{type:'cross'}},
    legend:{type:'scroll',top:0,textStyle:{fontSize:11},itemWidth:18,itemHeight:8},
    grid:{left:48,right:30,top:42,bottom:34},
    xAxis:{type:'time',axisLabel:{fontSize:11,color:'#94a3b8',formatter:'{M}/{d}'},axisLine:{lineStyle:{color:'#e2e8f0'}},splitLine:{show:false}},
    yAxis:{type:'value',axisLabel:{fontSize:11,color:'#94a3b8',formatter:'{value}%'},splitLine:{lineStyle:{color:'#eef2f7'}},
      axisPointer:{label:{formatter:function(p){return (p.value>0?'+':'')+p.value.toFixed(1)+'%';}}}},
    series:series},true);
}
var sel=document.getElementById('artSel');
DATA.forEach(function(a,i){var o=document.createElement('option');o.value=i;o.text=a.title+'（'+a.date+'）';sel.appendChild(o);});
sel.addEventListener('change',function(){cur=+this.value;render();});
document.getElementById('mAbs').onclick=function(){mode='abs';this.classList.add('on');document.getElementById('mExc').classList.remove('on');render();};
document.getElementById('mExc').onclick=function(){if(this.classList.contains('off'))return;mode='exc';this.classList.add('on');document.getElementById('mAbs').classList.remove('on');render();};
var rich=0,mx=0;DATA.forEach(function(a,i){var n=a.series.reduce(function(s,x){return s+x.data.length;},0);if(n>mx){mx=n;rich=i;}});
cur=rich;sel.value=rich;render();
window.addEventListener('resize',function(){chart.resize();});
document.getElementById('rkA').onclick=function(){this.classList.add('on');document.getElementById('rkE').classList.remove('on');document.getElementById('rankAbsBlk').style.display='';document.getElementById('rankExcBlk').style.display='none';if(window.__annoPins)window.__annoPins();};
document.getElementById('rkE').onclick=function(){this.classList.add('on');document.getElementById('rkA').classList.remove('on');document.getElementById('rankAbsBlk').style.display='none';document.getElementById('rankExcBlk').style.display='';if(window.__annoPins)window.__annoPins();};
(function(){
  var list=document.getElementById('artList');
  var cards=[].slice.call(list.querySelectorAll('.art-card'));
  var orig=cards.slice();
  var themeF='全部',q='';
  function refreshPins(){if(window.__annoPins)window.__annoPins();}
  function apply(){
    var ql=q.trim().toLowerCase();
    cards.forEach(function(c){
      var okT=(themeF==='全部'||c.dataset.theme===themeF);
      var okQ=!ql||(c.dataset.search||'').indexOf(ql)>=0;
      c.style.display=(okT&&okQ)?'':'none';
      var trs=c.querySelectorAll('tbody tr');
      for(var i=0;i<trs.length;i++){var tr=trs[i];tr.classList.toggle('hitrow',!!ql&&(tr.dataset.search||'').indexOf(ql)>=0);}
    });
    refreshPins();
  }
  document.getElementById('themeChips').addEventListener('click',function(e){
    var b=e.target.closest('.chip-f');if(!b)return;
    themeF=b.dataset.t;
    var all=this.querySelectorAll('.chip-f');
    for(var i=0;i<all.length;i++)all[i].classList.toggle('on',all[i]===b);
    apply();
  });
  document.getElementById('sQ').addEventListener('input',function(){q=this.value;apply();});
  document.getElementById('sortSel').addEventListener('change',function(){
    var v=this.value,arr=cards.slice();
    function num(c,k){var x=parseFloat(c.dataset[k]);return isNaN(x)?-999:x;}
    if(v==='new')arr=orig.slice();
    else if(v==='old')arr=orig.slice().reverse();
    else if(v==='exc')arr.sort(function(a,b){return num(b,'avgex')-num(a,'avgex');});
    else if(v==='cum')arr.sort(function(a,b){return num(b,'avgcum')-num(a,'avgcum');});
    for(var i=0;i<arr.length;i++)list.appendChild(arr[i]);
    refreshPins();
  });
})();
/* ================= 实时行情引擎 =================
   打开页面时: JSONP拉全部标的+ETF前复权日K + qt实时报价续点,
   浏览器端按同一口径重算全部指标并刷新 DOM。失败自动降级为静态数据。 */
(function(){
  var statEl=document.getElementById('liveStat');
  function setStat(t,tone){if(!statEl)return;statEl.textContent=t;statEl.style.color=tone==='ok'?'#b9f2c8':(tone==='warn'?'#ffd9c2':'#ffe2b8');}
  function fpct(v){return (v>0?'+':'')+v.toFixed(2)+'%';}
  function fcls(v){return v>0?'up':(v<0?'down':'flat');}
  function r2(v){return Math.round(v*100)/100;}
  function escH(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}
  function loadScript(src,cs){return new Promise(function(res,rej){var s=document.createElement('script');if(cs)s.charset=cs;s.src=src;var t=setTimeout(function(){s.remove();rej('timeout');},15000);s.onload=function(){clearTimeout(t);s.remove();res();};s.onerror=function(){clearTimeout(t);s.remove();rej('err');};document.head.appendChild(s);});}
  function sparkJS(series,force){
    var vals=series.map(function(p){return p[1];});
    if(vals.length<2)return '<span class="nodata">—</span>';
    var w=120,h=34,lo=Math.min.apply(null,vals),hi=Math.max.apply(null,vals);
    if(hi===lo)hi=lo+1;var n=vals.length;
    function X(i){return i/(n-1)*(w-4)+2;}function Y(v){return h-3-(v-lo)/(hi-lo)*(h-6);}
    var pts=vals.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}).join(' ');
    var last=vals[n-1];var color=force||(last>0?'#d9342b':(last<0?'#15883e':'#888'));
    var zero='';if(lo<=0&&0<=hi){var zy=Y(0).toFixed(1);zero='<line x1="2" y1="'+zy+'" x2="'+(w-2)+'" y2="'+zy+'" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2.5,2.5"/>';}
    return '<svg class="spark" viewBox="0 0 '+w+' '+h+'" width="'+w+'" height="'+h+'" preserveAspectRatio="none">'+zero+'<polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="'+X(n-1).toFixed(1)+'" cy="'+Y(last).toFixed(1)+'" r="1.9" fill="'+color+'"/></svg>';
  }
  function parseQt(sid){
    var v=window['v_'+sid];if(!v)return null;var f=String(v).split('~');if(f.length<33)return null;
    var pct=parseFloat(f[32]);var dr=f[30]||'';
    var m=dr.match(/(20\\d{2})[\\/\\-]?(\\d{2})[\\/\\-]?(\\d{2})/);if(!m||isNaN(pct))return null;
    var tm=dr.match(/(\\d{2}):?(\\d{2}):?\\d{2}\\s*$/);
    return {date:m[1]+'-'+m[2]+'-'+m[3],pct:pct,time:tm?(tm[1]+':'+tm[2]):''};
  }
  function cumSeries(kl,pub,cutoff){
    var base=null,out=[],last=null;
    for(var i=0;i<kl.length;i++){var d=kl[i][0],c=kl[i][1];
      if(cutoff&&d>cutoff)continue;
      if(d>=pub){if(base===null)base=c;out.push([d,r2((c/base-1)*100)]);last=c;}}
    return base===null?null:{base:base,out:out,last:last};
  }
  try{
    var sidSet={};
    DATA.forEach(function(a){a.series.forEach(function(s){sidSet[s.secid]=1;});if(a.etf)sidSet[a.etf.secid]=1;});
    var sids=Object.keys(sidSet);
    var dt=new Date();dt.setDate(dt.getDate()+1);
    var endDay=dt.toISOString().slice(0,10);
    var klMap={},qtTime='';
    // 并发池:限制同时在飞的请求数, 避免一次性 100+ 请求把同域连接打满 / 触发腾讯WAF限流
    function runPool(items,limit,worker){return new Promise(function(resolve){
      var idx=0,active=0,done=0,n=items.length;if(!n)return resolve();
      function next(){while(active<limit&&idx<n){active++;
        Promise.resolve(worker(items[idx++])).catch(function(){}).then(function(){
          active--;done++;if(done===n)resolve();else next();});}}
      next();});}
    function fetchKline(sid){
      var vn='kl_'+sid.replace(/\\W/g,'');
      return loadScript('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var='+vn+'&param='+sid+',day,2026-04-01,'+endDay+',320,qfq&r='+Math.random()).then(function(){
        try{var dd=window[vn]&&window[vn].data&&window[vn].data[sid];var k=dd&&(dd.qfqday||dd.day);
          if(k&&k.length)klMap[sid]=k.map(function(r){return [r[0],parseFloat(r[2])];});
        }catch(e){}
        try{delete window[vn];}catch(e){window[vn]=undefined;}
      }).catch(function(){});
    }
    var qtJobs=[];
    for(var i=0;i<sids.length;i+=50){
      (function(ch){qtJobs.push(loadScript('https://qt.gtimg.cn/q='+ch.join(',')+'&r='+Math.random(),'GBK').catch(function(){}));})(sids.slice(i,i+50));
    }
    Promise.all([runPool(sids,8,fetchKline)].concat(qtJobs)).then(function(){
      // 实时续点
      var qtToday='';
      sids.forEach(function(sid){
        var kl=klMap[sid];if(!kl||!kl.length)return;
        var q=parseQt(sid);if(!q)return;
        var lastD=kl[kl.length-1][0];
        if(q.date>lastD){kl.push([q.date,r2(kl[kl.length-1][1]*(1+q.pct/100))]);}
        if(q.date>qtToday){qtToday=q.date;qtTime=q.time;}
      });
      var okN=Object.keys(klMap).length;
      if(okN<sids.length*0.5){setStat('⚠ 实时行情拉取失败，当前为静态数据（基底截至页面生成日）','warn');return;}
      // 端侧 CUTOFF = A股序列末日众数
      var dayCnt={};
      Object.keys(klMap).forEach(function(sid){if(sid.slice(0,2)==='hk')return;var kl=klMap[sid];if(kl.length)dayCnt[kl[kl.length-1][0]]=(dayCnt[kl[kl.length-1][0]]||0)+1;});
      var cutoff='';var mx=0;Object.keys(dayCnt).forEach(function(d){if(dayCnt[d]>mx){mx=dayCnt[d];cutoff=d;}});
      if(!cutoff){setStat('⚠ 实时数据异常，显示静态数据','warn');return;}
      // 重算每篇
      var failN=0,allRows=[],arts=[];
      DATA.forEach(function(a){
        var etfCum=null;
        if(a.etf){
          var ekl=klMap[a.etf.secid];
          if(ekl){var er=cumSeries(ekl,a.date,cutoff);if(er){a.etf.data=er.out;a.etf._base=er.base;a.etf._last=er.last;etfCum=er.out.length?er.out[er.out.length-1][1]:null;}}
          if(etfCum===null)etfCum=(a.etf.scum!=null?a.etf.scum:null);
          a.etf._cum=etfCum;
        }
        var rows=[];
        a.series.forEach(function(s){
          var kl=klMap[s.secid],res=null;
          if(kl)res=cumSeries(kl,a.date,cutoff);
          if(res&&res.out.length){
            s.data=res.out;
            var cum=res.out[res.out.length-1][1];
            var vals=res.out.map(function(p){return p[1];});
            rows.push({s:s,cum:cum,exc:(etfCum!=null?r2(cum-etfCum):null),base:res.base,last:res.last,max:Math.max.apply(null,vals),min:Math.min.apply(null,vals),live:true});
          }else{
            failN++;
            rows.push({s:s,cum:s.scum,exc:(s.sexc!=null?s.sexc:null),base:null,last:null,max:null,min:null,live:false});
          }
        });
        var okR=rows.filter(function(r){return r.cum!=null;});
        var avg=okR.length?r2(okR.reduce(function(t,r){return t+r.cum;},0)/okR.length):null;
        var avgex=(avg!=null&&etfCum!=null)?r2(avg-etfCum):null;
        arts.push({a:a,rows:rows,avg:avg,avgex:avgex,etfCum:etfCum});
        rows.forEach(function(r){if(r.cum!=null)allRows.push({name:r.s.name,code:r.s.code,article:a.title,theme:a.theme,cum:r.cum,exc:r.exc});});
      });
      // ---- 全局 stats ----
      var n=allRows.length;
      var avgCum=r2(allRows.reduce(function(t,r){return t+r.cum;},0)/n);
      var win=allRows.filter(function(r){return r.cum>0;}).length;
      var excRows=allRows.filter(function(r){return r.exc!=null;});
      var beat=excRows.filter(function(r){return r.exc>0;}).length;
      var avgExc=excRows.length?r2(excRows.reduce(function(t,r){return t+r.exc;},0)/excRows.length):0;
      var king=excRows.slice().sort(function(x,y){return y.exc-x.exc;})[0];
      var winRate=(win/n*100).toFixed(1),beatRate=excRows.length?(beat/excRows.length*100).toFixed(1):'0.0';
      // ---- KPI ----
      var kv=function(id){return document.getElementById(id);};
      if(kv('kvAvg')){kv('kvAvg').className='kpi-val '+fcls(avgCum);kv('kvAvg').textContent=fpct(avgCum);}
      if(kv('kvWin'))kv('kvWin').innerHTML=winRate+'<span class="u">%</span> <span class="kpi-sub">'+win+'/'+n+'</span>';
      if(kv('kvBeat')){kv('kvBeat').className='kpi-val '+fcls(parseFloat(beatRate)-50);kv('kvBeat').innerHTML=beatRate+'<span class="u">%</span> <span class="kpi-sub">'+beat+'/'+n+'</span>';}
      if(kv('kvExc')){kv('kvExc').className='kpi-val '+fcls(avgExc);kv('kvExc').textContent=fpct(avgExc);}
      if(kv('kvKing')&&king)kv('kvKing').innerHTML=escH(king.name)+'<br><span class="b">'+fpct(king.exc)+'</span>';
      // ---- 洞察 ----
      var eligA=arts.filter(function(x){return x.avgex!=null&&x.rows.filter(function(r){return r.cum!=null;}).length>=2;});
      function insSet(key,html){var el=document.querySelector('.ins-card[data-ins="'+key+'"] .ins-d');if(el)el.innerHTML=html;}
      if(eligA.length){
        var bA=eligA.slice().sort(function(x,y){return y.avgex-x.avgex;})[0];
        var wA=eligA.slice().sort(function(x,y){return x.avgex-y.avgex;})[0];
        var tail=(avgCum<0&&avgExc>0)?'——板块普跌中选股相对抗跌':(avgExc>0?'——整体跑赢行业':'——整体未跑赢行业基准');
        insSet('alpha',n+'只标的平均跑赢对标行业ETF <b class="'+fcls(avgExc)+'">'+fpct(avgExc)+'</b>，'+beatRate+'% 的标的强于行业基准'+tail);
        insSet('best','《'+escH(bA.a.title)+'》篇均超额 <b class="'+fcls(bA.avgex)+'">'+fpct(bA.avgex)+'</b>（发布 '+bA.a.date+'）');
        insSet('worst','《'+escH(wA.a.title)+'》篇均超额 <b class="'+fcls(wA.avgex)+'">'+fpct(wA.avgex)+'</b>（发布 '+wA.a.date+'）');
      }
      // 主题聚合
      var thAgg={};
      arts.forEach(function(x){var t=x.a.theme||'其他';if(!thAgg[t])thAgg[t]={rows:[],arts:{}};x.rows.forEach(function(r){if(r.cum!=null){thAgg[t].rows.push(r);thAgg[t].arts[x.a.title]=1;}});});
      var thList=Object.keys(thAgg).map(function(t){
        var rs=thAgg[t].rows,exs=rs.filter(function(r){return r.exc!=null;});
        return {name:t,n:rs.length,na:Object.keys(thAgg[t].arts).length,
          cum:r2(rs.reduce(function(s,r){return s+r.cum;},0)/rs.length),
          exc:exs.length?r2(exs.reduce(function(s,r){return s+r.exc;},0)/exs.length):null};
      }).sort(function(x,y){return (y.exc==null?-999:y.exc)-(x.exc==null?-999:x.exc);});
      var bT=null;for(var ti=0;ti<thList.length;ti++){if(thList[ti].exc!=null&&thList[ti].n>=3){bT=thList[ti];break;}}
      if(king)insSet('king',escH(king.name)+' 超额 <b class="up">'+fpct(king.exc)+'</b>'+(bT?('；最强主题：'+escH(bT.name)+'（'+bT.n+'只平均超额 <b class="'+fcls(bT.exc)+'">'+fpct(bT.exc)+'</b>）'):''));
      // ---- 排行 ----
      function barRows(items,vk,sk,mab){
        return items.map(function(r){
          var v=r[vk],w=mab?Math.abs(v)/mab*100:0,c=fcls(v),sv=r[sk],sub='';
          if(sv!=null)sub='<span class="bar-ex '+fcls(sv)+'">'+(sk==='exc'?'α':'')+fpct(sv)+'</span>';
          return '<div class="bar-row"><div class="bar-name" title="'+escH(r.article)+'">'+escH(r.name)+'<span class="bar-code">'+r.code+'</span></div><div class="bar-track"><div class="bar-fill '+c+'" style="width:'+w.toFixed(1)+'%"></div></div><div class="bar-val '+c+'">'+fpct(v)+sub+'</div></div>';
        }).join('');
      }
      var rkAbs=allRows.slice().sort(function(x,y){return y.cum-x.cum;});
      var mabA=Math.max(Math.abs(rkAbs[0].cum),Math.abs(rkAbs[rkAbs.length-1].cum),1);
      var blkA=document.getElementById('rankAbsBlk');
      if(blkA)blkA.innerHTML='<div class="rank-wrap"><div class="rank-col"><h3>📈 涨幅榜 Top 8</h3>'+barRows(rkAbs.slice(0,8),'cum','exc',mabA)+'</div><div class="rank-col"><h3>📉 跌幅榜 Top 8</h3>'+barRows(rkAbs.slice(-8).reverse(),'cum','exc',mabA)+'</div></div>';
      if(excRows.length){
        var rkE=excRows.slice().sort(function(x,y){return y.exc-x.exc;});
        var mabE=Math.max(Math.abs(rkE[0].exc),Math.abs(rkE[rkE.length-1].exc),1);
        var blkE=document.getElementById('rankExcBlk');
        if(blkE)blkE.innerHTML='<div class="rank-wrap"><div class="rank-col"><h3>🚀 超额榜 Top 8</h3>'+barRows(rkE.slice(0,8),'exc','cum',mabE)+'</div><div class="rank-col"><h3>🪨 落后榜 Top 8</h3>'+barRows(rkE.slice(-8).reverse(),'exc','cum',mabE)+'</div></div>';
      }
      // ---- 主题卡 ----
      var TC={'机器人':'#7c3aed','新能源':'#0891b2','电力设备':'#2563eb','军工':'#475569','AI算力':'#2c5aa0','半导体':'#c2410c','软件':'#0d9488','医药':'#be123c','周期':'#a16207','高端制造':'#0e7490','金融':'#0369a1','电子':'#a21caf','其他':'#64748b'};
      var tmaxv=1;thList.forEach(function(t){if(t.exc!=null&&Math.abs(t.exc)>tmaxv)tmaxv=Math.abs(t.exc);});
      var tg=document.getElementById('themeGrid');
      if(tg)tg.innerHTML=thList.map(function(t){
        var col=TC[t.name]||'#64748b';
        var excT=t.exc!=null?fpct(t.exc):'—',excC=t.exc!=null?fcls(t.exc):'flat';
        var bar=t.exc!=null?('<div class="tc-bar"><i class="'+excC+'" style="width:'+(Math.abs(t.exc)/tmaxv*100).toFixed(0)+'%"></i></div>'):'';
        return '<div class="theme-card"><div class="tc-head"><span class="tc-dot" style="background:'+col+'"></span><span class="tc-name">'+escH(t.name)+'</span><span class="tc-n">'+t.na+'篇·'+t.n+'只</span></div><div class="tc-rows"><div>平均涨跌 <b class="'+fcls(t.cum)+'">'+fpct(t.cum)+'</b></div><div>平均超额 <b class="'+excC+'">'+excT+'</b></div></div>'+bar+'</div>';
      }).join('');
      // ---- 直方图 ----
      var hb=document.querySelector('.hist-card');
      if(hb){
        var vals2=allRows.map(function(r){return r.cum;});
        var edges=[[-1e9,-20],[-20,-10],[-10,-5],[-5,0],[0,5],[5,10],[10,20],[20,1e9]];
        var labs=['≤-20','-20~-10','-10~-5','-5~0','0~5','5~10','10~20','>20'];
        var cnts=edges.map(function(e){return vals2.filter(function(v){return v>=e[0]&&v<e[1];}).length;});
        var mxc=Math.max.apply(null,cnts)||1,Wd=640,Hh=176,slot=(Wd-24)/8,prt='';
        cnts.forEach(function(c,i){
          var bw=slot*0.6,cx=12+slot*i+slot/2,hp=c===0?0:Math.max(4,c/mxc*104),y=Hh-34-hp;
          var col=edges[i][1]<=0?'#15883e':'#d9342b';
          prt+='<rect x="'+(cx-bw/2).toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+hp.toFixed(1)+'" rx="4" fill="'+col+'" opacity="0.82"/>';
          prt+='<text x="'+cx.toFixed(1)+'" y="'+(y-6).toFixed(1)+'" text-anchor="middle" font-size="11" font-weight="600" fill="#475569">'+c+'</text>';
          prt+='<text x="'+cx.toFixed(1)+'" y="'+(Hh-16)+'" text-anchor="middle" font-size="10" fill="#8a97a8">'+labs[i]+'</text>';
        });
        hb.innerHTML='<div class="hist-t">全部 '+vals2.length+' 只标的累计涨跌幅分布（%）</div><svg viewBox="0 0 '+Wd+' '+Hh+'" width="100%" style="max-width:680px;display:block;margin:0 auto">'+prt+'<line x1="8" y1="'+(Hh-32)+'" x2="'+(Wd-8)+'" y2="'+(Hh-32)+'" stroke="#dde4ee"/></svg>';
      }
      // ---- 明细表 ----
      var cardMap={};
      document.querySelectorAll('#artList .art-card').forEach(function(c){var t=c.querySelector('.art-title');if(t)cardMap[t.textContent.trim()]=c;});
      arts.forEach(function(x){
        var card=cardMap[x.a.title];if(!card)return;
        if(x.avg!=null){var av=card.querySelector('.art-avg');if(av){av.className='art-avg '+fcls(x.avg);av.textContent='篇均 '+fpct(x.avg);}card.dataset.avgcum=x.avg;}
        if(x.avgex!=null){var ae=card.querySelector('.art-ex');if(ae){ae.className='art-ex '+fcls(x.avgex);ae.textContent='篇均超额 '+fpct(x.avgex);}card.dataset.avgex=x.avgex;}
        x.rows.forEach(function(r){
          if(!r.live)return;
          var tr=card.querySelector('tr[data-code="'+r.s.code+'"]');if(!tr)return;
          var td=tr.querySelectorAll('td');if(td.length<8)return;
          td[3].textContent=r.base.toFixed(2);
          td[4].textContent=(r.base*(1+r.cum/100)).toFixed(2);
          td[5].className='cum '+fcls(r.cum);td[5].textContent=fpct(r.cum);
          if(r.exc!=null){td[6].className='exc '+fcls(r.exc);td[6].textContent=fpct(r.exc);}
          td[7].innerHTML=sparkJS(r.s.data);
        });
        if(x.a.etf&&x.a.etf._base!=null){
          var btr=card.querySelector('tr.bench-row');
          if(btr){var btd=btr.querySelectorAll('td');
            if(btd.length>=8){btd[3].textContent=x.a.etf._base.toFixed(3);btd[4].textContent=x.a.etf._last.toFixed(3);
              if(x.a.etf._cum!=null){btd[5].className='cum '+fcls(x.a.etf._cum);btd[5].textContent=fpct(x.a.etf._cum);}
              btd[7].innerHTML=sparkJS(x.a.etf.data,'#1d4ed8');}}
        }
      });
      // ---- 走势图 ----
      try{render();}catch(e){}
      // ---- 批注重挂 ----
      try{if(window.__annoTag)window.__annoTag();if(window.__annoPins)window.__annoPins();}catch(e){}
      var isToday=(cutoff===new Date().toISOString().slice(0,10));
      var phase=isToday?(qtTime&&qtTime<'15:00'?'盘中实时':'今日收盘'):'收盘';
      setStat('⚡ 行情已更新：'+cutoff+(qtTime?' '+qtTime:'')+'（'+phase+'）'+(failN?' · '+failN+'只未更新':''),'ok');
    });
  }catch(e){setStat('⚠ 实时模块异常，显示静态数据','warn');}
})();
</script>
__QRBODY__
__ANNOBODY__
</body></html>"""

# ============ 批注/反馈系统 ============
ANNO_CSS = """
/* ===== 批注/反馈系统 ===== */
.anno-bar{position:fixed;right:18px;bottom:18px;z-index:1000;display:flex;flex-direction:column;gap:8px;align-items:flex-end}
.anno-btn{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid #cbd5e1;color:#334155;font-size:13px;font-weight:600;padding:8px 14px;border-radius:22px;box-shadow:0 3px 12px rgba(20,40,80,.16);cursor:pointer;user-select:none}
.anno-btn:hover{border-color:#94a3b8}
.anno-btn.primary,.anno-btn.on{background:linear-gradient(135deg,#fb923c,#ea580c);color:#fff;border:none}
.anno-btn.on{box-shadow:0 4px 14px rgba(234,88,12,.45)}
.anno-btn .badge{background:#ea580c;color:#fff;font-size:11px;min-width:18px;height:18px;border-radius:9px;display:inline-flex;align-items:center;justify-content:center;padding:0 5px}
.anno-btn.primary .badge{background:#fff;color:#ea580c}
.anno-mini{display:flex;gap:8px}
body.anno-on{cursor:crosshair}
body.anno-on .anno-bar *,body.anno-on .anno-drawer *{cursor:default}
.anno-hover{outline:2px dashed #ea580c!important;outline-offset:2px;background:rgba(251,146,60,.07)}
.anno-layer{position:absolute;top:0;left:0;z-index:900}
.anno-pin{position:absolute;width:22px;height:22px;border-radius:50% 50% 50% 3px;background:#ea580c;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.3);cursor:pointer;border:2px solid #fff}
.anno-pin:hover{background:#c2410c;z-index:901}
.anno-pop{position:absolute;z-index:1001;width:262px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 8px 30px rgba(20,40,80,.22);padding:12px}
.anno-pop .lab{font-size:11.5px;color:#64748b;margin-bottom:6px;font-weight:600;line-height:1.4}
.anno-pop textarea{width:100%;height:72px;font-family:inherit;font-size:13px;border:1px solid #cbd5e1;border-radius:7px;padding:7px;resize:vertical}
.anno-pop .row{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}
.anno-pop button{font-family:inherit;font-size:12.5px;font-weight:600;padding:6px 13px;border-radius:7px;border:none;cursor:pointer}
.anno-pop .save{background:#ea580c;color:#fff}.anno-pop .cancel{background:#eef1f5;color:#475569}
.anno-drawer{position:fixed;top:0;right:0;width:340px;max-width:90vw;height:100%;background:#fff;box-shadow:-6px 0 24px rgba(20,40,80,.18);z-index:1002;transform:translateX(100%);transition:transform .25s;display:flex;flex-direction:column}
.anno-drawer.open{transform:none}
.anno-drawer h3{font-size:15px;font-weight:700;padding:15px 18px;border-bottom:1px solid #eef1f5;display:flex;justify-content:space-between;align-items:center;margin:0}
.anno-drawer h3 .x{cursor:pointer;color:#94a3b8;font-size:22px;line-height:1}
.anno-bd{flex:1;overflow:auto;padding:14px 18px}
.anno-bd .glab{font-size:12px;font-weight:700;color:#475569;margin:0 0 6px}
.anno-bd textarea.global{width:100%;height:64px;font-family:inherit;font-size:13px;border:1px solid #cbd5e1;border-radius:8px;padding:8px;resize:vertical;margin-bottom:16px}
.anno-item{border:1px solid #eef1f5;border-radius:9px;padding:10px;margin-bottom:9px;background:#fafbfd}
.anno-item .top{display:flex;align-items:center;margin-bottom:5px}
.anno-item .n{background:#ea580c;color:#fff;font-size:11px;font-weight:700;min-width:18px;height:18px;border-radius:9px;display:inline-flex;align-items:center;justify-content:center}
.anno-item .tgt{font-size:11.5px;color:#64748b;flex:1;margin:0 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.anno-item .tgt:hover{color:#ea580c;text-decoration:underline}
.anno-item .del{color:#cbd5e1;cursor:pointer;font-size:16px}.anno-item .del:hover{color:#ef4444}
.anno-item .nt{font-size:13px;color:#1e293b;white-space:pre-wrap}
.anno-empty{color:#94a3b8;font-size:13px;text-align:center;padding:26px 10px;line-height:1.7}
.anno-foot{border-top:1px solid #eef1f5;padding:12px 18px;display:flex;gap:8px;flex-wrap:wrap}
.anno-foot button{flex:1;font-family:inherit;font-size:12.5px;font-weight:600;padding:9px;border-radius:8px;border:1px solid #cbd5e1;background:#fff;cursor:pointer;min-width:88px}
.anno-foot .exp{background:linear-gradient(135deg,#fb923c,#ea580c);color:#fff;border:none}
.anno-toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;font-size:13px;padding:10px 18px;border-radius:8px;z-index:1003;opacity:0;transition:opacity .2s;pointer-events:none;max-width:84vw;text-align:center;line-height:1.5}
.anno-toast.show{opacity:.96}
.anno-banner{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-size:12.5px;padding:8px 12px;border-radius:8px;margin-bottom:14px;line-height:1.5}
@media print{.anno-bar,.anno-drawer,.anno-layer,.anno-pop,.anno-toast{display:none!important}}
"""

ANNO_BODY = """
<div class="anno-ui">
  <div class="anno-bar">
    <div class="anno-mini">
      <div class="anno-btn" id="annoList" title="查看/编辑反馈清单">💬 反馈 <span class="badge" id="annoCount">0</span></div>
      <div class="anno-btn primary" id="annoExport" title="导出反馈，发给作者">📤 导出</div>
    </div>
    <div class="anno-btn" id="annoToggle">✍️ 批注模式：关</div>
  </div>
  <div class="anno-drawer" id="annoDrawer">
    <h3>批注反馈 <span class="x" id="annoClose">×</span></h3>
    <div class="anno-bd">
      <div id="annoBanner"></div>
      <div class="glab">总体意见</div>
      <textarea class="global" id="annoGlobal" placeholder="对整个看板的总体看法、想加或想改的地方…"></textarea>
      <div class="glab">逐条批注 <span id="annoListCount"></span></div>
      <div id="annoItems"></div>
    </div>
    <div class="anno-foot">
      <button class="exp" id="annoExport2">📤 导出反馈链接</button>
      <button id="annoImport">📂 导入</button>
      <button id="annoClear">🗑️ 清空</button>
    </div>
  </div>
  <div class="anno-toast" id="annoToast"></div>
</div>
<script>
(function(){
  var KEY='annoFB:'+location.pathname;
  var state={author:localStorage.getItem('annoAuthor')||'',global:'',items:[]};
  var seq=0,mode=false,curPop=null,hovEl=null;
  var layer=document.createElement('div');layer.className='anno-layer';document.body.appendChild(layer);
  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}
  function $(id){return document.getElementById(id);}
  function tag(){
    document.querySelectorAll('.kpi').forEach(function(el){var l=el.querySelector('.kpi-label');var t=l?l.textContent.trim():'指标';el.dataset.anno='kpi:'+t;el.dataset.annolabel='指标 · '+t;});
    var ch=document.querySelector('#mainChart');if(ch){var c=ch.closest('.card');if(c){c.dataset.anno='chart';c.dataset.annolabel='累计涨跌幅走势图';}}
    document.querySelectorAll('.ins-card').forEach(function(el){var t=el.querySelector('.ins-t');var x=t?t.textContent.trim():'洞察';el.dataset.anno='insight:'+x;el.dataset.annolabel='洞察 · '+x;});
    document.querySelectorAll('.theme-card').forEach(function(el){var t=el.querySelector('.tc-name');var x=t?t.textContent.trim():'主题';el.dataset.anno='theme:'+x;el.dataset.annolabel='主题 · '+x;});
    var hh=document.querySelector('.hist-card');if(hh){hh.dataset.anno='hist';hh.dataset.annolabel='涨跌幅分布图';}
    document.querySelectorAll('.rank-col').forEach(function(el){var h=el.querySelector('h3');var x=h?h.textContent.trim():'排行';el.dataset.anno='rank:'+x;el.dataset.annolabel='排行 · '+x;});
    document.querySelectorAll('.art-card').forEach(function(card){var t=card.querySelector('.art-title');var ti=t?t.textContent.trim():'';card.dataset.anno='art:'+ti;card.dataset.annolabel='文章 · '+ti;card.querySelectorAll('tbody tr').forEach(function(tr){var nm=tr.querySelector('.tname');var cd=tr.querySelector('.mono');var nn=nm?nm.textContent.trim():'';tr.dataset.anno='row:'+ti+'|'+(cd?cd.textContent.trim():'');tr.dataset.annolabel=ti+' · '+nn;});});
  }
  function findEl(target){var all=document.querySelectorAll('[data-anno]');for(var i=0;i<all.length;i++){if(all[i].dataset.anno===target)return all[i];}return null;}
  document.addEventListener('mousemove',function(e){
    if(!mode)return;
    var el=e.target.closest&&e.target.closest('[data-anno]');
    if(e.target.closest('.anno-ui')||e.target.closest('.anno-pop'))el=null;
    if(el===hovEl)return;
    if(hovEl)hovEl.classList.remove('anno-hover');
    if(el){el.classList.add('anno-hover');hovEl=el;}else hovEl=null;
  });
  document.addEventListener('click',function(e){
    if(!mode)return;
    if(e.target.closest('.anno-ui')||e.target.closest('.anno-pop')||e.target.closest('.anno-pin'))return;
    if(e.target.closest('select,button,a,input,textarea,option'))return;
    var el=e.target.closest('[data-anno]');if(!el)return;
    e.preventDefault();e.stopPropagation();
    openPop(el,e.pageX,e.pageY,null);
  },true);
  function closePop(){if(curPop){curPop.remove();curPop=null;}}
  function openPop(el,x,y,existing){
    closePop();
    var label=existing?existing.label:(el?el.dataset.annolabel:'');
    var pop=document.createElement('div');pop.className='anno-pop';
    pop.innerHTML='<div class="lab">📍 '+esc(label)+'</div><textarea placeholder="写下要改 / 要加的意见…"></textarea><div class="row"><button class="cancel">取消</button><button class="save">保存</button></div>';
    document.body.appendChild(pop);
    var maxL=window.scrollX+document.documentElement.clientWidth-272;
    pop.style.left=Math.max(8,Math.min(x,maxL))+'px';pop.style.top=(y+8)+'px';
    var ta=pop.querySelector('textarea');ta.value=existing?existing.note:'';setTimeout(function(){ta.focus();},0);
    pop.querySelector('.cancel').onclick=closePop;
    pop.querySelector('.save').onclick=function(){
      var v=ta.value.trim();
      if(existing){if(v)existing.note=v;else remove(existing);closePop();persist();renderAll();return;}
      if(!v){closePop();return;}
      if(!state.author){var a=prompt('署名（方便作者识别，可留空）：','');state.author=a||'';localStorage.setItem('annoAuthor',state.author);}
      state.items.push({n:++seq,target:el.dataset.anno,label:label,note:v});
      closePop();persist();renderAll();
    };
    curPop=pop;
  }
  document.addEventListener('mousedown',function(e){if(curPop&&!e.target.closest('.anno-pop'))closePop();},true);
  function remove(it){var i=state.items.indexOf(it);if(i>=0)state.items.splice(i,1);}
  function renderPins(){
    layer.innerHTML='';
    state.items.forEach(function(it){
      var pin=document.createElement('div');pin.className='anno-pin';pin.textContent=it.n;
      pin.onclick=function(ev){ev.stopPropagation();openPop(findEl(it.target),ev.pageX,ev.pageY,it);};
      layer.appendChild(pin);it._pin=pin;
    });
    posPins();
  }
  function posPins(){state.items.forEach(function(it){if(!it._pin)return;var el=findEl(it.target);if(!el||!el.offsetParent){it._pin.style.display='none';return;}var r=el.getBoundingClientRect();it._pin.style.display='flex';it._pin.style.left=(r.left+window.scrollX-6)+'px';it._pin.style.top=(r.top+window.scrollY-6)+'px';});}
  window.__annoPins=posPins;window.__annoTag=tag;
  window.addEventListener('scroll',posPins,{passive:true});window.addEventListener('resize',posPins);
  function renderDrawer(){
    $('annoGlobal').value=state.global;
    var box=$('annoItems');box.innerHTML='';
    if(!state.items.length)box.innerHTML='<div class="anno-empty">还没有逐条批注。<br>点右下角「✍️ 批注模式」开启后，<br>点任意 指标卡 / 洞察 / 主题 / 标的行 / 文章 / 图表 即可标注。</div>';
    state.items.forEach(function(it){
      var d=document.createElement('div');d.className='anno-item';
      d.innerHTML='<div class="top"><span class="n">'+it.n+'</span><span class="tgt" title="点击定位">'+esc(it.label)+'</span><span class="del" title="删除">×</span></div><div class="nt">'+esc(it.note)+'</div>';
      d.querySelector('.del').onclick=function(){remove(it);persist();renderAll();};
      d.querySelector('.tgt').onclick=function(){var el=findEl(it.target);if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.classList.add('anno-hover');setTimeout(function(){el.classList.remove('anno-hover');},1300);}};
      box.appendChild(d);
    });
    $('annoCount').textContent=state.items.length;$('annoListCount').textContent='('+state.items.length+')';
  }
  function renderAll(){renderPins();renderDrawer();}
  function buildObj(){return {v:1,page:document.title,ts:new Date().toISOString().slice(0,19).replace('T',' '),author:state.author,global:state.global,items:state.items.map(function(it){return {n:it.n,target:it.target,label:it.label,note:it.note};})};}
  function persist(){try{localStorage.setItem(KEY,JSON.stringify(buildObj()));}catch(e){}}
  function enc(s){return btoa(unescape(encodeURIComponent(s)));}
  function dec(s){return decodeURIComponent(escape(atob(s)));}
  function doExport(){
    if(!state.items.length&&!state.global.trim()){toast('还没有任何批注或意见');openDrawer();return;}
    var js=JSON.stringify(buildObj());
    var url=location.origin+location.pathname+'#fb='+enc(js);
    var long=url.length>7000;
    if(navigator.clipboard)navigator.clipboard.writeText(long?js:url).then(function(){},function(){});
    var blob=new Blob([js],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='看板反馈_'+(state.author||'匿名')+'.json';document.body.appendChild(a);a.click();a.remove();
    toast(long?'反馈较多：已复制 JSON 并下载文件，发给作者即可':'✅ 反馈链接已复制，直接发给作者即可（已同时下载 JSON 备份）');
  }
  function doImport(){
    var s=prompt('粘贴反馈链接 或 反馈JSON：','');if(!s)return;
    try{if(s.indexOf('#fb=')>=0)s=dec(s.split('#fb=')[1]);var obj=JSON.parse(s);apply(obj,true);toast('已导入反馈');}catch(e){toast('导入失败：格式不对');}
  }
  function clearAll(){if(!confirm('清空所有批注和意见？'))return;state.global='';state.items=[];seq=0;persist();renderAll();banner('');}
  function apply(obj,external){
    state.global=obj.global||'';
    state.items=(obj.items||[]).map(function(it){return {n:it.n,target:it.target,label:it.label,note:it.note};});
    seq=state.items.reduce(function(m,it){return Math.max(m,it.n||0);},0);
    renderAll();persist();
    if(external){banner('正在查看 <b>'+esc(obj.author||'匿名')+'</b> 的反馈　'+esc(obj.ts||''));openDrawer();}
  }
  function load(){
    var h=location.hash;
    if(h.indexOf('#fb=')===0){try{apply(JSON.parse(dec(h.slice(4))),true);return;}catch(e){}}
    var s=localStorage.getItem(KEY);if(s){try{apply(JSON.parse(s),false);}catch(e){}}
  }
  function setMode(on){mode=on;document.body.classList.toggle('anno-on',on);var b=$('annoToggle');b.classList.toggle('on',on);b.textContent=on?'✍️ 批注中：点卡片/行标注':'✍️ 批注模式：关';if(!on&&hovEl){hovEl.classList.remove('anno-hover');hovEl=null;}if(on)toast('已开启批注：点任意 指标卡 / 洞察 / 主题 / 标的行 / 文章 / 图表 即可标注');}
  function openDrawer(){$('annoDrawer').classList.add('open');}
  function closeDrawer(){$('annoDrawer').classList.remove('open');}
  var tmr;function toast(m){var t=$('annoToast');t.textContent=m;t.classList.add('show');clearTimeout(tmr);tmr=setTimeout(function(){t.classList.remove('show');},3800);}
  function banner(m){var b=$('annoBanner');b.innerHTML=m?'<div class="anno-banner">'+m+'</div>':'';}
  tag();
  $('annoToggle').onclick=function(){setMode(!mode);};
  $('annoList').onclick=openDrawer;$('annoClose').onclick=closeDrawer;
  $('annoExport').onclick=doExport;$('annoExport2').onclick=doExport;
  $('annoImport').onclick=doImport;$('annoClear').onclick=clearAll;
  $('annoGlobal').addEventListener('input',function(){state.global=this.value;persist();});
  load();renderAll();
})();
</script>
"""

QR_BODY = """
<div class="qr-mask" id="qrMask">
  <div class="qr-box">
    <div class="qr-title" id="qrTitle"></div>
    <div class="qr-svg" id="qrSvg"></div>
    <div class="qr-tip">📱 微信 / 相机扫码看原文</div>
    <div class="qr-url" id="qrUrl"></div>
    <div class="qr-btns">
      <button class="qr-copy" id="qrCopy">📋 复制链接</button>
      <a class="qr-open" id="qrOpen" target="_blank" rel="noopener">↗ 打开原文</a>
      <button id="qrClose">关闭</button>
    </div>
  </div>
</div>
<script>
(function(){
  var mask=document.getElementById('qrMask');
  function openQR(url,title){
    document.getElementById('qrTitle').textContent=title||'';
    document.getElementById('qrUrl').textContent=url;
    document.getElementById('qrOpen').href=url;
    var box=document.getElementById('qrSvg');box.innerHTML='';
    try{
      if(typeof qrcode==='undefined')throw 0;
      var qr=qrcode(0,'M');qr.addData(url);qr.make();
      box.innerHTML=qr.createSvgTag({cellSize:6,margin:1,scalable:true});
    }catch(e){
      box.innerHTML='<a href="'+url+'" target="_blank" style="font-size:12px;color:#2c5aa0">二维码加载失败，点此打开原文</a>';
    }
    mask.style.display='flex';
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('.art-link');
    if(b){e.preventDefault();openQR(b.dataset.url,b.dataset.title);return;}
    if(e.target===mask||e.target.id==='qrClose')mask.style.display='none';
  });
  var cp=document.getElementById('qrCopy');
  if(cp)cp.onclick=function(){
    var u=document.getElementById('qrUrl').textContent,self=this;
    if(navigator.clipboard)navigator.clipboard.writeText(u).then(function(){self.textContent='✓ 已复制';setTimeout(function(){self.textContent='📋 复制链接';},1500);});
  };
  document.addEventListener('keydown',function(e){if(e.key==='Escape')mask.style.display='none';});
})();
</script>
"""

HTML = (TEMPLATE
        .replace("__ASHLAST__", st["ash_last"])
        .replace("__TODAY__", PAGE_UPDATE)
        .replace("__KPI__", kpi_html)
        .replace("__INS__", ins_html)
        .replace("__RANKABS__", rank_abs_html)
        .replace("__RANKEXC__", rank_exc_html)
        .replace("__THEMES__", themes_html)
        .replace("__HIST__", hist_html)
        .replace("__CHIPS__", chips_html)
        .replace("__ARTS__", "".join(arts_html))
        .replace("__CHART__", chart_json)
        .replace("__ANNOCSS__", ANNO_CSS)
        .replace("__QRBODY__", QR_BODY)
        .replace("__ANNOBODY__", ANNO_BODY))

open("/tmp/tracking.html", "w", encoding="utf-8").write(HTML)
print("HTML 生成完成:", len(HTML), "字节")
