#!/usr/bin/env python3
"""
Импорт остатков Teez (xlsx + PDF-каталог с розничными ценами) -> data/catalog.json

Запуск:
  python tools/import_teez.py путь/к/остатки.xlsx путь/к/каталог.pdf [--images папка_с_фото]

* Количества, цвета и размеры берутся из xlsx.
* Розничная цена берётся из PDF-каталога (строка «NNNN ₸/шт» под названием).
  Если в PDF товара нет — цена = цена из xlsx × MARKUP (по умолчанию 1.2).
* Закупочные цены из xlsx в catalog.json НЕ попадают (репозиторий публичный).
* Уже существующие ручные правки в catalog.json (описание, материал, цена,
  фото) сохраняются, если у товара совпадает id.
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

MARKUP = 1.2
ROOT = Path(__file__).resolve().parent.parent
SIZE_ORDER = ['XXXS','XXS','XS','S','M','M/L','L','XL','XXL','XXXL','4XL','ONE']

def slugify(s):
    tr = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюяәғқңөұүһі',
      ['a','b','v','g','d','e','e','zh','z','i','y','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','sch','','y','','e','yu','ya','a','g','k','n','o','u','u','h','i']))
    s = ''.join(tr.get(ch, ch) for ch in s.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:60].strip('-')

# ---------- классификация ----------
def gender_of(n):
    l = n.lower()
    if 'детск' in l: return 'kids'
    if 'унисекс' in l: return 'unisex'
    if 'мужск' in l: return 'men'
    if 'женск' in l or 'женщ' in l: return 'women'
    for w in ['платье','юбка','туника','лосины','легинсы','леггинсы','велосипедки','боди','сарафан','блуза','пижама','капор','разлетайки']:
        if w in l: return 'women'
    if any(w in l for w in ['бейсболка','кепка','козырёк','сумка','шоппер','шопер','балаклава','снуд','панама']): return 'unisex'
    return 'women'

CAT_RULES = [
    ('hats',     ['шапка','бейсболка','кепка','козырёк','панама','балаклава','снуд','капор']),
    ('bags',     ['сумка','шоппер','шопер']),
    ('underwear',['трусы','бельев']),
    ('sets',     ['костюм','комплект']),
    ('home',     ['пижама','сорочка','ночная','домашн']),
    ('dresses',  ['платье','сарафан','туника']),
    ('hoodies',  ['толстовка','худи','свитшот','жилет']),
    ('longsleeves',['лонгслив','водолазка','рубашка','блуза']),
    ('pants',    ['брюки','лосины','легинсы','леггинсы']),
    ('shorts',   ['шорты','велосипедки','юбка']),
    ('tops',     ['майка','топ','боди']),
    ('tshirts',  ['футболка','поло']),
]
def category_of(n):
    l = n.lower()
    for cat, words in CAT_RULES:
        if any(w in l for w in words): return cat
    return 'tshirts'

def material_of(n):
    l = n.lower()
    parts = []
    if 'хлоп' in l: parts.append('хлопок')
    if 'эластан' in l: parts.append('эластан')
    if 'флис' in l: parts.append('флис')
    if 'вязан' in l: parts.append('вязаный трикотаж')
    if 'рубчик' in l: parts.append('трикотаж в рубчик')
    if 'мех' in l or 'плюш' in l: parts.append('искусственный мех / плюш')
    if 'джинс' in l: parts.append('деним')
    if 'трикотаж' in l and 'вязаный трикотаж' not in parts: parts.append('трикотаж')
    return ', '.join(dict.fromkeys(parts))

def features_of(n):
    l = n.lower(); f = []
    pairs = [('оверсайз','Свободный крой оверсайз'),('удлин','Удлинённая модель'),('укороч','Укороченная модель'),
             ('с капюшоном','С капюшоном'),('капюшон','С капюшоном'),('утепл','Утеплённая модель'),('начёс','С начёсом'),
             ('спорт','Подходит для спорта и активного отдыха'),('домашн','Для дома и отдыха'),('ночн','Для сна'),
             ('летн','Летняя модель'),('принт','С принтом'),('полоск','В полоску'),('однотон','Однотонная'),
             ('базов','Базовая вещь на каждый день'),('утягив','Утягивающий эффект'),('высокой посадкой','Высокая посадка'),
             ('молни','На молнии'),('липучк','Регулируемая застёжка-липучка'),('металлической застёжке','Металлическая застёжка'),
             ('регулируем','Регулируемый размер'),('сетк','Сетка для вентиляции'),('через плечо','Носится через плечо'),
             ('макси','Длина макси'),('миди','Длина миди'),('мини','Длина мини'),('разрез','С разрезом'),
             ('длинн','Длинный рукав'),('коротк','Короткий рукав'),('стойк','Воротник-стойка'),('пуговиц','Застёжка на пуговицы'),
             ('с ушками','С ушками'),('корейск','В корейском стиле'),('двухцвет','Двухцветная'),('кант','С контрастным кантом'),
             ('стрейч','Тянется (стрейч)'),('вечерн','Подойдёт для вечера'),('повседнев','На каждый день')]
    for k, v in pairs:
        if k in l and v not in f: f.append(v)
    return f

def season_of(n, cat):
    l = n.lower()
    if any(w in l for w in ['утепл','зимн','начёс','флис','шапка','балаклава','мех','вязан','капор']): return 'Осень / зима'
    if any(w in l for w in ['летн','шорты','велосипедки','панама','сарафан','разлетайки']): return 'Весна / лето'
    if cat in ('home','underwear','bags'): return 'Всесезонная'
    return 'Всесезонная'

# ---------- PDF цены ----------
def pdf_prices(pdf):
    txt = subprocess.run(['pdftotext','-layout',str(pdf),'-'],capture_output=True,text=True).stdout
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    res = {}; name = None; idx = {}
    for i, l in enumerate(lines):
        if l.startswith('Всего:'):
            name = lines[i-1]
            idx[name] = idx.get(name, -1) + 1
        m = re.match(r'(\d[\d\s]*) ₸/шт', l)
        if m and name:
            key = (name, idx[name])
            if key not in res: res[key] = int(m.group(1).replace(' ',''))
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx'); ap.add_argument('pdf', nargs='?')
    ap.add_argument('--images', default=None, help='папка с готовыми фото <hash>.webp (по умолчанию images/)')
    a = ap.parse_args()
    import openpyxl
    wb = openpyxl.load_workbook(a.xlsx); ws = wb.active
    sizes = [ws.cell(2, c).value for c in range(2, 14)]
    imgs = {}
    for im in ws._images:
        imgs[im.anchor._from.row + 1] = hashlib.md5(im._data()).hexdigest()[:10]
    prices = pdf_prices(a.pdf) if a.pdf else {}
    old = {}
    cat_path = ROOT / 'data' / 'catalog.json'
    if cat_path.exists():
        old = {p['id']: p for p in json.load(open(cat_path, encoding='utf-8'))['products']}

    products = []; cur = None; seen_names = {}
    for r in range(3, ws.max_row + 1):
        v = [ws.cell(r, c).value for c in range(1, 17)]
        if v[0] is None or str(v[0]).strip().upper() == 'ИТОГО': continue
        if v[14] is not None or v[15] is not None:
            name = str(v[0]).strip()
            n_idx = seen_names.get(name, -1) + 1; seen_names[name] = n_idx
            price = prices.get((name, n_idx)) or prices.get((name, 0)) or round((v[15] or 0) * MARKUP / 10) * 10
            cur = {'name': name, 'price': int(price), 'img': imgs.get(r), 'variants': []}
            products.append(cur)
        else:
            sz = {}
            for i in range(12):
                q = v[1 + i]
                if q:
                    k = sizes[i]
                    if k.startswith('Без размера'): k = 'ONE'
                    sz[k] = sz.get(k, 0) + int(q)
            if sz:
                cur['variants'].append({'color': str(v[0]).strip().capitalize(), 'img': imgs.get(r), 'sizes': sz})

    out = []; used = set()
    for i, p in enumerate(products, 1):
        if not p['variants']: continue
        base = slugify(p['name']); slug = base; k = 2
        while slug in used: slug = f'{base}-{k}'; k += 1
        used.add(slug)
        pid = f'SD{i:03d}'
        cat = category_of(p['name']); g = gender_of(p['name'])
        if not p['img']: p['img'] = next((vv['img'] for vv in p['variants'] if vv['img']), None)
        for vv in p['variants']:
            if not vv['img']: vv['img'] = p['img']  # нет фото цвета — показываем общее фото модели
        for j, vv in enumerate(p['variants'], 1):
            vv['sku'] = f'{pid}-{j:02d}'
            vv['sizes'] = {s: vv['sizes'][s] for s in SIZE_ORDER if s in vv['sizes']}
        item = {
            'id': pid, 'slug': slug, 'name': p['name'], 'category': cat, 'gender': g,
            'price': p['price'], 'old_price': None,
            'material': material_of(p['name']), 'season': season_of(p['name'], cat),
            'features': features_of(p['name']), 'description': '',
            'image': p['img'], 'variants': p['variants'],
        }
        if pid in old:  # сохраняем ручные правки
            for key in ('price','old_price','material','season','features','description','name','category','gender'):
                if old[pid].get(key) not in (None, '', []): item[key] = old[pid][key]
        out.append(item)
    cat_path.parent.mkdir(exist_ok=True)
    json.dump({'_comment': 'Каталог товаров. Можно править цены (price), старую цену (old_price), описание, материал. Остатки по размерам — в variants[].sizes. После правки сайт пересобирается автоматически (GitHub Actions) или командой python build.py',
               'products': out}, open(cat_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'OK: {len(out)} товаров, {sum(len(p["variants"]) for p in out)} цветов -> {cat_path}')

if __name__ == '__main__':
    main()
