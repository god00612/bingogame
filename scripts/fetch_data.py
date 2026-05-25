"""
每月自動從 twfood.cc 抓取當季蔬果推薦清單，寫入 data.json。
由 GitHub Actions 排程執行，無需 CORS Proxy。
"""
import json, re, urllib.request
from urllib.parse import unquote
from datetime import date

# 已知無圖代碼 → 替換
CODE_FIX = {'T1': 'T2'}

# 通用類別名稱（取破折號後的具體品名）
GENERIC = {'雜柑', '雜果', '其他'}


def fetch_page(url):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BingoBot/1.0)'}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode('utf-8', errors='replace')


def parse_items(html, type_):
    items = []
    seen_codes, seen_names = set(), set()
    pattern = rf'href="/{re.escape(type_)}/([^/"]+)/([^"]+)"[^>]*>(.*?)</a>'
    for m in re.finditer(pattern, html, re.DOTALL):
        code     = m.group(1)
        path_seg = m.group(2)
        text     = re.sub(r'<[^>]+>', '', m.group(3))

        if '推薦No:' not in text:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)

        raw = unquote(path_seg).replace('+', ' ')

        paren = re.search(r'[（(]([^）)]+)[）)]', raw)
        if paren:
            name = re.split(r'[,，]', paren.group(1))[0].strip()
        else:
            segs   = re.split(r'[-－]', raw)
            prefix = segs[0].strip()
            suffix = segs[1].strip() if len(segs) > 1 else ''
            name   = suffix if prefix in GENERIC and suffix else prefix

        if not name or len(name) > 8 or name in seen_names:
            continue
        seen_names.add(name)

        fixed_code = CODE_FIX.get(code, code)
        items.append({
            'name':   name,
            'imgUrl': f'https://www.twfood.cc/img/code/{fixed_code}/_.jpg'
        })
    return items


def fetch_category(type_):
    seen_urls, seen_names = set(), set()
    items = []

    def add_items(page_items):
        for item in page_items:
            if len(items) >= 25:
                return
            if item['imgUrl'] not in seen_urls and item['name'] not in seen_names:
                seen_urls.add(item['imgUrl'])
                seen_names.add(item['name'])
                items.append(item)

    # 先抓前 5 頁
    for page in range(1, 6):
        try:
            html = fetch_page(f'https://www.twfood.cc/{type_}?page={page}&per-page=5')
            add_items(parse_items(html, type_))
            print(f'  [{type_}] page {page}: {len(items)} items so far')
        except Exception as e:
            print(f'  [{type_}] page {page} failed: {e}')

    # 不足 25 筆繼續翻頁（最多到第 20 頁）
    for page in range(6, 21):
        if len(items) >= 25:
            break
        try:
            html       = fetch_page(f'https://www.twfood.cc/{type_}?page={page}&per-page=5')
            page_items = parse_items(html, type_)
            if not page_items:
                break
            add_items(page_items)
            print(f'  [{type_}] page {page}: {len(items)} items so far')
        except Exception as e:
            print(f'  [{type_}] page {page} failed: {e}')
            break

    return items


if __name__ == '__main__':
    print('Fetching vege...')
    vege = fetch_category('vege')
    print(f'  → {len(vege)} vege items')

    print('Fetching fruit...')
    fruit = fetch_category('fruit')
    print(f'  → {len(fruit)} fruit items')

    data = {
        'updated': str(date.today()),
        'vege':    vege,
        'fruit':   fruit
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'\ndata.json written  vege={len(vege)}  fruit={len(fruit)}')
