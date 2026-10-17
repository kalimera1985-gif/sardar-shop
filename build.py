#!/usr/bin/env python3
"""
Сборщик сайта SARDAR.  Запуск:  python build.py
Берёт config.json + data/catalog.json + images/ и собирает готовый статический сайт в папку site/.
Никаких внешних зависимостей (только стандартная библиотека Python 3.8+).
"""
import csv, html, io, json, os, re, shutil
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xesc

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'site'
CFG = json.load(open(ROOT / 'config.json', encoding='utf-8'))
PRODUCTS = json.load(open(ROOT / 'data' / 'catalog.json', encoding='utf-8'))['products']
SITE = CFG['site_url'].rstrip('/') + '/'
TODAY = date.today().isoformat()
NB = ' '

# ---------------- справочники ----------------
CATS = {  # id: (slug, название, коротко)
    'tshirts':    ('futbolki',        'Футболки и поло',                 'Футболки'),
    'tops':       ('mayki-i-topy',    'Майки и топы',                    'Майки и топы'),
    'longsleeves':('longslivy',       'Лонгсливы, водолазки и рубашки',  'Лонгсливы'),
    'hoodies':    ('hudi-i-svitshoty','Худи, свитшоты и жилеты',         'Худи и жилеты'),
    'dresses':    ('platya',          'Платья, сарафаны и туники',       'Платья'),
    'home':       ('domashnyaya-odezhda','Домашняя одежда и пижамы',     'Для дома'),
    'pants':      ('bryuki-i-losiny', 'Брюки, лосины и леггинсы',        'Брюки и лосины'),
    'shorts':     ('shorty-i-yubki',  'Шорты, велосипедки и юбки',       'Шорты и юбки'),
    'sets':       ('kostyumy',        'Костюмы и комплекты',             'Костюмы'),
    'underwear':  ('belyo',           'Бельё',                           'Бельё'),
    'hats':       ('golovnye-ubory',  'Шапки, кепки и балаклавы',        'Головные уборы'),
    'bags':       ('sumki',           'Сумки-шопперы',                   'Сумки'),
}
GENDERS = {
    'women':  ('zhenskoe',  'Женщинам',  'Женская одежда'),
    'men':    ('muzhskoe',  'Мужчинам',  'Мужская одежда'),
    'kids':   ('detskoe',   'Детям',     'Детская одежда'),
    'unisex': ('uniseks',   'Унисекс',   'Одежда и аксессуары унисекс'),
}
GENDER_FOR = {'women': 'для женщин', 'men': 'для мужчин', 'kids': 'для детей', 'unisex': 'для мужчин и женщин'}
SIZE_ORDER = ['XXXS','XXS','XS','S','M','M/L','L','XL','XXL','XXXL','4XL','ONE']

COLORS = {  # цвет: (hex, семейство для фильтра)
 'алый':('#e0242f','red'),'аметистовый':('#9966cc','purple'),'багровый':('#9b1c2e','red'),'бежевый':('#e3cfb0','beige'),
 'белый':('#ffffff','white'),'бирюзовый':('#30c4b5','blue'),'бордовый':('#7a1f2b','red'),'бронзовый':('#b0793c','beige'),
 'вишневый':('#8f1d3a','red'),'голубой':('#7ec8ef','blue'),'горчичный':('#d4a531','yellow'),'желтый':('#f5d533','yellow'),
 'зеленый':('#3c9a52','green'),'зеленый хаки':('#6b6a3c','green'),'золотистый хаки':('#a69152','green'),'индиго':('#3f3d99','blue'),
 'карамельный':('#c68a52','beige'),'конфетный':('#f59ac0','pink'),'кораллово-розовый':('#f48a8a','pink'),'коралловый':('#ff7f61','pink'),
 'коричневый':('#6d4a2f','beige'),'красный':('#d52b2b','red'),'кремовый':('#f5ead2','white'),'лавандовый':('#b9a7e3','purple'),
 'лазурный':('#2a8fe0','blue'),'лайм':('#b5e03c','green'),'ледяной':('#d7eef5','blue'),'лесной зеленый':('#2e5e3a','green'),
 'лимонный':('#f7ec6e','yellow'),'манго':('#ffaa3b','yellow'),'медный':('#b36a3c','beige'),'молочный':('#f8f3e6','white'),
 'морской':('#1f6f8b','blue'),'мятный':('#a5e3c9','green'),'небесно-голубой':('#9fd8f3','blue'),'оливковый':('#7a7a3a','green'),
 'оранжевый':('#f57c22','yellow'),'пудровый':('#e9c3c0','pink'),'пурпурный':('#8e2a8e','purple'),'разноцветный':('conic-gradient(#e33,#fc3,#3c6,#39f,#c3c,#e33)','multi'),
 'розовый':('#f3a3c0','pink'),'рыжий':('#d0682a','yellow'),'салатовый':('#a8dc5a','green'),'светло-бежевый':('#efe2cc','beige'),
 'светло-голубой':('#bfe3f6','blue'),'светло-коричневый':('#a07a58','beige'),'светло-синий':('#6c9bd6','blue'),'серебряный':('#c7cbd1','grey'),
 'серый':('#9aa1a9','grey'),'серый меланж':('#b5b8bd','grey'),'серый металлик':('#8d939b','grey'),'синий':('#2851b8','blue'),
 'сиреневый':('#c8a2d8','purple'),'темно-бирюзовый':('#14787a','blue'),'темно-зеленый':('#24492f','green'),'темно-розовый':('#d9577e','pink'),
 'темно-серый':('#5a6068','grey'),'темно-синий':('#1d2b5a','blue'),'угольный':('#3a3d42','black'),'фиолетовый':('#6d3fb5','purple'),
 'фуксия':('#d6338a','pink'),'хаки':('#8a8455','green'),'хром':('#a8adb4','grey'),'черный':('#16181c','black'),'шоколадный':('#4e3021','beige'),
}
FAMILIES = [('black','Чёрный','#16181c'),('white','Белый','#ffffff'),('grey','Серый','#9aa1a9'),('beige','Бежевый и коричневый','#d2b48c'),
            ('red','Красный и бордовый','#d52b2b'),('pink','Розовый','#f3a3c0'),('purple','Фиолетовый','#8e6bc9'),('blue','Синий и голубой','#2f7fd6'),
            ('green','Зелёный и хаки','#3c9a52'),('yellow','Жёлтый и оранжевый','#f5c533'),('multi','Разноцветный','conic-gradient(#e33,#fc3,#3c6,#39f,#c3c,#e33)')]
PRICE_BUCKETS = [('0-800','до 800 ₸'),('800-1300','800 – 1 300 ₸'),('1300-2000','1 300 – 2 000 ₸'),('2000-','от 2 000 ₸')]

def chex(name):  return COLORS.get(name.lower(), ('#cccccc', 'multi'))[0]
def cfam(name):  return COLORS.get(name.lower(), ('#cccccc', 'multi'))[1]
def money(n):    return f'{int(n):,}'.replace(',', NB) + NB + '₸'
def e(s):        return html.escape(str(s), quote=True)
def size_label(s, p): return ('Детский' if p['gender'] == 'kids' else 'Единый') if s == 'ONE' else s
def p_url(p):    return f"tovar/{p['slug']}/"
def stock(p):    return sum(sum(v['sizes'].values()) for v in p['variants'])
def p_sizes(p):
    have = {s for v in p['variants'] for s, q in v['sizes'].items() if q > 0}
    return [s for s in SIZE_ORDER if s in have]
def wa_link(text=''):
    num = re.sub(r'\D', '', CFG['whatsapp'])
    return f'https://wa.me/{num}' + (('?text=' + __import__('urllib.parse').parse.quote(text)) if text else '')
def lower_first(s): return s[:1].lower() + s[1:]

# ---------------- тексты для товара ----------------
CAT_PHRASE = {
 'tshirts':'футболка на каждый день', 'tops':'лёгкая база для гардероба', 'longsleeves':'вещь с длинным рукавом для многослойных образов',
 'hoodies':'тёплый верхний слой', 'dresses':'платье на каждый день', 'home':'удобная одежда для дома и сна',
 'pants':'низ для прогулок, спорта и дома', 'shorts':'лёгкий низ для тёплой погоды и тренировок', 'sets':'готовый комплект — не нужно подбирать пару',
 'underwear':'базовое бельё', 'hats':'аксессуар, который защищает и завершает образ', 'bags':'вместительная сумка на каждый день'}

def description(p):
    if p.get('description'): return p['description']
    colors = [v['color'] for v in p['variants']]
    sizes = [size_label(s, p) for s in p_sizes(p)]
    parts = []
    parts.append(f"{p['name']} — {CAT_PHRASE.get(p['category'], 'одежда')} {GENDER_FOR[p['gender']]}.")
    if p.get('features'):
        parts.append('Особенности: ' + ', '.join(lower_first(f) for f in p['features']) + '.')
    if p.get('material'):
        parts.append(f"Материал: {p['material']}.")
    if len(colors) > 1:
        parts.append(f"В наличии {len(colors)} {plural(len(colors), 'цвет', 'цвета', 'цветов')}: " + ', '.join(c.lower() for c in colors) + '.')
    else:
        parts.append(f"Цвет: {colors[0].lower()}.")
    if sizes == ['Единый'] or sizes == ['Детский']:
        parts.append('Размер единый.' if sizes == ['Единый'] else 'Детский размер — точный рост уточните у нас в WhatsApp.')
    else:
        parts.append('Размеры в наличии: ' + ', '.join(sizes) + '.')
    parts.append(f"Вещь новая, со склада в Астане. Доставим курьером {CFG['delivery']['carrier']} по Астане, в Косшы и пригород за 1–2 дня.")
    return ' '.join(parts)

def plural(n, a, b, c):
    n = abs(n) % 100; n1 = n % 10
    if 10 < n < 20: return c
    if 1 < n1 < 5: return b
    if n1 == 1: return a
    return c

def care(p):
    m = (p.get('material') or '').lower()
    if p['category'] == 'hats' and ('вязан' in m or 'мех' in m or 'флис' in m):
        return 'Ручная или деликатная стирка при 30 °C, не выкручивать. Сушить в расправленном виде, вдали от батареи.'
    if p['category'] == 'bags':
        return 'Стирка при 30 °C или чистка влажной губкой. Не отбеливать. Гладить с изнанки, не задевая принт.'
    base = 'Стирка при 30 °C с вещами похожего цвета, наизнанку. Не отбеливать. Сушить в расправленном виде. Гладить при средней температуре.'
    if 'хлоп' in m: base += ' Хлопок может немного сесть при горячей стирке — не превышайте 40 °C.'
    return base + ' Точные рекомендации — на ярлыке изделия.'

# ---------------- общие части страницы ----------------
ICON_SVG = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M9 4h19a2 2 0 0 1 2 2v20a2 2 0 0 1-2 2H9L2 16z" fill="#ffc61a"/><circle cx="9.5" cy="16" r="2.4" fill="#fff"/><path d="M15.5 20.6c.9.8 2.2 1.3 3.6 1.3 2 0 3.3-1 3.3-2.6 0-3.4-6.3-2.2-6.3-5.6 0-1.5 1.3-2.6 3.1-2.6 1.2 0 2.3.4 3 1" fill="none" stroke="#13233a" stroke-width="2.2" stroke-linecap="round"/></svg>'
CART_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 7h12l-1 13H7z"/><path d="M9 7a3 3 0 0 1 6 0"/></svg>'
WA_SVG = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3a13 13 0 0 0-11.2 19.6L3 29l6.6-1.7A13 13 0 1 0 16 3zm0 23.6a10.6 10.6 0 0 1-5.4-1.5l-.4-.2-3.9 1 1-3.8-.3-.4A10.6 10.6 0 1 1 16 26.6zm5.8-7.9c-.3-.2-1.9-.9-2.2-1s-.5-.2-.7.2-.8 1-1 1.2-.4.2-.7.1a8.7 8.7 0 0 1-4.3-3.8c-.3-.6.3-.5.9-1.7.1-.2 0-.4 0-.5l-1-2.4c-.3-.6-.5-.5-.7-.5h-.6a1.2 1.2 0 0 0-.9.4 3.7 3.7 0 0 0-1.1 2.7 6.5 6.5 0 0 0 1.3 3.4 14.8 14.8 0 0 0 5.7 5c2.1.9 2.9 1 4 .8a3.4 3.4 0 0 0 2.2-1.6 2.8 2.8 0 0 0 .2-1.6c-.1-.1-.3-.2-.6-.3z"/></svg>'
CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m5 12 4.5 4.5L19 7"/></svg>'
TRUCK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 6h11v10H3zM14 9h4l3 3v4h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></svg>'
RETURN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 9h11a5 5 0 0 1 0 10H8"/><path d="m8 5-4 4 4 4"/></svg>'

def header(r, active=''):
    nav = [('katalog/zhenskoe/', 'Женщинам', 'women'), ('katalog/muzhskoe/', 'Мужчинам', 'men'),
           ('katalog/golovnye-ubory/', 'Аксессуары', 'acc'), ('dostavka/', 'Доставка', 'dost')]
    free = CFG['delivery'].get('free_from')
    note = f"<span class=\"wide\">Цены — за товар. </span>Доставка {CFG['delivery']['carrier']}<span class=\"wide\"> по Астане и пригороду</span> — <b>оплачивается отдельно</b>" if not free else f"Доставка {CFG['delivery']['carrier']}<span class=\"wide\"> по Астане и пригороду</span> — <b>бесплатно от {money(free)}</b>"
    return f'''<a class="sr" href="#main">Перейти к содержимому</a>
<div class="top-note">{note}</div>
<header class="hdr"><div class="wrap">
 <a class="logo" href="{r}" aria-label="{e(CFG['store_name'])} — на главную">{ICON_SVG}<span>{e(CFG['store_name'])}</span></a>
 <nav class="nav" aria-label="Разделы">{''.join(f'<a href="{r}{u}"' + (' aria-current="page"' if k == active else '') + f'>{t}</a>' for u, t, k in nav)}</nav>
 <form class="hdr-search" role="search" action="{r}katalog/" method="get"><label class="sr" for="q-{active or 'x'}">Поиск по товарам</label><input id="q-{active or 'x'}" name="q" type="search" placeholder="Платье, худи, кепка…" autocomplete="off"></form>
 <a class="cart-btn" href="{r}korzina/" data-open-cart aria-label="Корзина">{CART_SVG}<span class="lbl">Корзина</span><span class="cnt" data-cart-count>0</span></a>
</div></header>'''

def footer(r):
    s = CFG['seller']
    cats = ''.join(f'<li><a href="{r}katalog/{v[0]}/">{v[2]}</a></li>' for k, v in list(CATS.items())[:8])
    contacts = [f'<li><a href="{wa_link()}" rel="noopener">WhatsApp: {e(CFG["phone_display"])}</a></li>',
                f'<li><a href="tel:+{re.sub(r"[^0-9]", "", CFG["phone_display"])}">Позвонить</a></li>']
    if CFG.get('telegram'): contacts.append(f'<li><a href="https://t.me/{e(CFG["telegram"].lstrip("@"))}" rel="noopener">Telegram</a></li>')
    if CFG.get('instagram'): contacts.append(f'<li><a href="https://instagram.com/{e(CFG["instagram"].lstrip("@"))}" rel="noopener">Instagram</a></li>')
    if CFG.get('email'): contacts.append(f'<li><a href="mailto:{e(CFG["email"])}">{e(CFG["email"])}</a></li>')
    contacts.append(f'<li>{e(CFG["work_hours"])}</li>')
    return f'''<footer class="ftr"><div class="wrap">
 <div class="cols">
  <div><a class="logo" href="{r}">{ICON_SVG}<span>{e(CFG['store_name'])}</span></a><p>{e(CFG['tagline'])}</p></div>
  <div><h3>Каталог</h3><ul>{cats}</ul></div>
  <div><h3>Покупателям</h3><ul><li><a href="{r}dostavka/">Доставка и оплата</a></li><li><a href="{r}dostavka/#vozvrat">Обмен и возврат</a></li><li><a href="{r}razmery/">Таблица размеров</a></li><li><a href="{r}korzina/">Корзина</a></li><li><a href="{r}kontakty/">Контакты</a></li></ul></div>
  <div><h3>Связаться</h3><ul>{''.join(contacts)}</ul></div>
 </div>
 <div class="legal">{e(s['legal_name'])}{(', БИН ' + e(s['bin'])) if s.get('bin') else ''} · {e(s['address'])} · Цены указаны в тенге. Данные о товарах для поисковиков и ИИ-ассистентов: <a href="{r}llms.txt">llms.txt</a>, <a href="{r}data/products.json">products.json</a>, <a href="{r}data/products.csv">products.csv</a></div>
</div></footer>
<a class="wa-float" href="{wa_link('Здравствуйте! Вопрос по товару на сайте ' + CFG['store_name'])}" rel="noopener" aria-label="Написать в WhatsApp">{WA_SVG}</a>
<div class="drawer" id="drawer" role="dialog" aria-modal="true" aria-label="Корзина">
 <div class="shade"></div>
 <div class="panel"><header><h2>Корзина</h2><button type="button" class="x" aria-label="Закрыть">×</button></header>
  <div class="items"></div>
  <footer><div data-free></div><div class="sum-row total"><span>Товары</span><span data-sub></span></div><p class="size-hint" style="margin:0">Доставка СДЭК оплачивается отдельно</p>
   <a class="btn sun block" href="{r}korzina/">Оформить заказ</a><button type="button" class="btn alt block" onclick="document.querySelector('#drawer .x').click()">Продолжить покупки</button></footer>
 </div>
</div>'''

def page(path, title, desc, body, active='', jsonld=None, og_image=None, robots='index,follow', extra_head=''):
    depth = path.count('/') if path else 0
    r = '../' * depth
    canon = SITE + path
    og = SITE + (og_image or 'og.jpg')
    lds = ''.join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    doc = f'''<!doctype html>
<html lang="ru" data-root="{r}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{e(CFG['store_name'])}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}"><meta property="og:image" content="{og}"><meta property="og:locale" content="ru_KZ">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#13233a">
<link rel="icon" href="{r}favicon.svg" type="image/svg+xml">
<link rel="alternate" type="text/plain" title="Описание магазина для ИИ" href="{r}llms.txt">
<link rel="alternate" type="application/json" title="Каталог товаров (JSON)" href="{r}data/products.json">
<link rel="preload" href="{r}assets/fonts/onest-cyrillic-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{r}assets/fonts/unbounded-cyrillic-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{r}assets/style.css?v={VER}">
{extra_head}{lds}
</head>
<body>
{header(r, active)}
<main id="main">
{body.replace('{R}', r)}
</main>
{footer(r)}
<script src="{r}assets/catalog.js?v={VER}"></script>
<script src="{r}assets/app.js?v={VER}"></script>
</body>
</html>'''
    out = OUT / path / 'index.html' if path and not path.endswith('.html') else OUT / (path or 'index.html')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding='utf-8')

# ---------------- карточки и каталог ----------------
def card(p, i):
    colors = [v['color'] for v in p['variants']]
    st = stock(p)
    sizes = p_sizes(p)
    fams = sorted({cfam(c) for c in colors})
    search = ' '.join([p['name'], CATS[p['category']][1], GENDERS[p['gender']][1], p['id']] + colors).lower()
    dots = ''.join(f'<i style="background:{chex(c)}"></i>' for c in colors[:5])
    more = f'{len(colors)} {plural(len(colors), "цвет", "цвета", "цветов")}' if len(colors) > 1 else colors[0]
    badge = '<span class="badge low">Последние</span>' if st <= 10 else ''
    sz = ' '.join(size_label(s, p) for s in sizes)
    old = f'<s>{money(p["old_price"])}</s>' if p.get('old_price') else ''
    return f'''<a class="card" href="{{R}}{p_url(p)}" data-id="{p['id']}" data-i="{i}" data-g="{p['gender']}" data-c="{p['category']}" data-s="{' '.join(sizes)}" data-cf="{' '.join(fams)}" data-p="{p['price']}" data-vc="{len(colors)*10+len(sizes)}" data-n="{e(search)}">
 <div class="ph"><img src="{{R}}images/{p['image']}.webp" alt="{e(p['name'])}" loading="lazy" width="268" height="360">{badge}<span class="tag">{money(p['price'])}{old}</span></div>
 <h3>{e(p['name'])}</h3>
 <div class="meta"><span class="dots">{dots}</span><span>{e(more)}</span></div>
 <div class="sizes">{e(sz)}</div>
</a>'''

def catalog_block(prods, heading, preset='', h_tag='h2', intro=''):
    present_c = [k for k in CATS if any(p['category'] == k for p in prods)]
    present_g = [k for k in GENDERS if any(p['gender'] == k for p in prods)]
    present_s = [s for s in SIZE_ORDER if any(s in p_sizes(p) for p in prods)]
    present_f = [f for f in FAMILIES if any(cfam(v['color']) == f[0] for p in prods for v in p['variants'])]
    def chips(key, items):
        return '<div class="chips">' + ''.join(f'<button type="button" class="chip{" size" if key == "s" else ""}" data-f="{key}" data-v="{v}" aria-pressed="false">{lab}</button>' for v, lab in items) + '</div>'
    sw = '<div class="chips">' + ''.join(f'<button type="button" class="chip" data-f="cf" data-v="{k}" aria-pressed="false"><span class="sw" style="background:{h}"></span>{n}</button>' for k, n, h in present_f) + '</div>'
    filt = f'''<aside class="filters" aria-label="Фильтры">
 <div class="f-top"><h2 style="font-size:20px;margin:0">Фильтры</h2><button type="button" class="x f-close" aria-label="Закрыть фильтры">×</button></div>
 {'<div class="f-group"><h3>Для кого</h3>' + chips('g', [(k, GENDERS[k][1]) for k in present_g]) + '</div>' if len(present_g) > 1 else ''}
 {'<div class="f-group"><h3>Категория</h3>' + chips('c', [(k, CATS[k][2]) for k in present_c]) + '</div>' if len(present_c) > 1 else ''}
 <div class="f-group"><h3>Размер</h3>{chips('s', [(s, 'Единый' if s == 'ONE' else s) for s in present_s])}<p class="size-hint"><a href="{{R}}razmery/">Как выбрать размер</a></p></div>
 <div class="f-group"><h3>Цвет</h3>{sw}</div>
 <div class="f-group"><h3>Цена</h3>{chips('pr', PRICE_BUCKETS)}</div>
 <div class="f-group"><button type="button" class="link-btn" data-reset>Сбросить фильтры</button></div>
 <button type="button" class="btn sun f-apply">Показать</button>
</aside>'''
    cards = '\n'.join(card(p, i) for i, p in enumerate(prods))
    return f'''<section class="sect" id="catalog" data-preset="{preset}" aria-labelledby="cat-h"><div class="wrap">
 <div class="sect-head"><{h_tag} id="cat-h">{e(heading)}</{h_tag}></div>{intro}
 <div class="cat-layout">{filt}
  <div>
   <div class="tools"><span class="count" data-count>{len(prods)} товаров</span>
    <button type="button" class="chip f-open">Фильтры</button>
    <label class="sr" for="sort">Сортировка</label><select id="sort"><option value="">По умолчанию</option><option value="cheap">Сначала дешевле</option><option value="expensive">Сначала дороже</option><option value="choice">Больше цветов и размеров</option></select>
   </div>
   <div class="grid">{cards}</div>
   <div class="empty" hidden><p>По этим фильтрам ничего не нашлось.</p><button type="button" class="btn alt" data-reset>Сбросить фильтры</button></div>
  </div>
 </div>
</div></section>'''

# ---------------- JSON-LD ----------------
def org_ld():
    s = CFG['seller']
    return {'@context': 'https://schema.org', '@type': 'OnlineStore', '@id': SITE + '#store', 'name': CFG['store_name'],
            'legalName': s['legal_name'], 'url': SITE, 'logo': SITE + 'favicon.svg', 'image': SITE + 'og.jpg',
            'description': CFG['tagline'], 'telephone': CFG['phone_display'],
            'address': {'@type': 'PostalAddress', 'addressLocality': s['city'], 'addressCountry': 'KZ', 'streetAddress': s['address']},
            'areaServed': [{'@type': 'City', 'name': z['name']} for z in CFG['delivery']['zones'] if z['id'] != 'kz'] + [{'@type': 'Country', 'name': 'Казахстан'}],
            'currenciesAccepted': 'KZT', 'paymentAccepted': ', '.join(CFG['payment_methods']),
            'contactPoint': {'@type': 'ContactPoint', 'telephone': CFG['phone_display'], 'contactType': 'customer service', 'availableLanguage': ['ru', 'kk']}}

def shipping_ld():
    out = []
    for z in CFG['delivery']['zones']:
        if z['price'] is None: continue
        out.append({'@type': 'OfferShippingDetails', 'shippingLabel': f"{CFG['delivery']['carrier']}, {z['name']}",
                    'shippingRate': {'@type': 'MonetaryAmount', 'value': z['price'], 'currency': 'KZT'},
                    'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'KZ', 'addressRegion': z['name']},
                    'deliveryTime': {'@type': 'ShippingDeliveryTime', 'handlingTime': {'@type': 'QuantitativeValue', 'minValue': 0, 'maxValue': 1, 'unitCode': 'DAY'},
                                     'transitTime': {'@type': 'QuantitativeValue', 'minValue': 1, 'maxValue': 3, 'unitCode': 'DAY'}}})
        break
    return out

def return_ld():
    return {'@type': 'MerchantReturnPolicy', 'applicableCountry': 'KZ', 'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
            'merchantReturnDays': CFG['returns_days'], 'returnMethod': 'https://schema.org/ReturnByMail', 'returnFees': 'https://schema.org/ReturnShippingFees'}

def product_ld(p):
    url = SITE + p_url(p)
    variants = []
    for v in p['variants']:
        for s, q in v['sizes'].items():
            variants.append({'@type': 'Product', 'sku': f"{v['sku']}-{s}", 'name': f"{p['name']}, {v['color'].lower()}, размер {size_label(s, p)}",
                             'color': v['color'], 'size': size_label(s, p), 'image': SITE + f"images/{v['img']}.webp",
                             'offers': {'@type': 'Offer', 'url': url + f"?c={v['sku']}", 'price': p['price'], 'priceCurrency': 'KZT',
                                        'availability': 'https://schema.org/InStock' if q > 0 else 'https://schema.org/OutOfStock',
                                        'itemCondition': 'https://schema.org/NewCondition', 'inventoryLevel': {'@type': 'QuantitativeValue', 'value': q},
                                        'seller': {'@id': SITE + '#store'}, 'shippingDetails': shipping_ld(), 'hasMerchantReturnPolicy': return_ld()}})
    audience = {'women': 'female', 'men': 'male', 'kids': None, 'unisex': 'unisex'}[p['gender']]
    ld = {'@context': 'https://schema.org', '@type': 'ProductGroup', 'productGroupID': p['id'], 'name': p['name'], 'url': url,
          'description': description(p), 'category': f"Одежда > {GENDERS[p['gender']][2]} > {CATS[p['category']][1]}",
          'image': [SITE + f"images/{v['img']}.webp" for v in p['variants']][:10], 'variesBy': ['https://schema.org/color', 'https://schema.org/size'],
          'brand': {'@type': 'Brand', 'name': 'Без бренда'}, 'hasVariant': variants,
          'offers': {'@type': 'AggregateOffer', 'lowPrice': p['price'], 'highPrice': p['price'], 'priceCurrency': 'KZT', 'offerCount': len(variants)}}
    if audience: ld['audience'] = {'@type': 'PeopleAudience', 'suggestedGender': audience}
    if p['gender'] == 'kids': ld['audience'] = {'@type': 'PeopleAudience', 'suggestedMaxAge': 14}
    if p.get('material'): ld['material'] = p['material']
    return ld

def crumbs_ld(items):
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList',
            'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + u} for i, (n, u) in enumerate(items)]}

def itemlist_ld(prods, name):
    return {'@context': 'https://schema.org', '@type': 'ItemList', 'name': name, 'numberOfItems': len(prods),
            'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'url': SITE + p_url(p), 'name': p['name']} for i, p in enumerate(prods)]}

# ---------------- FAQ (используется на главной и в «Доставке») ----------------
def faq_items():
    d = CFG['delivery']; z0 = d['zones'][0]
    sub = [z['name'] for z in d['zones'] if z['id'] not in ('astana', 'kz')]
    free = f" При заказе от {money(d['free_from'])} доставка по Астане и пригороду бесплатная." if d.get('free_from') else ''
    return [
     ('Как оформить заказ?', 'Выберите цвет и размер в карточке товара, добавьте в корзину и нажмите «Оформить заказ». Заполните имя, телефон и адрес — заказ уйдёт нам в WhatsApp. Мы подтвердим наличие и время доставки в течение рабочего дня.'),
     ('Куда вы доставляете?', f"Курьером {d['carrier']} по Астане и в пригород: {', '.join(sub)}. В другие города Казахстана тоже отправляем через {d['carrier']} — стоимость по тарифу перевозчика."),
     ('Сколько стоит доставка?', f"Цена на сайте — это цена товара. Доставка {d['carrier']} оплачивается отдельно по тарифу перевозчика: стоимость зависит от района и веса посылки, мы назовём её при подтверждении заказа.{free}"),
     ('Как быстро привезут?', 'По Астане обычно 1–2 дня после подтверждения заказа, в пригород — 1–3 дня, в регионы — 2–7 дней.'),
     ('Как оплатить?', ' / '.join(CFG['payment_methods']) + '.'),
     ('Вещи новые?', 'Да, все вещи новые, со склада в Астане. Это остатки партий, поэтому цены ниже обычных, а количество в каждом размере ограничено — на сайте показан точный остаток.'),
     ('Можно вернуть или обменять?', f"Да, в течение {CFG['returns_days']} дней, если вещь не носили и сохранены ярлыки. Нижнее бельё надлежащего качества обмену и возврату не подлежит. Напишите нам в WhatsApp — подскажем, как оформить."),
     ('Как подобрать размер?', 'Посмотрите таблицу размеров на сайте и сравните со своими замерами. Если сомневаетесь — напишите в WhatsApp модель и ваши параметры, подскажем.'),
     ('Есть ли оптовые цены?', CFG.get('wholesale_note') or 'Напишите нам в WhatsApp.'),
    ]

def faq_html(items):
    return '<div class="faq">' + ''.join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in items) + '</div>'

def faq_ld(items):
    return {'@context': 'https://schema.org', '@type': 'FAQPage',
            'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in items]}

def zones_html():
    d = CFG['delivery']
    return '<ul class="zones">' + ''.join(f'<li><b>{e(z["name"])}</b>{money(z["price"]) if z["price"] is not None else "по тарифу СДЭК"} · {e(z["eta"])}</li>' for z in d['zones']) + '</ul>'

def steps_html():
    return '''<ol class="steps">
 <li><b>Выберите вещь</b><span>Фильтруйте по размеру, цвету и цене. В карточке — точный остаток по каждому размеру.</span></li>
 <li><b>Положите в корзину</b><span>Сразу видна итоговая сумма за товары. Доставка СДЭК оплачивается отдельно.</span></li>
 <li><b>Отправьте заказ</b><span>Заполните адрес — заказ придёт нам в WhatsApp. Мы подтвердим его в течение рабочего дня.</span></li>
 <li><b>Получите курьером</b><span>СДЭК привезёт заказ по Астане за 1–2 дня. Оплата — Kaspi или при получении.</span></li>
</ol>'''

# ---------------- страницы ----------------
def build_home():
    total = sum(stock(p) for p in PRODUCTS)
    ncol = sum(len(p['variants']) for p in PRODUCTS)
    minp = min(p['price'] for p in PRODUCTS)
    # фото для «стопки» в hero — самые ходовые позиции
    top = sorted(PRODUCTS, key=stock, reverse=True)
    pile = [top[1], top[0], top[4]]
    tiles = []
    for k, (slug, name, short) in CATS.items():
        ps = [p for p in PRODUCTS if p['category'] == k]
        if not ps: continue
        rep = max(ps, key=stock)
        tiles.append(f'<a class="cat" href="{{R}}katalog/{slug}/"><b>{short}</b><small>{len(ps)} {plural(len(ps), "модель", "модели", "моделей")}</small><img src="{{R}}images/{rep["image"]}.webp" alt="" loading="lazy"></a>')
    genders = ''.join(f'<a class="chip" href="{{R}}katalog/{v[0]}/">{v[1]} <span class="n">{sum(1 for p in PRODUCTS if p["gender"] == k)}</span></a>' for k, v in GENDERS.items() if any(p['gender'] == k for p in PRODUCTS))
    body = f'''
<section class="hero"><div class="wrap">
 <div>
  <h1>Одежда со склада в Астане</h1>
  <p class="lead">Новые футболки, платья, худи, пижамы и кепки по ценам остатков. Цена на сайте — окончательная цена вещи. Привезём курьером СДЭК по Астане и в Косшы за 1–2 дня.</p>
  <div class="hero-cta"><a class="btn sun" href="#catalog">Смотреть каталог</a><a class="btn alt" href="{wa_link('Здравствуйте! Хочу подобрать одежду')}" rel="noopener">Подобрать в WhatsApp</a></div>
  <ul class="facts"><li><b>{len(PRODUCTS)}</b> моделей</li><li><b>{ncol}</b> цветов</li><li><b>{total:,}</b> вещей в наличии</li></ul>
 </div>
 <div class="hero-pile" aria-hidden="true">{''.join(f'<img src="{{R}}images/{p["image"]}.webp" alt="" width="268" height="360">' for p in pile)}<span class="tag">от {money(minp)}</span></div>
</div></section>
<section class="sect" aria-labelledby="cats-h"><div class="wrap">
 <div class="sect-head"><h2 id="cats-h">Категории</h2></div>
 <div class="genders">{genders}</div>
 <div class="cats">{''.join(tiles)}</div>
</div></section>
{catalog_block(PRODUCTS, 'Весь каталог')}
<section class="sect" aria-labelledby="how-h"><div class="wrap">
 <div class="sect-head"><h2 id="how-h">Как заказать</h2></div>
 {steps_html()}
</div></section>
<section class="sect" aria-labelledby="dz-h"><div class="wrap">
 <div class="sect-head"><h2 id="dz-h">Доставка по Астане и пригороду</h2><a href="{{R}}dostavka/">Подробнее</a></div>
 {zones_html()}
</div></section>
<section class="sect"><div class="wrap"><div class="band">
 <div><h2 style="margin-bottom:.3em">Опт от 10 штук</h2><p>{e(CFG['wholesale_note'])}</p></div>
 <a class="btn sun" href="{wa_link('Здравствуйте! Интересует опт.')}" rel="noopener">Написать в WhatsApp</a>
</div></div></section>
<section class="sect" aria-labelledby="faq-h"><div class="wrap">
 <div class="sect-head"><h2 id="faq-h">Частые вопросы</h2></div>
 {faq_html(faq_items())}
</div></section>'''.replace('{total:,}', f'{total:,}'.replace(',', NB))
    body = body.replace(f'{total:,}', f'{total:,}'.replace(',', NB))
    website = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': CFG['store_name'], 'url': SITE, 'inLanguage': 'ru',
               'potentialAction': {'@type': 'SearchAction', 'target': SITE + 'katalog/?q={search_term_string}', 'query-input': 'required name=search_term_string'}}
    page('', CFG['store_title'], f"{CFG['tagline']} {len(PRODUCTS)} моделей, цены от {money(minp)}.", body,
         jsonld=[org_ld(), website, itemlist_ld(PRODUCTS, 'Каталог ' + CFG['store_name']), faq_ld(faq_items())])

def build_catalog_pages():
    page('katalog/', f"Каталог одежды — {CFG['store_name']}, Астана", f"Все {len(PRODUCTS)} моделей одежды и аксессуаров в наличии. Фильтр по размеру, цвету и цене. Доставка СДЭК по Астане.",
         catalog_block(PRODUCTS, 'Каталог', h_tag='h1'), jsonld=[itemlist_ld(PRODUCTS, 'Каталог'), crumbs_ld([('Главная', ''), ('Каталог', 'katalog/')])])
    for k, (slug, name, short) in CATS.items():
        ps = [p for p in PRODUCTS if p['category'] == k]
        if not ps: continue
        lo = min(p['price'] for p in ps)
        intro = f'<p style="color:var(--ink-2);max-width:70ch">{e(name)} — {len(ps)} {plural(len(ps), "модель", "модели", "моделей")} в наличии, цены от {money(lo)}. Доставка {CFG["delivery"]["carrier"]} по Астане и пригороду.</p>'
        page(f'katalog/{slug}/', f"{name} купить в Астане — от {money(lo)} | {CFG['store_name']}",
             f"{name}: {len(ps)} моделей в наличии, цены от {money(lo)}. Все размеры и цвета на сайте, доставка СДЭК по Астане, Косшы и пригороду.",
             catalog_block(ps, name, h_tag='h1', intro=intro), active='acc' if k in ('hats', 'bags') else '',
             jsonld=[itemlist_ld(ps, name), crumbs_ld([('Главная', ''), ('Каталог', 'katalog/'), (name, f'katalog/{slug}/')])])
    for k, (slug, short, name) in GENDERS.items():
        ps = [p for p in PRODUCTS if p['gender'] == k or (p['gender'] == 'unisex' and k in ('women', 'men'))]
        if not ps: continue
        lo = min(p['price'] for p in ps)
        intro = f'<p style="color:var(--ink-2);max-width:70ch">{e(name)}: {len(ps)} {plural(len(ps), "модель", "модели", "моделей")}, цены от {money(lo)}.</p>'
        page(f'katalog/{slug}/', f"{name} в Астане — от {money(lo)} | {CFG['store_name']}",
             f"{name} со склада в Астане: {len(ps)} моделей, цены от {money(lo)}. Доставка СДЭК по Астане и пригороду.",
             catalog_block(ps, name, h_tag='h1', intro=intro), active=k,
             jsonld=[itemlist_ld(ps, name), crumbs_ld([('Главная', ''), ('Каталог', 'katalog/'), (name, f'katalog/{slug}/')])])

def size_tables(p=None):
    women = [('XXXS','38','76','58','84'),('XXS','40','80','62','88'),('XS','42','84','66','92'),('S','44','88','70','96'),('M','46','92','74','100'),('M/L','46–48','92–96','74–78','100–104'),
             ('L','48','96','78','104'),('XL','50','100','82','108'),('XXL','52','104','86','112'),('XXXL','54','108','90','116'),('4XL','56','112','94','120')]
    men = [('XS','44','88','76','—'),('S','46','92','80','—'),('M','48','96','84','—'),('L','50','100','88','—'),('XL','52','104','92','—'),('XXL','54','108','96','—'),('XXXL','56','112','100','—'),('4XL','58','116','104','—')]
    def tbl(rows, cap, hips=True):
        only = set(p_sizes(p)) if p else None
        rows = [r for r in rows if not only or r[0] in only] or rows
        head = '<tr><th>Размер</th><th>RU</th><th>Грудь, см</th><th>Талия, см</th>' + ('<th>Бёдра, см</th>' if hips else '') + '</tr>'
        body = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in (r if hips else r[:4])) + '</tr>' for r in rows)
        return f'<div class="tbl-wrap"><table class="size-table"><caption class="sr">{cap}</caption><thead>{head}</thead><tbody>{body}</tbody></table></div>'
    return tbl(women, 'Женские размеры'), tbl(men, 'Мужские размеры', hips=False)

def build_product(p, idx):
    url = p_url(p); cname, cslug = CATS[p['category']][1], CATS[p['category']][0]
    v0 = p['variants'][0]
    colors_btn = ''.join(f'<button type="button" data-sku="{v["sku"]}" aria-pressed="{"true" if i == 0 else "false"}" title="{e(v["color"])}" aria-label="Цвет: {e(v["color"])}"><img src="{{R}}images/{v["img"]}.webp" alt="" loading="lazy"><i style="background:{chex(v["color"])}"></i></button>' for i, v in enumerate(p['variants']))
    thumbs = ''.join(f'<button type="button" data-sku="{v["sku"]}" aria-current="{"true" if i == 0 else "false"}" aria-label="Фото, цвет {e(v["color"])}"><img src="{{R}}images/{v["img"]}.webp" alt="" loading="lazy"></button>' for i, v in enumerate(p['variants']))
    sizes_all = p_sizes(p)
    stock_rows = ''.join('<tr><td>' + e(v['color']) + '</td>' + ''.join(
        f'<td class="{"" if v["sizes"].get(s) else "z"}">{v["sizes"].get(s, 0) or "—"}</td>' for s in sizes_all) + '</tr>' for v in p['variants'])
    stock_tbl = f'<div class="tbl-wrap"><table class="stock"><caption class="sr">Остатки по цветам и размерам, шт</caption><thead><tr><th>Цвет / размер</th>{"".join(f"<th>{size_label(s, p)}</th>" for s in sizes_all)}</tr></thead><tbody>{stock_rows}</tbody></table></div>'
    spec = [('Артикул', f'<span data-sku-text>{v0["sku"]}</span> (модель {p["id"]})'), ('Категория', cname), ('Для кого', GENDERS[p['gender']][1]),
            ('Материал', e(p['material']) if p.get('material') else 'Уточняйте в WhatsApp — пришлём фото ярлыка'),
            ('Сезон', e(p['season'])), ('Цвета', e(', '.join(v['color'] for v in p['variants']))),
            ('Размеры', e(', '.join(size_label(s, p) for s in sizes_all))), ('Особенности', e(', '.join(p['features'])) if p.get('features') else '—'),
            ('Состояние', 'Новая вещь'), ('Всего в наличии', f'{stock(p)} шт')]
    spec_html = '<table class="spec">' + ''.join(f'<tr><th>{a}</th><td>{b}</td></tr>' for a, b in spec) + '</table>'
    one_size = sizes_all in (['ONE'],)
    wt, mt = size_tables(p)
    size_block = ('<p>Размер единый — подходит на большинство. Если нужно точнее, напишите нам, пришлём замеры.</p>' if one_size else
                  (mt if p['gender'] == 'men' else wt) + f'<p class="size-hint">Таблица ориентировочная: посадка моделей отличается. Нужны точные замеры этой модели — <a href="{wa_link("Пришлите замеры: " + p["name"] + " (" + p["id"] + ")")}" rel="noopener">спросите в WhatsApp</a>. <a href="{{R}}razmery/">Все таблицы размеров</a></p>')
    d = CFG['delivery']; z0 = d['zones'][0]
    old = f'<s>{money(p["old_price"])}</s>' if p.get('old_price') else ''
    related = [q for q in PRODUCTS if q['category'] == p['category'] and q['id'] != p['id']]
    related = sorted(related, key=lambda q: (q['gender'] != p['gender'], -stock(q)))[:8]
    rel_html = f'''<section class="sect" aria-labelledby="rel-h"><div class="wrap"><div class="sect-head"><h2 id="rel-h">Похожие товары</h2><a href="{{R}}katalog/{cslug}/">Все {e(CATS[p['category']][2].lower())}</a></div>
<div class="grid">{''.join(card(q, i) for i, q in enumerate(related))}</div></div></section>''' if related else ''
    free_txt = f', бесплатно от {money(d["free_from"])}' if d.get('free_from') else ''
    body = f'''<div class="wrap">
<nav aria-label="Навигация"><ol class="crumbs"><li><a href="{{R}}">Главная</a></li><li><a href="{{R}}katalog/">Каталог</a></li><li><a href="{{R}}katalog/{cslug}/">{e(cname)}</a></li><li aria-current="page">{e(p['name'])}</li></ol></nav>
<article class="pdp" id="pdp" data-id="{p['id']}">
 <div class="gal">
  <div class="gal-main"><img src="{{R}}images/{v0['img']}.webp" alt="{e(p['name'])}, цвет {e(v0['color'])}" width="268" height="360"></div>
  {'<div class="gal-thumbs">' + thumbs + '</div>' if len(p['variants']) > 1 else ''}
 </div>
 <div>
  <h1>{e(p['name'])}</h1>
  <div class="sku">Артикул <span data-sku-text>{v0['sku']}</span> · {stock(p)} шт в наличии</div>
  <div class="price-row"><span class="tag">{money(p['price'])}{old}</span><small>цена за 1 шт, доставка отдельно</small></div>
  <div class="opt"><h2>Цвет: <span data-color-name>{e(v0['color'])}</span></h2><div class="colors">{colors_btn}</div></div>
  <div class="opt"><h2>Размер</h2><div class="size-btns">{''.join(f'<button type="button">{size_label(s, p)}</button>' for s in v0['sizes'])}</div><p class="size-hint">Выберите размер</p>{'' if one_size else '<p class="size-hint"><a href="#razmer">Таблица размеров</a></p>'}</div>
  <div class="buy"><div class="qty"><button type="button" data-q="-1" aria-label="Меньше">−</button><input type="number" inputmode="numeric" value="1" min="1" aria-label="Количество"><button type="button" data-q="1" aria-label="Больше">+</button></div>
   <button type="button" class="btn sun" data-add>Добавить в корзину</button></div>
  <p class="buy-msg" role="status" aria-live="polite"></p>
  <button type="button" class="btn alt block" data-buy-now>Купить сейчас</button>
  <ul class="perks">
   <li>{TRUCK_SVG}<span>Доставка {d['carrier']} по Астане 1–2 дня, Косшы и пригород 1–3 дня. {('Стоимость — ' + money(z0['price']) + free_txt + '.') if z0['price'] is not None else 'Оплачивается отдельно по тарифу ' + d['carrier'] + '.'}</span></li>
   <li>{RETURN_SVG}<span>Обмен и возврат {CFG['returns_days']} дней, если вещь не носили.</span></li>
   <li>{CHECK_SVG}<span>Новая вещь со склада в Астане. Остаток по размерам — точный.</span></li>
  </ul>
  <div class="info">
   <details open><summary>Описание</summary><div class="body"><p>{e(description(p))}</p><p><a href="{wa_link('Здравствуйте! Вопрос по товару ' + p['name'] + ' (арт. ' + p['id'] + ')')}" rel="noopener">Задать вопрос о товаре в WhatsApp</a></p></div></details>
   <details open><summary>Характеристики</summary><div class="body">{spec_html}</div></details>
   <details><summary>Наличие по цветам и размерам</summary><div class="body">{stock_tbl}</div></details>
   <details id="razmer"><summary>Таблица размеров</summary><div class="body">{size_block}</div></details>
   <details><summary>Уход</summary><div class="body"><p>{e(care(p))}</p></div></details>
   <details><summary>Доставка и оплата</summary><div class="body">{zones_html()}<p>Оплата: {e('; '.join(CFG['payment_methods']))}. <a href="{{R}}dostavka/">Подробнее</a></p></div></details>
  </div>
 </div>
</article>
</div>
{rel_html}
<div class="sticky-buy"><span class="tag">{money(p['price'])}</span><button type="button" class="btn sun" data-add>В корзину</button></div>'''
    desc = f"{p['name']} — {money(p['price'])}. " + f"{len(p['variants'])} {plural(len(p['variants']), 'цвет', 'цвета', 'цветов')}, размеры {', '.join(size_label(s, p) for s in sizes_all)}. Доставка СДЭК по Астане 1–2 дня."
    page(url, f"{p['name']} — купить в Астане за {money(p['price'])} | {CFG['store_name']}", desc, body,
         jsonld=[product_ld(p), crumbs_ld([('Главная', ''), ('Каталог', 'katalog/'), (cname, f'katalog/{cslug}/'), (p['name'], url)])],
         og_image=f"images/{p['image']}.webp")

def build_cart():
    body = f'''<div class="wrap" id="checkout">
<h1 style="margin-top:24px">Оформление заказа</h1>
<div data-empty hidden class="empty"><p>Корзина пустая. Добавьте товары из каталога.</p><a class="btn sun" href="{{R}}katalog/">Перейти в каталог</a></div>
<div data-done hidden class="done box"><span class="tag">Заказ <span data-num></span></span><h2>Заказ сформирован</h2>
 <p>Мы открыли WhatsApp с текстом заказа — просто нажмите «Отправить». Если окно не открылось, используйте кнопку ниже.</p>
 <p><a class="btn wa" data-wa-again href="#" target="_blank" rel="noopener">Открыть WhatsApp</a> <button type="button" class="btn alt" data-copy>Скопировать текст заказа</button></p>
 <p class="size-hint">Подтвердим заказ и время доставки в течение рабочего дня. <a href="{{R}}katalog/">Вернуться в каталог</a></p></div>
<form class="checkout" data-full novalidate>
 <div>
  <section class="box" aria-labelledby="h-items" style="margin-bottom:18px"><h2 id="h-items">Товары</h2><div data-lines></div></section>
  <section class="box" aria-labelledby="h-del" style="margin-bottom:18px"><h2 id="h-del">Доставка {e(CFG['delivery']['carrier'])}</h2>
   <div class="radios" data-zones></div>
   <div class="field" data-city-field hidden><label for="f-city">Город</label><input id="f-city" name="city" autocomplete="address-level2"><span class="err">Укажите город</span></div>
   <div data-addr><div class="field"><label for="f-street">Улица, дом</label><input id="f-street" name="street" autocomplete="street-address" placeholder="Например: пр. Мангилик Ел, 55"><span class="err">Укажите улицу и дом</span></div>
   <div class="field"><label for="f-flat">Квартира / офис, подъезд, этаж</label><input id="f-flat" name="flat" placeholder="Необязательно"></div></div>
  </section>
  <section class="box" aria-labelledby="h-who"><h2 id="h-who">Получатель</h2>
   <div class="two"><div class="field"><label for="f-name">Имя</label><input id="f-name" name="name" autocomplete="name" required><span class="err">Укажите имя</span></div>
   <div class="field"><label for="f-phone">Телефон</label><input id="f-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="+7 (7__) ___-__-__" required><span class="err">Нужен номер из 11 цифр</span></div></div>
   <h3 style="font:600 15px var(--f-body);margin:8px 0 10px">Оплата</h3><div class="radios" data-pay></div>
   <div class="field"><label for="f-comment">Комментарий</label><textarea id="f-comment" name="comment" placeholder="Удобное время доставки, вопросы по размеру"></textarea></div>
  </section>
 </div>
 <aside class="summary box" aria-labelledby="h-sum"><h2 id="h-sum">Итого</h2>
  <div class="sum-row"><span>Товары</span><span data-s-sub></span></div>
  <div class="sum-row"><span>Доставка</span><span data-s-del></span></div>
  <div data-s-free style="margin:10px 0"></div>
  <div class="sum-row total"><span>Итого за товары</span><span data-s-total></span></div>
  <p class="size-hint" data-s-delnote>Доставка {e(CFG['delivery']['carrier'])} оплачивается отдельно по тарифу перевозчика — стоимость назовём при подтверждении заказа.</p>
  <button type="submit" class="btn wa block" style="margin-top:16px">{WA_SVG.replace('<svg', '<svg style="width:22px;height:22px;fill:currentColor"')}Отправить заказ в WhatsApp</button>
  <p class="size-hint">Нажимая кнопку, вы отправляете заказ продавцу ({e(CFG['seller']['legal_name'])}). Оплата — после подтверждения заказа.</p>
 </aside>
</form>
</div>'''
    page('korzina/', f"Корзина и оформление заказа — {CFG['store_name']}", 'Оформление заказа с доставкой СДЭК по Астане и пригороду.', body, robots='noindex,follow')

def build_info_pages():
    d = CFG['delivery']; items = faq_items()
    sub = ', '.join(z['name'] for z in d['zones'] if z['id'] not in ('astana', 'kz'))
    pick = f"<h2>Самовывоз</h2><p>{e(d['pickup']['address'])}. {e(d['pickup'].get('hours', ''))}</p>" if d.get('pickup', {}).get('enabled') else ''
    body = f'''<div class="wrap prose">
<nav aria-label="Навигация"><ol class="crumbs"><li><a href="{{R}}">Главная</a></li><li aria-current="page">Доставка и оплата</li></ol></nav>
<h1>Доставка и оплата</h1>
<p>Доставляем курьером <b>{e(d['carrier'])}</b> по Астане и в пригород: {e(sub)}. В другие города Казахстана — тоже через {e(d['carrier'])}. Цены на сайте указаны за товар, <b>доставка оплачивается отдельно</b> по тарифу {e(d['carrier'])} — стоимость назовём при подтверждении заказа.{(' Заказы от <b>' + money(d['free_from']) + '</b> по Астане и пригороду доставляем бесплатно.') if d.get('free_from') else ''}</p>
{zones_html()}
{pick}
<h2>Как проходит заказ</h2>{steps_html()}
<h2>Оплата</h2><ul>{''.join(f'<li>{e(m)}</li>' for m in CFG['payment_methods'])}</ul>
<h2 id="vozvrat">Обмен и возврат</h2>
<p>Вещь можно обменять или вернуть в течение {CFG['returns_days']} дней с момента получения, если её не носили, сохранены ярлыки и товарный вид. Нижнее бельё надлежащего качества обмену и возврату не подлежит. Напишите нам в <a href="{wa_link('Здравствуйте! Хочу оформить обмен/возврат.')}" rel="noopener">WhatsApp</a> — согласуем курьера.</p>
<h2>Частые вопросы</h2>{faq_html(items)}
</div>'''
    page('dostavka/', f"Доставка и оплата — {CFG['store_name']}, Астана", f"Доставка СДЭК по Астане, Косшы и пригороду за 1–2 дня. Оплата Kaspi или при получении. Возврат {CFG['returns_days']} дней.",
         body, active='dost', jsonld=[faq_ld(items), crumbs_ld([('Главная', ''), ('Доставка и оплата', 'dostavka/')])])

    wt, mt = size_tables()
    body = f'''<div class="wrap prose">
<nav aria-label="Навигация"><ol class="crumbs"><li><a href="{{R}}">Главная</a></li><li aria-current="page">Таблица размеров</li></ol></nav>
<h1>Таблица размеров</h1>
<p>Снимите мерки по белью: грудь — по самым выступающим точкам, талия — по самому узкому месту, бёдра — по самым выступающим точкам ягодиц. Если вы между размерами, для свободной посадки берите больший.</p>
<h2>Женская одежда</h2>{wt}
<h2>Мужская одежда</h2>{mt}
<h2>Единый размер</h2><p>Шапки, кепки, балаклавы, сумки и часть оверсайз-моделей идут в одном размере. Кепки и бейсболки регулируются застёжкой.</p>
<p>Таблицы ориентировочные — у моделей разная посадка. Пришлите название модели и ваши параметры в <a href="{wa_link('Здравствуйте! Помогите подобрать размер.')}" rel="noopener">WhatsApp</a>, подскажем точно.</p>
</div>'''
    page('razmery/', f"Таблица размеров одежды — {CFG['store_name']}", 'Как подобрать размер женской и мужской одежды: таблица соответствия XS–4XL, обхваты груди, талии и бёдер.', body)

    s = CFG['seller']
    body = f'''<div class="wrap prose">
<nav aria-label="Навигация"><ol class="crumbs"><li><a href="{{R}}">Главная</a></li><li aria-current="page">Контакты</li></ol></nav>
<h1>Контакты</h1>
<p><a class="btn wa" href="{wa_link('Здравствуйте!')}" rel="noopener">Написать в WhatsApp</a></p>
<table class="spec">
<tr><th>Телефон / WhatsApp</th><td>{e(CFG['phone_display'])}</td></tr>
{f"<tr><th>Telegram</th><td>{e(CFG['telegram'])}</td></tr>" if CFG.get('telegram') else ''}
{f"<tr><th>Instagram</th><td>{e(CFG['instagram'])}</td></tr>" if CFG.get('instagram') else ''}
{f"<tr><th>E-mail</th><td>{e(CFG['email'])}</td></tr>" if CFG.get('email') else ''}
<tr><th>Режим работы</th><td>{e(CFG['work_hours'])}</td></tr>
<tr><th>Продавец</th><td>{e(s['legal_name'])}{(', БИН ' + e(s['bin'])) if s.get('bin') else ''}</td></tr>
<tr><th>Адрес</th><td>{e(s['address'])}</td></tr>
</table>
</div>'''
    page('kontakty/', f"Контакты — {CFG['store_name']}, Астана", f"Как связаться с магазином {CFG['store_name']}: WhatsApp {CFG['phone_display']}, {CFG['work_hours'].lower()}.", body, jsonld=[org_ld()])

    body = f'''<div class="wrap" style="padding:60px 16px;text-align:center"><span class="tag" style="font-size:28px">404</span><h1 style="margin-top:20px">Такой страницы нет</h1><p>Возможно, товар закончился или ссылка устарела.</p><a class="btn sun" href="{{R}}katalog/">Открыть каталог</a></div>'''
    page('404.html', f"Страница не найдена — {CFG['store_name']}", 'Страница не найдена', body, robots='noindex')
    # GitHub Pages отдаёт 404.html из корня, поэтому пути в нём должны быть абсолютными
    p404 = (OUT / '404.html').read_text(encoding='utf-8').replace('data-root=""', f'data-root="{SITE}"')
    p404 = re.sub(r'(href|src)="(?!https?:|#|mailto:|tel:)([^"]*)"', lambda m: f'{m.group(1)}="{SITE}{m.group(2)}"', p404)
    (OUT / '404.html').write_text(p404, encoding='utf-8')

# ---------------- данные для JS, ИИ и поисковиков ----------------
def build_data():
    js = {'cfg': {k: CFG[k] for k in ('store_name', 'whatsapp', 'phone_display', 'delivery', 'payment_methods', 'order_webhook', 'currency')},
          'products': {p['id']: {'n': p['name'], 'u': p_url(p), 'p': p['price'], 'g': p['gender'],
                                 'v': [[v['sku'], v['color'], v['img'], v['sizes']] for v in p['variants']]} for p in PRODUCTS}}
    (OUT / 'assets').mkdir(parents=True, exist_ok=True)
    (OUT / 'assets' / 'catalog.js').write_text('window.SHOP=' + json.dumps(js, ensure_ascii=False, separators=(',', ':')) + ';', encoding='utf-8')

    feed = []
    for p in PRODUCTS:
        feed.append({'id': p['id'], 'name': p['name'], 'url': SITE + p_url(p), 'price': p['price'], 'currency': 'KZT',
                     'old_price': p.get('old_price'), 'category': CATS[p['category']][1], 'gender': GENDERS[p['gender']][1],
                     'material': p.get('material') or None, 'season': p.get('season'), 'features': p.get('features', []),
                     'description': description(p), 'in_stock_total': stock(p), 'image': SITE + f"images/{p['image']}.webp",
                     'variants': [{'sku': v['sku'], 'color': v['color'], 'image': SITE + f"images/{v['img']}.webp",
                                   'sizes': {size_label(s, p): q for s, q in v['sizes'].items()},
                                   'url': SITE + p_url(p) + f"?c={v['sku']}"} for v in p['variants']]})
    meta = {'store': CFG['store_name'], 'seller': CFG['seller']['legal_name'], 'site': SITE, 'updated': TODAY, 'currency': 'KZT',
            'delivery': {'carrier': CFG['delivery']['carrier'], 'free_from': CFG['delivery'].get('free_from'),
                         'zones': [{'name': z['name'], 'price': z['price'], 'eta': z['eta']} for z in CFG['delivery']['zones']]},
            'payment_methods': CFG['payment_methods'], 'returns_days': CFG['returns_days'],
            'how_to_order': 'Добавить товары в корзину на сайте и отправить заказ в WhatsApp, либо написать в WhatsApp ' + CFG['phone_display'],
            'products': feed}
    (OUT / 'data').mkdir(exist_ok=True)
    (OUT / 'data' / 'products.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['sku', 'model_id', 'name', 'color', 'size', 'qty', 'price_kzt', 'category', 'gender', 'material', 'url', 'image'])
    for p in PRODUCTS:
        for v in p['variants']:
            for s, q in v['sizes'].items():
                w.writerow([f"{v['sku']}-{s}", p['id'], p['name'], v['color'], size_label(s, p), q, p['price'], CATS[p['category']][1],
                            GENDERS[p['gender']][1], p.get('material', ''), SITE + p_url(p) + f"?c={v['sku']}", SITE + f"images/{v['img']}.webp"])
    (OUT / 'data' / 'products.csv').write_text('﻿' + buf.getvalue(), encoding='utf-8')

    # Google Merchant / Яндекс-совместимый RSS-фид
    items = []
    for p in PRODUCTS:
        for v in p['variants']:
            for s, q in v['sizes'].items():
                items.append(f'''<item><g:id>{xesc(v["sku"])}-{xesc(s)}</g:id><g:item_group_id>{p["id"]}</g:item_group_id><title>{xesc(p["name"] + ", " + v["color"].lower() + ", " + size_label(s, p))}</title>
<description>{xesc(description(p))}</description><link>{xesc(SITE + p_url(p) + "?c=" + v["sku"])}</link><g:image_link>{xesc(SITE + "images/" + v["img"] + ".webp")}</g:image_link>
<g:availability>{"in_stock" if q > 0 else "out_of_stock"}</g:availability><g:price>{p["price"]} KZT</g:price><g:condition>new</g:condition><g:brand>Без бренда</g:brand><g:identifier_exists>no</g:identifier_exists>
<g:color>{xesc(v["color"])}</g:color><g:size>{xesc(size_label(s, p))}</g:size><g:gender>{ {"women": "female", "men": "male", "kids": "unisex", "unisex": "unisex"}[p["gender"]] }</g:gender>{"<g:age_group>kids</g:age_group>" if p["gender"] == "kids" else "<g:age_group>adult</g:age_group>"}
<g:product_type>{xesc("Одежда > " + CATS[p["category"]][1])}</g:product_type></item>''')
    (OUT / 'feed.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel><title>{xesc(CFG["store_name"])}</title><link>{SITE}</link><description>{xesc(CFG["tagline"])}</description>\n' + '\n'.join(items) + '\n</channel></rss>', encoding='utf-8')

    # llms.txt — краткая карта сайта для ИИ (стандарт llmstxt.org)
    d = CFG['delivery']
    zones = '\n'.join(f"- {z['name']}: {money(z['price']) if z['price'] is not None else 'по тарифу СДЭК'}, {z['eta']}" for z in d['zones'])
    cats = '\n'.join(f"- [{v[1]}]({SITE}katalog/{v[0]}/): {(lambda n: f"{n} {plural(n, 'модель', 'модели', 'моделей')}")(sum(1 for p in PRODUCTS if p['category'] == k))}, от {money(min(p['price'] for p in PRODUCTS if p['category'] == k))}" for k, v in CATS.items() if any(p['category'] == k for p in PRODUCTS))
    llms = f'''# {CFG['store_name']}

> {CFG['tagline']} Интернет-магазин новой одежды и аксессуаров (остатки партий со склада в Астане, Казахстан). Продавец — {CFG['seller']['legal_name']}. Цены в тенге (KZT). {len(PRODUCTS)} моделей, {sum(len(p['variants']) for p in PRODUCTS)} цветовых вариантов, {sum(stock(p) for p in PRODUCTS)} шт в наличии. Данные обновлены {TODAY}.

Как купить: выбрать товар, цвет и размер на сайте, добавить в корзину и отправить заказ в WhatsApp ({CFG['phone_display']}). Можно сразу написать в WhatsApp: {wa_link()}
Цены на сайте — цены продажи за 1 шт. Доставка: курьер {d['carrier']}, оплачивается отдельно по тарифу перевозчика{(', бесплатно от ' + money(d['free_from'])) if d.get('free_from') else ''}.
{zones}
Оплата: {'; '.join(CFG['payment_methods'])}. Обмен и возврат — {CFG['returns_days']} дней (кроме нижнего белья).

## Каталог
- [Весь каталог]({SITE}katalog/)
{cats}
- [Женская одежда]({SITE}katalog/zhenskoe/)
- [Мужская одежда]({SITE}katalog/muzhskoe/)

## Данные (машиночитаемые)
- [products.json]({SITE}data/products.json): все товары с ценами, цветами, размерами и остатками
- [products.csv]({SITE}data/products.csv): то же в CSV, одна строка = артикул-цвет-размер
- [feed.xml]({SITE}feed.xml): товарный фид Google Merchant
- [llms-full.txt]({SITE}llms-full.txt): полный каталог текстом

## Покупателям
- [Доставка и оплата]({SITE}dostavka/)
- [Таблица размеров]({SITE}razmery/)
- [Контакты]({SITE}kontakty/)
'''
    (OUT / 'llms.txt').write_text(llms, encoding='utf-8')
    full = [llms, '\n## Все товары\n']
    for p in PRODUCTS:
        full.append(f"### {p['name']} — {money(p['price'])}\n- Ссылка: {SITE}{p_url(p)}\n- Модель: {p['id']}; категория: {CATS[p['category']][1]}; для кого: {GENDERS[p['gender']][1]}"
                    + (f"; материал: {p['material']}" if p.get('material') else '') + f"; сезон: {p['season']}\n- {description(p)}\n- Наличие (цвет: размер — шт):")
        for v in p['variants']:
            full.append(f"  - {v['color']} [{v['sku']}]: " + ', '.join(f"{size_label(s, p)} — {q}" for s, q in v['sizes'].items()))
        full.append('')
    (OUT / 'llms-full.txt').write_text('\n'.join(full), encoding='utf-8')

    bots = ['GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'anthropic-ai', 'PerplexityBot', 'Perplexity-User',
            'Google-Extended', 'Googlebot', 'Bingbot', 'YandexBot', 'Applebot', 'Applebot-Extended', 'CCBot', 'Meta-ExternalAgent', 'Bytespider', 'DuckAssistBot', 'MistralAI-User', 'cohere-ai', 'YouBot']
    robots = '# Сайт открыт для поисковых систем и ИИ-ассистентов\n' + ''.join(f'User-agent: {b}\nAllow: /\n\n' for b in bots) + 'User-agent: *\nAllow: /\nDisallow: /korzina/\n\n' + f'Sitemap: {SITE}sitemap.xml\n'
    (OUT / 'robots.txt').write_text(robots, encoding='utf-8')
    urls = [''] + ['katalog/'] + [f'katalog/{v[0]}/' for k, v in CATS.items() if any(p['category'] == k for p in PRODUCTS)] + \
           [f'katalog/{v[0]}/' for k, v in GENDERS.items() if any(p['gender'] == k for p in PRODUCTS)] + [p_url(p) for p in PRODUCTS] + ['dostavka/', 'razmery/', 'kontakty/']
    sm = ''.join(f'<url><loc>{SITE}{u}</loc><lastmod>{TODAY}</lastmod></url>' for u in urls)
    (OUT / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n', encoding='utf-8')
    (OUT / 'favicon.svg').write_text(ICON_SVG.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" '), encoding='utf-8')
    (OUT / '.nojekyll').write_text('', encoding='utf-8')
    if (ROOT / 'CNAME').exists(): shutil.copy(ROOT / 'CNAME', OUT / 'CNAME')

def copy_static():
    (OUT / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / 'assets' / 'app.js', OUT / 'assets' / 'app.js')
    css = (ROOT / 'assets' / 'fonts.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'assets' / 'style.css').read_text(encoding='utf-8')
    (OUT / 'assets' / 'style.css').write_text(css, encoding='utf-8')
    shutil.copytree(ROOT / 'assets' / 'fonts', OUT / 'assets' / 'fonts')
    if (ROOT / 'og.jpg').exists(): shutil.copy(ROOT / 'og.jpg', OUT / 'og.jpg')
    src = ROOT / 'images'; dst = OUT / 'images'; dst.mkdir(exist_ok=True)
    need = {p['image'] for p in PRODUCTS} | {v['img'] for p in PRODUCTS for v in p['variants']}
    missing = [h for h in need if not (src / f'{h}.webp').exists()]
    for h in need:
        if (src / f'{h}.webp').exists(): shutil.copy(src / f'{h}.webp', dst / f'{h}.webp')
    if missing: print(f'ВНИМАНИЕ: нет {len(missing)} фото в images/: {missing[:5]}…')

VER = TODAY.replace('-', '')

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    copy_static(); build_data(); build_home(); build_catalog_pages()
    for i, p in enumerate(PRODUCTS): build_product(p, i)
    build_cart(); build_info_pages()
    n = sum(1 for _ in OUT.rglob('*.html'))
    print(f'Готово: {n} страниц, {len(PRODUCTS)} товаров -> {OUT}')
    if 'USERNAME' in SITE: print('Подсказка: впишите адрес сайта в config.json -> site_url')
    if CFG['whatsapp'].startswith('7700000'): print('Подсказка: впишите номер WhatsApp в config.json -> whatsapp')

if __name__ == '__main__':
    main()
