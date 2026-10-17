/**
 * SARDAR — учёт продаж в Google Таблице.
 *
 * Что делает:
 *  1) принимает заказы с сайта (doPost) → листы «Заказы» и «Позиции», остатки уменьшаются сами;
 *  2) отдаёт сайту актуальные остатки (doGet ?action=stock) — проданное исчезает с сайта;
 *  3) меню SARDAR → «Добавить продажу вручную» — для продаж через WhatsApp, Kaspi, Instagram, магазин;
 *  4) (необязательно) присылает уведомление о новом заказе в Telegram.
 *
 * Установка — см. README.md, раздел «Учёт продаж».
 */

// ---- Необязательно: уведомления в Telegram о каждом новом заказе ----
// 1) В Telegram напишите @BotFather → /newbot → скопируйте токен сюда.
// 2) Напишите своему боту любое сообщение, затем откройте
//    https://api.telegram.org/bot<ТОКЕН>/getUpdates и скопируйте "chat":{"id": ...} сюда.
const TELEGRAM_BOT_TOKEN = '';
const TELEGRAM_CHAT_ID = '';

const SHEET_ORDERS = 'Заказы';
const SHEET_ITEMS = 'Позиции';
const SHEET_STOCK = 'Остатки';
const STATUSES = ['Новый', 'Подтверждён', 'Отправлен', 'Доставлен', 'Отменён', 'Возврат'];
const SOURCES = ['Сайт', 'WhatsApp', 'Instagram', 'Kaspi', 'OLX', 'Магазин', 'Другое'];

// ================= меню =================
function onOpen() {
  SpreadsheetApp.getUi().createMenu('SARDAR')
    .addItem('Добавить продажу вручную', 'showManualSale')
    .addItem('Проверить подключение сайта', 'checkSetup')
    .addToUi();
}

// ================= приём заказа с сайта =================
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var num = recordOrder_(data, 'Сайт', 'Новый', false);
    return json_({ ok: true, number: num });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, error: String(err) });
  }
}

// ================= остатки для сайта =================
function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || 'stock';
  if (action === 'stock') return json_(getStockPublic_());
  return json_({ ok: true });
}

function getStockPublic_() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('stock');
  if (cached) return JSON.parse(cached);
  var out = { updated: new Date().toISOString(), stock: {} };
  var map = readStock_();
  Object.keys(map).forEach(function (k) { out.stock[k] = Math.max(0, map[k].remain); });
  try { cache.put('stock', JSON.stringify(out), 60); } catch (err) { }
  return out;
}

// ================= ядро: запись заказа =================
function recordOrder_(d, defaultSource, defaultStatus, trusted) {
  // trusted = true только для ручной продажи из таблицы; с сайта статус, оплата и цена берутся из таблицы, а не из запроса
  if (!d || !Array.isArray(d.items) || !d.items.length) throw new Error('В заказе нет товаров');
  if (d.items.length > 60) throw new Error('Слишком много позиций');
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var zs = ss.getSheetByName(SHEET_ORDERS), ps = ss.getSheetByName(SHEET_ITEMS);
    var tz = ss.getSpreadsheetTimeZone();
    var now = new Date();
    var num = clean_(d.number) || ('R-' + Utilities.formatDate(now, tz, 'ddMM') + '-' + Math.floor(1000 + Math.random() * 9000));

    // защита от повторной отправки того же заказа
    var last = zs.getLastRow();
    if (last > 1) {
      var nums = zs.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); });
      if (nums.indexOf(num) > -1) return num;
    }

    var stock = readStock_();
    var warnings = [], lines = [];
    var rows = d.items.map(function (it) {
      var key = clean_(it.key) || (clean_(it.sku) + '-' + clean_(it.size));
      var info = stock[key];
      var qty = Math.max(1, Math.min(999, parseInt(it.qty, 10) || 1));
      var price = info ? info.price : (trusted ? (Number(it.price) || 0) : 0); // цену неизвестного товара с сайта не принимаем
      if (trusted && Number(it.price) > 0) price = Number(it.price); // ручная продажа: можно указать цену со скидкой
      if (!info) warnings.push('Неизвестный артикул ' + key);
      else if (qty > info.remain) warnings.push('Не хватает остатка: ' + key + ' (есть ' + info.remain + ', заказано ' + qty + ')');
      if (info) info.remain -= qty;
      lines.push((info ? info.name : clean_(it.name)) + ' — ' + (info ? info.color : clean_(it.color)) + ', ' + (info ? info.size : clean_(it.size)) + ' × ' + qty + ' = ' + (qty * price) + ' ₸ [' + key + ']');
      return [num, now, key, info ? info.model : '', info ? info.name : clean_(it.name), info ? info.color : clean_(it.color),
              info ? info.size : clean_(it.size), qty, price];
    });

    // строка заказа
    var r = zs.getLastRow() + 1;
    var comment = [clean_(d.comment), warnings.join('; ')].filter(String).join(' | ');
    var address = [clean_(d.address)].filter(String).join(', ');
    zs.getRange(r, 1, 1, 18).setValues([[
      num, now, (trusted && SOURCES.indexOf(d.source) > -1) ? d.source : defaultSource,
      (trusted && STATUSES.indexOf(d.status) > -1) ? d.status : defaultStatus,
      (trusted && d.paid === 'Да') ? 'Да' : 'Нет', txt_(d.name), txt_(d.phone), txt_(d.place), txt_(address), txt_(d.payment),
      '=SUMIFS(Позиции!J:J,Позиции!A:A,A' + r + ')', trusted ? (Number(d.delivery) || '') : '', trusted ? txt_(d.track) : '',
      '=SUMIFS(Позиции!L:L,Позиции!A:A,A' + r + ')',
      '=IF(OR(D' + r + '="Отменён",D' + r + '="Возврат"),0,K' + r + '-N' + r + '-L' + r + ')',
      Utilities.formatDate(now, tz, 'yyyy-MM'), txt_(comment), txt_(lines.join('\n'))
    ]]);
    zs.getRange(r, 2).setNumberFormat('dd.MM.yyyy HH:mm');
    zs.getRange(r, 11, 1, 5).setNumberFormat('#,##0 "₸"');
    if (warnings.length) zs.getRange(r, 1, 1, 18).setBackground('#fff4cc');

    // позиции
    var p0 = ps.getLastRow() + 1;
    var full = rows.map(function (row, i) {
      var pr = p0 + i;
      return row.concat([
        '=H' + pr + '*I' + pr,
        '=IFERROR(VLOOKUP(C' + pr + ',Остатки!A:K,11,FALSE),0)',
        '=H' + pr + '*K' + pr,
        '=IFERROR(VLOOKUP(A' + pr + ',Заказы!A:D,4,FALSE),"")',
        '=IFERROR(VLOOKUP(C' + pr + ',Остатки!A:D,4,FALSE),"")'
      ]);
    });
    ps.getRange(p0, 1, full.length, 14).setValues(full);
    ps.getRange(p0, 2, full.length, 1).setNumberFormat('dd.MM.yyyy');
    ps.getRange(p0, 9, full.length, 4).setNumberFormat('#,##0 "₸"');

    SpreadsheetApp.flush();
    CacheService.getScriptCache().remove('stock');
    notifyTelegram_(num, d, lines, warnings, rows);
    return num;
  } finally {
    lock.releaseLock();
  }
}

// key -> {row, model, name, color, size, remain, price}
function readStock_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_STOCK);
  var n = sh.getLastRow() - 1;
  var map = {};
  if (n < 1) return map;
  sh.getRange(2, 1, n, 10).getValues().forEach(function (v, i) {
    if (!v[0]) return;
    map[String(v[0])] = { row: i + 2, model: v[1], name: v[2], cat: v[3], color: v[4], size: v[5], remain: Number(v[8]) || 0, price: Number(v[9]) || 0 };
  });
  return map;
}

// ================= ручная продажа =================
function showManualSale() {
  var html = HtmlService.createHtmlOutput(MANUAL_HTML).setWidth(720).setHeight(640);
  SpreadsheetApp.getUi().showModalDialog(html, 'Продажа вручную');
}

function getCatalogForDialog() {
  var map = readStock_();
  return Object.keys(map).map(function (k) {
    var v = map[k];
    return [k, v.name + ' · ' + v.color + ' · ' + v.size + ' · ' + v.price + ' ₸ · ост. ' + v.remain, v.price, v.remain];
  });
}

function addManualSale(form) {
  form.number = '';
  var num = recordOrder_(form, form.source || 'WhatsApp', form.status || 'Подтверждён', true);
  return num;
}

// ================= служебное =================
function checkSetup() {
  var url = ScriptApp.getService().getUrl();
  var ui = SpreadsheetApp.getUi();
  var names = SpreadsheetApp.getActiveSpreadsheet().getSheets().map(function (s) { return s.getName(); });
  var miss = [SHEET_ORDERS, SHEET_ITEMS, SHEET_STOCK].filter(function (n) { return names.indexOf(n) < 0; });
  ui.alert('Проверка',
    (miss.length ? 'Не найдены листы: ' + miss.join(', ') + '\n\n' : 'Листы на месте.\n\n') +
    (url ? 'Адрес веб-приложения (вставьте в config.json → order_webhook):\n' + url
         : 'Веб-приложение ещё не развернуто: Начать развертывание → Новое развертывание → Веб-приложение, доступ «Все».'),
    ui.ButtonSet.OK);
}

// При ручной правке: дата заказа → месяц; новая строка в «Позициях» → подставить товар и формулы
function onEdit(e) {
  try {
    var sh = e.range.getSheet(), r = e.range.getRow(), c = e.range.getColumn();
    if (r < 2) return;
    var tz = e.source.getSpreadsheetTimeZone();
    if (sh.getName() === SHEET_ORDERS) {
      if (c === 2) {
        var dt = sh.getRange(r, 2).getValue();
        if (dt instanceof Date) sh.getRange(r, 16).setValue(Utilities.formatDate(dt, tz, 'yyyy-MM'));
      }
      if (c === 1 && sh.getRange(r, 11).getFormula() === '') {
        sh.getRange(r, 11).setFormula('=SUMIFS(Позиции!J:J,Позиции!A:A,A' + r + ')');
        sh.getRange(r, 14).setFormula('=SUMIFS(Позиции!L:L,Позиции!A:A,A' + r + ')');
        sh.getRange(r, 15).setFormula('=IF(OR(D' + r + '="Отменён",D' + r + '="Возврат"),0,K' + r + '-N' + r + '-L' + r + ')');
        if (!sh.getRange(r, 2).getValue()) { var now = new Date(); sh.getRange(r, 2).setValue(now); sh.getRange(r, 16).setValue(Utilities.formatDate(now, tz, 'yyyy-MM')); }
        if (!sh.getRange(r, 4).getValue()) sh.getRange(r, 4).setValue('Подтверждён');
      }
    }
    if (sh.getName() === SHEET_ITEMS && c === 3) {
      var key = String(sh.getRange(r, 3).getValue());
      var info = readStock_()[key];
      if (info) {
        if (!sh.getRange(r, 4).getValue()) sh.getRange(r, 4, 1, 4).setValues([[info.model, info.name, info.color, info.size]]);
        if (!sh.getRange(r, 8).getValue()) sh.getRange(r, 8).setValue(1);
        if (!sh.getRange(r, 9).getValue()) sh.getRange(r, 9).setValue(info.price);
      }
      if (sh.getRange(r, 10).getFormula() === '') {
        sh.getRange(r, 10, 1, 5).setFormulas([[
          '=H' + r + '*I' + r, '=IFERROR(VLOOKUP(C' + r + ',Остатки!A:K,11,FALSE),0)', '=H' + r + '*K' + r,
          '=IFERROR(VLOOKUP(A' + r + ',Заказы!A:D,4,FALSE),"")', '=IFERROR(VLOOKUP(C' + r + ',Остатки!A:D,4,FALSE),"")']]);
      }
    }
    CacheService.getScriptCache().remove('stock');
  } catch (err) { console.error(err); }
}

function notifyTelegram_(num, d, lines, warnings, rows) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  var sum = rows.reduce(function (a, r) { return a + r[7] * r[8]; }, 0);
  var text = '🛍 Новый заказ ' + num + ' (' + (d.source || 'Сайт') + ')\n' + lines.join('\n') + '\nИтого за товары: ' + sum + ' ₸\n' +
    (d.name ? 'Клиент: ' + d.name + '\n' : '') + (d.phone ? 'Тел: ' + d.phone + '\n' : '') +
    (d.place ? 'Куда: ' + d.place + (d.address ? ', ' + d.address : '') + '\n' : '') + (warnings.length ? '⚠️ ' + warnings.join('; ') : '');
  try {
    UrlFetchApp.fetch('https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage', {
      method: 'post', contentType: 'application/json', muteHttpExceptions: true,
      payload: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text: text })
    });
  } catch (err) { console.error(err); }
}

function clean_(v) { return v === undefined || v === null ? '' : String(v).trim().slice(0, 500); }
// текст в ячейку без риска, что «+7 …» или «=…» станет формулой
function txt_(v) { v = clean_(v); return /^[=+\-@]/.test(v) ? "'" + v : v; }
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

// ================= форма ручной продажи =================
var MANUAL_HTML = '<!doctype html><html><head><base target="_top"><meta charset="utf-8"><style>' +
  'body{font:14px/1.4 Arial,sans-serif;color:#13233a;margin:0;padding:4px 6px}' +
  'label{display:block;font-weight:bold;margin:8px 0 3px}input,select,textarea{width:100%;box-sizing:border-box;padding:7px;border:1px solid #c5d0d8;border-radius:5px;font:inherit}' +
  '.row{display:flex;gap:8px}.row>*{flex:1}.it{display:flex;gap:6px;margin-bottom:6px}.it .k{flex:5}.it .q{flex:1}.it .p{flex:1.4}.it button{flex:0 0 32px}' +
  'button{padding:9px 14px;border:0;border-radius:6px;background:#13233a;color:#fff;font-weight:bold;cursor:pointer}button.alt{background:#eef3f6;color:#13233a}' +
  '#sum{font-weight:bold;font-size:16px;margin:10px 0}#msg{margin-top:8px}.err{color:#c8243a}.ok{color:#147a4b}' +
  '</style></head><body>' +
  '<div class="row"><div><label>Источник</label><select id="source"><option>WhatsApp</option><option>Kaspi</option><option>Instagram</option><option>OLX</option><option>Магазин</option><option>Сайт</option><option>Другое</option></select></div>' +
  '<div><label>Статус</label><select id="status"><option>Подтверждён</option><option>Новый</option><option>Отправлен</option><option>Доставлен</option></select></div>' +
  '<div><label>Оплачен</label><select id="paid"><option>Нет</option><option>Да</option></select></div></div>' +
  '<label>Товары (начните вводить артикул или название)</label><div id="items"></div>' +
  '<button class="alt" type="button" onclick="addItem()">+ Ещё товар</button><div id="sum"></div>' +
  '<div class="row"><div><label>Клиент</label><input id="name"></div><div><label>Телефон</label><input id="phone"></div></div>' +
  '<div class="row"><div><label>Район / город</label><input id="place" value="Астана"></div><div><label>Адрес</label><input id="address"></div></div>' +
  '<div class="row"><div><label>Способ оплаты</label><input id="payment" value="Kaspi"></div><div><label>Трек СДЭК</label><input id="track"></div></div>' +
  '<label>Комментарий</label><input id="comment">' +
  '<p><button type="button" id="save" onclick="save()">Записать продажу</button> <button class="alt" type="button" onclick="google.script.host.close()">Закрыть</button></p><div id="msg"></div>' +
  '<datalist id="cat"></datalist><script>' +
  'var CAT={};google.script.run.withSuccessHandler(function(rows){var dl=document.getElementById("cat");rows.forEach(function(r){CAT[r[0]]=r;var o=document.createElement("option");o.value=r[0];o.label=r[1];o.textContent=r[1];dl.appendChild(o);});addItem();}).getCatalogForDialog();' +
  'function addItem(){var d=document.createElement("div");d.className="it";d.innerHTML=\'<input class="k" list="cat" placeholder="SD057-01-S"><input class="q" type="number" min="1" value="1" title="Кол-во"><input class="p" type="number" min="0" placeholder="Цена" title="Цена за шт"><button class="alt" type="button" title="Убрать">×</button>\';' +
  'd.querySelector("button").onclick=function(){d.remove();calc();};var k=d.querySelector(".k"),p=d.querySelector(".p");k.onchange=function(){var r=CAT[k.value.trim()];if(r){p.value=r[2];k.title=r[1];}calc();};d.querySelector(".q").oninput=calc;p.oninput=calc;document.getElementById("items").appendChild(d);}' +
  'function items(){return Array.prototype.map.call(document.querySelectorAll(".it"),function(d){return{key:d.querySelector(".k").value.trim(),qty:+d.querySelector(".q").value||1,price:+d.querySelector(".p").value||0};}).filter(function(i){return i.key;});}' +
  'function calc(){var s=0;items().forEach(function(i){s+=i.qty*i.price;});document.getElementById("sum").textContent="Итого: "+s.toLocaleString("ru-RU")+" ₸";}' +
  'function val(id){return document.getElementById(id).value;}' +
  'function save(){var it=items(),m=document.getElementById("msg");var bad=it.filter(function(i){return !CAT[i.key];});' +
  'if(!it.length){m.className="err";m.textContent="Добавьте хотя бы один товар";return;}if(bad.length){m.className="err";m.textContent="Нет такого артикула: "+bad.map(function(b){return b.key;}).join(", ");return;}' +
  'document.getElementById("save").disabled=true;m.className="";m.textContent="Сохраняю…";' +
  'google.script.run.withSuccessHandler(function(n){m.className="ok";m.textContent="Записано: "+n+". Можно добавить следующую продажу.";document.getElementById("save").disabled=false;document.getElementById("items").innerHTML="";addItem();calc();})' +
  '.withFailureHandler(function(e){m.className="err";m.textContent="Ошибка: "+e.message;document.getElementById("save").disabled=false;})' +
  '.addManualSale({items:it,source:val("source"),status:val("status"),paid:val("paid"),name:val("name"),phone:val("phone"),place:val("place"),address:val("address"),payment:val("payment"),track:val("track"),comment:val("comment")});}' +
  '</script></body></html>';
