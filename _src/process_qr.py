# -*- coding: utf-8 -*-
"""自动处理 qr_in/ 里的二维码图:解码→渲染读标题→对应文章→裁黑边→写入 article_links.json。
幂等:解码URL已在 article_links.json 里的跳过。无新图则空跑。
被 sync.sh 在抓取前调用,用户只需把二维码图丢进 qr_in/。"""
import os, re, json, glob, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
QRIN = os.path.join(HERE, "qr_in")
QROUT = os.path.join(HERE, "qr")
LINKS = os.path.join(HERE, "article_links.json")
STOCKS = os.path.join(HERE, "stocks.json")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"

def decode_qr(path):
    """用 qrserver 在线接口解码二维码图,返回 URL。"""
    try:
        import ssl
        ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with open(path, "rb") as f:
            data = f.read()
        boundary = "----qrb"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"q.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request("https://api.qrserver.com/v1/read-qr-code/", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        r = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode())
        return r[0]["symbol"][0].get("data")
    except Exception as e:
        print("  解码失败:", e); return None

def fetch_title(url):
    """无头渲染取标题(SPA 动态加载)。综合 <title>/og:title/h1 取最长,防截断。"""
    try:
        out = subprocess.run([CHROME, "--headless=new", "--disable-gpu",
                              "--virtual-time-budget=16000", f"--user-agent={UA}",
                              "--dump-dom", url], capture_output=True, timeout=45).stdout.decode("utf-8", "ignore")
        cands = []
        for pat in [r"<title>([^<]+)</title>",
                    r'property="og:title"[^>]*content="([^"]+)"',
                    r'content="([^"]+)"[^>]*property="og:title"',
                    r'<h1[^>]*>([^<]{6,60})</h1>']:
            for m in re.findall(pat, out):
                s = m.strip()
                if s and "内参" not in s:
                    cands.append(s)
        return max(cands, key=len) if cands else None
    except Exception as e:
        print("  取标题失败:", e); return None

def keywords(title):
    """从标题抽取去标点的中文/英文词块,用于匹配。"""
    segs = re.split(r"[，、：；,!！?？\s（）()【】]+", title)
    out = set()
    for s in segs:
        s = s.strip()
        if len(s) >= 2:
            out.add(s)
    # 额外:连续中文2-5gram,抓"焦煤""电网""交换机""钼钨铀"等核心词
    for m in re.findall(r"[一-龥A-Za-z]{2,6}", title):
        out.add(m)
    return out

def match_article(pub_title, article_titles):
    """按关键词重叠把官方标题对应到看板文章;自信才返回,否则 None。"""
    pk = keywords(pub_title)
    scored = []
    for at in article_titles:
        ak = keywords(at)
        # 共同词按长度加权
        common = pk & ak
        score = sum(len(w) for w in common)
        # 再加:核心主题词命中(双向子串)
        for w in ak:
            if len(w) >= 2 and w in pub_title:
                score += len(w)
        scored.append((score, at))
    scored.sort(reverse=True)
    if not scored:
        return None, scored
    best_s, best = scored[0]
    second_s = scored[1][0] if len(scored) > 1 else 0
    # 自信: 最高分>=4 且明显领先次高(>1.3倍或差>=4)
    if best_s >= 4 and (best_s >= second_s * 1.3 or best_s - second_s >= 4):
        return best, scored
    return None, scored

def crop_qr(src, dst):
    """裁掉黑色背景边,输出正方形干净二维码。"""
    from PIL import Image
    import numpy as np
    im = Image.open(src).convert("RGB")
    a = np.array(im.convert("L")); white = a > 235
    rf = white.mean(axis=1); cf = white.mean(axis=0)
    rows = np.where(rf > 0.12)[0]; cols = np.where(cf > 0.12)[0]
    if len(rows) == 0 or len(cols) == 0:
        im.save(dst); return
    t, b, l, r = int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())
    side = max(r - l, b - t); cx, cy = (l + r) // 2, (t + b) // 2
    l2, t2 = max(0, cx - side // 2 - 3), max(0, cy - side // 2 - 3)
    im.crop((l2, t2, l2 + side + 6, t2 + side + 6)).save(dst)

def slug(article_title):
    # 取一个短关键词做文件名
    for kw in ["焦煤","电网","交换机","芯片级互联","钼钨铀","信创","软件","锂电","锂资源","机器人",
               "半导体","封装","存储","功率半导体","券商","航空","航天","商业航天","大国重工",
               "医药","化工","金属","MLCC","被动元件","PCB","人工智能","新能源车","热管理"]:
        if kw in article_title:
            return kw
    return re.sub(r"[^一-龥A-Za-z0-9]", "", article_title)[:8]

def main():
    os.makedirs(QROUT, exist_ok=True)
    links = json.load(open(LINKS, encoding="utf-8")) if os.path.exists(LINKS) else {}
    known_urls = {v.get("url") if isinstance(v, dict) else v for v in links.values()}
    article_titles = [v["title"] for v in json.load(open(STOCKS, encoding="utf-8")).values()] \
        if os.path.exists(STOCKS) else []
    imgs = sorted(glob.glob(os.path.join(QRIN, "*.jpg")) + glob.glob(os.path.join(QRIN, "*.jpeg"))
                  + glob.glob(os.path.join(QRIN, "*.png")))
    new, manual = 0, []
    for p in imgs:
        url = decode_qr(p)
        if not url:
            continue
        if url in known_urls:
            continue  # 已处理
        title = fetch_title(url) or ""
        art, scored = match_article(title, article_titles)
        print(f"  图 {os.path.basename(p)} → {url}")
        print(f"    官方标题: {title[:40]}")
        if not art:
            top = "; ".join(f"{s}:{t[:12]}" for s, t in scored[:3])
            print(f"    ⚠ 未能自信匹配,需人工确认。候选: {top}")
            manual.append((os.path.basename(p), url, title))
            continue
        sl = slug(art)
        dst_name = f"qr_{sl}.png"
        crop_qr(p, os.path.join(QROUT, dst_name))
        links[art] = {"url": url, "img": f"qr/{dst_name}"}
        known_urls.add(url)
        new += 1
        print(f"    ✅ 对应《{art}》→ {dst_name}")
    if new:
        json.dump(links, open(LINKS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"二维码处理: 新增 {new} 篇" + (f", {len(manual)} 张待人工确认" if manual else ""))
    if manual:
        print("  待确认(告诉我对应哪篇即可):")
        for n, u, t in manual:
            print(f"    - {n}: {t[:30]}")

if __name__ == "__main__":
    main()
