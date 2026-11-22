#!/usr/bin/env python3
"""按 channels.txt 生成精简直播列表。
用法: python3 build.py [--slate-check] [--probe-order] [--local-dir DIR] [--report report.json]
  --slate-check  抓每条线路一帧，和 slates/ 参考图比对，丢掉“盗版提示/打赏”占位画面（需要 ffmpeg、Pillow）
  --probe-order  能播的线路排前面（只有在国内机器上运行才有意义；GitHub 机房在国外，默认不用）
  --local-dir    用本地 <源名>.m3u 文件代替下载（测试用）
"""
import argparse, datetime, json, os, re, subprocess, sys, tempfile, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--config', default=os.path.join(HERE, 'config.json'))
ap.add_argument('--channels', default=os.path.join(HERE, 'channels.txt'))
ap.add_argument('--out')
ap.add_argument('--slate-check', action='store_true')
ap.add_argument('--probe-order', action='store_true')
ap.add_argument('--local-dir')
ap.add_argument('--report')
A = ap.parse_args()
C = json.load(open(A.config, encoding='utf-8'))
OUT = A.out or os.path.join(HERE, C.get('output', 'output/elderly.m3u'))

# ---------- 读 channels.txt ----------
plan = []   # (group, key, display, aliases) 或 (group, '*', None, [前缀...])
group = '未分组'
for raw in open(A.channels, encoding='utf-8'):
    line = raw.strip()
    if not line or line.startswith('#'): continue
    m = re.fullmatch(r'\[(.+)\]', line)
    if m: group = m.group(1).strip(); continue
    if line.startswith('*'):
        plan.append((group, '*', None, line[1:].split())); continue
    disp, _, al = line.partition('=')
    disp = disp.strip(); key = disp.split()[0]
    aliases = [a.strip().replace(' ', '') for a in al.split(',') if a.strip()]
    plan.append((group, key, disp, aliases))

# ---------- 源 ----------
EN = {  # iptv-org 英文名 -> 中文
 r'^Anhui TV':'安徽卫视', r'^Bingtuan Satellite':'兵团卫视', r'^Guangdong Satellite':'广东卫视', r'^Hunan TV':'湖南卫视',
 r'^Jiangsu Satellite':'江苏卫视', r'^Jiangxi TV':'江西卫视', r'^Nei Monggol TV \(':'内蒙古卫视', r'^Qinghai TV':'青海卫视',
 r'^Shandong (Satellite )?TV \(':'山东卫视', r'^Shenzhen Satellite':'深圳卫视', r'^Sichuan Satellite':'四川卫视', r'^Tianjin TV':'天津卫视',
 r'^Xinjiang TV 1$':'新疆卫视', r'^Xizang TV Chinese':'西藏卫视', r'^Yanbian Satellite':'延边卫视', r'^Zhejiang Satellite':'浙江卫视',
 r'^Beijing Satellite':'北京卫视', r'^Guizhou TV':'贵州卫视', r'^Hebei TV':'河北卫视', r'^Heilongjiang TV':'黑龙江卫视',
 r'^Liaoning TV':'辽宁卫视', r'^Yunnan Satellite':'云南卫视', r'^Ningxia Satellite':'宁夏卫视', r'^Kangba TV':'康巴卫视',
 r"^Xi'an Silk Road":'西安丝路', r"^Xi'an Business Information":'西安商务资讯',
 r'^CCTV-Nostalgia Theater':'CCTV怀旧剧场', r'^CCTV-The First Theater':'CCTV第一剧场'}

def fetch(src):
    if A.local_dir:
        return open(os.path.join(A.local_dir, src['name'] + '.m3u'), encoding='utf-8', errors='ignore').read()
    req = urllib.request.Request(src['url'], headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')

def parse(text):
    out, cur = [], None
    for l in text.splitlines():
        l = l.strip()
        if l.startswith('#EXTINF'):
            tvg = re.search(r'tvg-name="([^"]*)"', l); ua = re.search(r'http-user-agent="([^"]*)"', l)
            cur = {'raw': l.split(',')[-1].strip(), 'tvg': tvg.group(1) if tvg else '', 'ua': ua.group(1) if ua else None}
        elif l and not l.startswith('#') and cur:
            cur['url'] = l; out.append(cur); cur = None
    return out

def norm(e):
    n = e['raw']
    for pat, zh in EN.items():
        if re.search(pat, n): return zh
    n = re.sub(r'\s*\((\d+p|\d+i)\)|\s*\[[^\]]*\]', '', n).strip()
    m = re.match(r'^CCTV[-\s]?(\d{1,2}\+?)(?![\dK])', n, re.I)
    if m and not re.search(r'4K|8K', n, re.I): return 'CCTV' + m.group(1)
    n = re.sub(r'^CCTV-(?=\D)', 'CCTV', n).replace(' ', '')
    # suxuang 的本地频道显示名常省略省份，tvg-name 里才有（如 tvg-name=陕西都市青春, 名称=都市青春）
    if e['tvg'] and e['tvg'].endswith(n) and len(e['tvg']) > len(n) and not e['tvg'].startswith('CCTV'): n = e['tvg'].replace(' ', '')
    return n

found = {}    # 归一化名 -> [(源, url, ua)]
stats = {'blocked': 0, 'dropped_4k': 0, 'slate': 0}
for src in C['sources']:
    try: items = parse(fetch(src))
    except Exception as ex: print(f'!! 源 {src["name"]} 下载失败: {ex}', file=sys.stderr); continue
    for e in items:
        if not e['url'].startswith('http'): continue
        n = norm(e)
        if any(b in e['raw'] for b in C['blocked_names']) or any(re.search(p, e['url']) for p in C['blocked_url_patterns']):
            stats['blocked'] += 1; continue
        if C.get('drop_4k') and re.search(r'4K|8K|2160p', e['raw'] + e['url'], re.I): stats['dropped_4k'] += 1; continue
        L = found.setdefault(n, [])
        if e['url'] not in [x[1] for x in L]: L.append((src['name'], e['url'], e['ua']))

# ---------- 按频道表挑选 ----------
used, result = set(), []   # result: (group, key, display, lines)
listed = {k for _, k, _, _ in plan if k != '*'} | {a for _, k, _, al in plan if k != '*' for a in al}
for g, key, disp, al in plan:
    if key == '*':
        extra = sorted(n for n in found if n not in used and n not in listed
                       and any(n.startswith(p) for p in al) and n not in [p + '卫视' for p in al])
        for n in extra: used.add(n); result.append((g, n, n, list(found[n])))
        continue
    lines = []
    for name in [key] + al:
        for x in found.get(name, []):
            if x[1] not in [y[1] for y in lines]: lines.append(x)
        used.add(name)
    if lines: result.append((g, key, disp, lines))

# ---------- 可选：画面占位检测 / 可播排序 ----------
def dhash(img):
    w, h = img.size; img = img.crop((0, 0, w, int(h * 0.6))).convert('L').resize((17, 16))
    px = list(img.getdata()); return [px[r * 17 + c] > px[r * 17 + c + 1] for r in range(16) for c in range(16)]
status = {}
if A.slate_check or A.probe_order:
    from PIL import Image
    sd = os.path.join(HERE, 'slates'); refs = [dhash(Image.open(os.path.join(sd, f))) for f in sorted(os.listdir(sd))]
    def probe(url):
        f = tempfile.mktemp(suffix='.jpg')
        try:
            r = subprocess.run(['ffmpeg', '-v', 'error', '-rw_timeout', '10000000', '-y', '-ss', '2', '-i', url, '-frames:v', '1',
                                '-vf', 'scale=320:-1', f], capture_output=True, timeout=40)
            if r.returncode or not os.path.exists(f): return 'fail'
            h = dhash(Image.open(f))
            return 'slate' if any(sum(a != b for a, b in zip(h, ref)) <= 40 for ref in refs) else 'ok'
        except Exception: return 'fail'
        finally:
            if os.path.exists(f): os.remove(f)
    urls = sorted({x[1] for r in result for x in r[3]})
    with ThreadPoolExecutor(16) as ex:
        for u, s in zip(urls, ex.map(probe, urls)): status[u] = s
    stats['slate'] = sum(1 for s in status.values() if s == 'slate')
    for r in result:
        r[3][:] = [x for x in r[3] if status.get(x[1]) != 'slate']
        if A.probe_order: r[3].sort(key=lambda x: status.get(x[1]) != 'ok')
    result = [r for r in result if r[3]]

MAXL = C.get('max_lines_per_channel', 99)
now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
out = ['#EXTM3U x-tvg-url="http://epg.51zmt.top:8000/e.xml"',
       f'# 生成时间(北京时间) {now:%Y-%m-%d %H:%M}  频道 {len(result)}  线路 {sum(min(len(r[3]), MAXL) for r in result)}']
for g, key, disp, lines in result:
    for src, url, ua in lines[:MAXL]:
        uaattr = f' http-user-agent="{ua}"' if ua else ''
        out.append(f'#EXTINF:-1 tvg-name="{key}" tvg-logo="https://live.fanmingming.cn/tv/{key}.png" group-title="{g}"{uaattr},{disp}')
        out.append(url)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
missing = [d for g, k, d, _ in plan if k != '*' and k not in {r[1] for r in result}]
groups = {}
for g, *_ in result: groups[g] = groups.get(g, 0) + 1
print(f'写出 {OUT}: ' + '，'.join(f'{g} {c}' for g, c in groups.items()) + f'；源里没找到: {"、".join(missing) or "无"}；过滤 {stats}')
if A.report:
    json.dump({'groups': groups, 'missing': missing, 'stats': stats,
               'channels': [{'group': g, 'name': d, 'lines': [(s, u, status.get(u)) for s, u, _ in L[:MAXL]]} for g, k, d, L in result]},
              open(A.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
