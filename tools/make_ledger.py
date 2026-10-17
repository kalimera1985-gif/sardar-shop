#!/usr/bin/env python3
"""
Создаёт таблицу учёта продаж SARDAR_учет_продаж.xlsx (для загрузки в Google Таблицы).

  python tools/make_ledger.py Остатки_Teez.xlsx  [выходной_файл.xlsx]

Листы:
  Заказы   — один заказ = одна строка (статус, оплата, трек СДЭК, сумма, себестоимость, прибыль)
  Позиции  — каждая проданная вещь (артикул-размер, кол-во, цена, закупка)
  Остатки  — начальный остаток, продано, остаток по каждому артикулу-размеру (+ закупочная цена)
  Сводка   — выручка, прибыль, продажи по месяцам, категориям, источникам, статусам

ВАЖНО: файл содержит ЗАКУПОЧНЫЕ цены — не кладите его в публичный репозиторий GitHub.
"""
import json, sys
from datetime import date
from pathlib import Path
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
CATS = {'tshirts': 'Футболки и поло', 'tops': 'Майки и топы', 'longsleeves': 'Лонгсливы и водолазки', 'hoodies': 'Худи, свитшоты, жилеты',
        'dresses': 'Платья и туники', 'home': 'Домашняя одежда', 'pants': 'Брюки и лосины', 'shorts': 'Шорты и юбки', 'sets': 'Костюмы и комплекты',
        'underwear': 'Бельё', 'hats': 'Головные уборы', 'bags': 'Сумки'}
STATUSES = ['Новый', 'Подтверждён', 'Отправлен', 'Доставлен', 'Отменён', 'Возврат']
SOURCES = ['Сайт', 'WhatsApp', 'Instagram', 'Kaspi', 'OLX', 'Магазин', 'Другое']

INK = '13233A'; SUN = 'FFC61A'; MIST = 'EEF3F6'
HEAD_FONT = Font(bold=True, color='FFFFFF'); HEAD_FILL = PatternFill('solid', fgColor=INK)
CALC_FILL = PatternFill('solid', fgColor=MIST)
THIN = Side(style='thin', color='D8E1E7')
MONEY = '#,##0 "₸"'

def cost_prices(teez_xlsx):
    """Закупочная цена по номеру модели (SD001…) — в том же порядке, что и tools/import_teez.py"""
    ws = openpyxl.load_workbook(teez_xlsx, data_only=True).active
    res = []
    for r in range(3, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if name is None or str(name).strip().upper() == 'ИТОГО': continue
        if ws.cell(r, 15).value is not None or ws.cell(r, 16).value is not None:
            res.append(int(ws.cell(r, 16).value or 0))
    return {f'SD{i:03d}': c for i, c in enumerate(res, 1)}

def header(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(1, i, c); cell.font = HEAD_FONT; cell.fill = HEAD_FILL
        cell.alignment = Alignment(vertical='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = 'A2'

def main():
    teez = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT.parent / 'SARDAR_учет_продаж.xlsx'
    prods = json.load(open(ROOT / 'data' / 'catalog.json', encoding='utf-8'))['products']
    costs = cost_prices(teez)
    wb = openpyxl.Workbook()

    # ---------- Заказы ----------
    z = wb.active; z.title = 'Заказы'
    header(z, ['№ заказа', 'Дата', 'Источник', 'Статус', 'Оплачен', 'Клиент', 'Телефон', 'Район / город', 'Адрес', 'Способ оплаты',
               'Сумма товаров', 'Доставка СДЭК, ₸', 'Трек СДЭК', 'Себестоимость', 'Прибыль', 'Месяц', 'Комментарий', 'Состав заказа'],
           [14, 17, 11, 13, 10, 18, 18, 16, 28, 22, 14, 12, 16, 14, 13, 10, 28, 50])
    z.auto_filter.ref = 'A1:R1'
    for col, items in (('C', SOURCES), ('D', STATUSES), ('E', ['Да', 'Нет'])):
        dv = DataValidation(type='list', formula1='"' + ','.join(items) + '"', allow_blank=True)
        z.add_data_validation(dv); dv.add(f'{col}2:{col}5000')
    for c in 'KLNO': z.column_dimensions[c].number_format = MONEY

    # ---------- Позиции ----------
    p = wb.create_sheet('Позиции')
    header(p, ['№ заказа', 'Дата', 'Артикул-размер', 'Модель', 'Товар', 'Цвет', 'Размер', 'Кол-во', 'Цена, ₸', 'Сумма, ₸',
               'Закуп. цена, ₸', 'Себестоимость, ₸', 'Статус заказа', 'Категория'],
           [14, 17, 18, 9, 40, 16, 9, 8, 11, 12, 12, 13, 13, 22])
    p.auto_filter.ref = 'A1:N1'

    # ---------- Остатки ----------
    o = wb.create_sheet('Остатки')
    header(o, ['Артикул-размер', 'Модель', 'Товар', 'Категория', 'Цвет', 'Размер', 'Начальный остаток', 'Продано', 'Остаток',
               'Цена продажи, ₸', 'Закуп. цена, ₸', 'Остаток по закупке, ₸'],
           [18, 9, 44, 22, 18, 9, 11, 10, 10, 13, 13, 15])
    r = 2
    for pr in prods:
        for v in pr['variants']:
            for s, q in v['sizes'].items():
                key = f"{v['sku']}-{s}"
                o.append([key, pr['id'], pr['name'], CATS[pr['category']], v['color'], 'Единый' if s == 'ONE' else s, q,
                          f'=SUMIFS(Позиции!H:H,Позиции!C:C,A{r},Позиции!M:M,"<>Отменён",Позиции!M:M,"<>Возврат")',
                          f'=G{r}-H{r}', pr['price'], costs.get(pr['id'], 0), f'=I{r}*K{r}'])
                for c in 'HIL': o[f'{c}{r}'].fill = CALC_FILL
                for c in 'JKL': o[f'{c}{r}'].number_format = MONEY
                r += 1
    last_o = r - 1
    o.auto_filter.ref = f'A1:L{last_o}'

    # ---------- Сводка ----------
    s = wb.create_sheet('Сводка', 0)
    s.column_dimensions['A'].width = 34; s.column_dimensions['B'].width = 16
    for c in 'DEFGHIJ': s.column_dimensions[c].width = 15
    s.column_dimensions['D'].width = 26
    s['A1'] = 'SARDAR — учёт продаж'; s['A1'].font = Font(bold=True, size=16, color=INK)
    s['A2'] = 'Отменённые заказы и возвраты в выручку и прибыль не входят. Всё считается автоматически.'
    s['A2'].font = Font(italic=True, color='4A5B70')
    ok = 'Заказы!D:D,"<>Отменён",Заказы!D:D,"<>Возврат"'
    kpi = [
        ('Заказов всего', '=COUNTA(Заказы!A:A)-1', None),
        ('Заказов без отмен', f'=COUNTIFS(Заказы!A:A,"<>",Заказы!A:A,"<>№ заказа",{ok})', None),
        ('Продано вещей, шт', '=SUMIFS(Позиции!H:H,Позиции!M:M,"<>Отменён",Позиции!M:M,"<>Возврат")', None),
        ('Выручка (без отмен)', f'=SUMIFS(Заказы!K:K,{ok})', MONEY),
        ('— в т.ч. доставлено', '=SUMIFS(Заказы!K:K,Заказы!D:D,"Доставлен")', MONEY),
        ('Себестоимость проданного', f'=SUMIFS(Заказы!N:N,{ok})', MONEY),
        ('Прибыль', '=SUM(Заказы!O:O)', MONEY),
        ('Маржа, %', '=IF(B7=0,0,B10/B7)', '0.0%'),
        ('Средний чек', '=IF(B5=0,0,B7/B5)', MONEY),
        ('Оплачено клиентами', f'=SUMIFS(Заказы!K:K,Заказы!E:E,"Да",{ok})', MONEY),
        ('Ждём оплату', '=B7-B13', MONEY),
        ('Расходы на доставку СДЭК (если платили вы)', '=SUM(Заказы!L:L)', MONEY),
        ('Остаток на складе, шт', f'=SUM(Остатки!I2:I{last_o})', None),
        ('Остаток по закупке', f'=SUM(Остатки!L2:L{last_o})', MONEY),
        ('Остаток по цене продажи', f'=SUMPRODUCT(Остатки!I2:I{last_o},Остатки!J2:J{last_o})', MONEY),
    ]
    for i, (lab, f, fmt) in enumerate(kpi, 4):
        s.cell(i, 1, lab); c = s.cell(i, 2, f); c.font = Font(bold=True)
        if fmt: c.number_format = fmt
    s['A3'] = 'Показатель'; s['B3'] = 'Значение'
    # статусы
    s['D3'] = 'Статус'; s['E3'] = 'Заказов'; s['F3'] = 'Сумма'
    for i, st in enumerate(STATUSES, 4):
        s.cell(i, 4, st); s.cell(i, 5, f'=COUNTIF(Заказы!D:D,D{i})'); c = s.cell(i, 6, f'=SUMIFS(Заказы!K:K,Заказы!D:D,D{i})'); c.number_format = MONEY
    # источники
    s['H3'] = 'Источник'; s['I3'] = 'Заказов'; s['J3'] = 'Выручка'
    for i, src in enumerate(SOURCES, 4):
        s.cell(i, 8, src); s.cell(i, 9, f'=COUNTIFS(Заказы!C:C,H{i},{ok})'); c = s.cell(i, 10, f'=SUMIFS(Заказы!K:K,Заказы!C:C,H{i},{ok})'); c.number_format = MONEY
    # по месяцам
    row = 21
    s.cell(row, 1, 'По месяцам').font = Font(bold=True, size=13, color=INK)
    for j, h in enumerate(['Месяц', 'Заказов', 'Выручка', 'Прибыль'], 1):
        s.cell(row + 1, j if j == 1 else j + 0, h)
    t = date.today(); y, m = t.year, t.month
    for k in range(12):
        rr = row + 2 + k
        mm = f'{y}-{m:02d}'
        s.cell(rr, 1, mm)
        s.cell(rr, 2, f'=COUNTIFS(Заказы!P:P,A{rr},{ok})')
        s.cell(rr, 3, f'=SUMIFS(Заказы!K:K,Заказы!P:P,A{rr},{ok})').number_format = MONEY
        s.cell(rr, 4, f'=SUMIFS(Заказы!O:O,Заказы!P:P,A{rr})').number_format = MONEY
        m += 1
        if m > 12: m = 1; y += 1
    # по категориям
    s.cell(row, 6, 'По категориям').font = Font(bold=True, size=13, color=INK)
    for j, h in enumerate(['Категория', 'Продано, шт', 'Выручка', 'Остаток, шт'], 6):
        s.cell(row + 1, j, h)
    for k, cat in enumerate(CATS.values()):
        rr = row + 2 + k
        s.cell(rr, 6, cat)
        s.cell(rr, 7, f'=SUMIFS(Позиции!H:H,Позиции!N:N,F{rr},Позиции!M:M,"<>Отменён",Позиции!M:M,"<>Возврат")')
        s.cell(rr, 8, f'=SUMIFS(Позиции!J:J,Позиции!N:N,F{rr},Позиции!M:M,"<>Отменён",Позиции!M:M,"<>Возврат")').number_format = MONEY
        s.cell(rr, 9, f'=SUMIFS(Остатки!I:I,Остатки!D:D,F{rr})')
    for cell in (s['A3'], s['B3'], s['D3'], s['E3'], s['F3'], s['H3'], s['I3'], s['J3']) + tuple(s[row + 1]):
        if cell.value: cell.font = HEAD_FONT; cell.fill = HEAD_FILL
    s.column_dimensions['F'].width = 24; s.column_dimensions['H'].width = 14

    # ---------- Инструкция ----------
    h = wb.create_sheet('Как пользоваться')
    h.column_dimensions['A'].width = 110
    lines = [
        'КАК ВЕСТИ УЧЁТ',
        '1. Заказы с сайта появляются на листе «Заказы» сами (статус «Новый»), состав — на листе «Позиции». Остатки уменьшаются автоматически.',
        '2. Продажи вне сайта (WhatsApp, Kaspi, Instagram, магазин): меню SARDAR → «Добавить продажу вручную».',
        '3. Меняйте «Статус» по ходу: Новый → Подтверждён → Отправлен → Доставлен. «Отменён» и «Возврат» возвращают вещи в остаток и убирают сумму из выручки.',
        '4. «Оплачен» = Да, когда деньги пришли. В «Трек СДЭК» впишите номер отправления.',
        '5. «Доставка СДЭК, ₸» — заполняйте, только если доставку оплатили вы (для учёта расходов).',
        '6. На сайте показываются остатки из листа «Остатки» (обновление примерно раз в минуту).',
        '7. Новая поставка: увеличьте «Начальный остаток» нужной строки или добавьте строки (столбцы H, I, L скопируйте формулами сверху).',
        '',
        'Серые столбцы считаются формулами — не вписывайте туда значения вручную.',
        'Закупочные цены есть только в этой таблице — на сайт они не попадают.',
    ]
    for i, l in enumerate(lines, 1):
        h.cell(i, 1, l).alignment = Alignment(wrap_text=True)
    h['A1'].font = Font(bold=True, size=14)

    wb.save(out)
    print(f'OK: {out}  ({last_o - 1} строк остатков)')

if __name__ == '__main__':
    main()
