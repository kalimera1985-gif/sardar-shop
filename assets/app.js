/* SARDAR — логика магазина: корзина, фильтры, карточка товара, оформление заказа.
   Данные товаров приходят из assets/catalog.js (window.SHOP), который генерирует build.py */
(function () {
  'use strict';
  var SHOP = window.SHOP || { cfg: {}, products: {} };
  var CFG = SHOP.cfg;
  var ROOT = document.documentElement.getAttribute('data-root') || '';
  var KEY = 'sardar_cart_v1';
  var NB = ' ';

  // ---------- утилиты ----------
  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); }
  function fmt(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, NB) + NB + '₸'; }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function sizeLabel(s, p) { return s === 'ONE' ? (p && p.g === 'kids' ? 'Детский' : 'Единый') : s; }
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || 'null'); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  var memCart = null;
  function img(h) { return ROOT + 'images/' + h + '.webp'; }

  // индекс вариантов по артикулу
  var BY_SKU = {};
  Object.keys(SHOP.products).forEach(function (id) {
    var p = SHOP.products[id]; p.id = id;
    p.v.forEach(function (v) { BY_SKU[v[0]] = { p: p, sku: v[0], color: v[1], img: v[2], sizes: v[3] }; });
  });

  // ---------- живые остатки из Google Таблицы (если подключена) ----------
  var STOCK_KEY = 'sardar_stock_v1';
  function applyStock(map) {
    if (!map) return;
    Object.keys(map).forEach(function (key) {
      var i = key.lastIndexOf('-'); if (i < 0) return;
      var v = BY_SKU[key.slice(0, i)], size = key.slice(i + 1);
      if (v && size in v.sizes) v.sizes[size] = Math.max(0, +map[key] || 0);
    });
  }
  var cachedStock = store(STOCK_KEY);
  if (cachedStock && cachedStock.t > Date.now() - 10 * 60 * 1000) applyStock(cachedStock.s);
  function refreshAll() {
    $$('.card[data-id]').forEach(function (el) {
      var p = SHOP.products[el.getAttribute('data-id')]; if (!p) return;
      var left = p.v.reduce(function (a, v) { return a + Object.keys(v[3]).reduce(function (b, s) { return b + v[3][s]; }, 0); }, 0);
      el.classList.toggle('soldout', left === 0);
      var b = $('.badge', el);
      if (left === 0) { if (!b) { b = document.createElement('span'); $('.ph', el).appendChild(b); } b.className = 'badge low'; b.textContent = 'Нет в наличии'; }
    });
    if (window.__pdpRefresh) window.__pdpRefresh();
    var before = (store(KEY) || []).length; var c = getCart();
    if (c.length < before) toast('Часть товаров из корзины уже раскупили — корзина обновлена');
    setCart(c);
  }
  if (CFG.order_webhook && window.fetch) {
    fetch(CFG.order_webhook + (CFG.order_webhook.indexOf('?') > -1 ? '&' : '?') + 'action=stock')
      .then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.stock) { applyStock(d.stock); store(STOCK_KEY, { t: Date.now(), s: d.stock }); refreshAll(); } })
      .catch(function () { });
  }

  var toastT;
  function toast(msg) {
    var t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove('show'); }, 2400);
  }

  // ---------- корзина ----------
  function getCart() {
    var c = store(KEY); if (!c && memCart) c = memCart;
    c = Array.isArray(c) ? c : [];
    return c.filter(function (it) { var v = BY_SKU[it.sku]; return v && v.sizes[it.size] > 0 && it.qty > 0; })
      .map(function (it) { var max = BY_SKU[it.sku].sizes[it.size]; return { sku: it.sku, size: it.size, qty: Math.min(it.qty, max) }; });
  }
  function setCart(c) { memCart = c; store(KEY, c); renderBadge(); renderDrawer(); if (window.__renderCheckout) window.__renderCheckout(); }
  function addToCart(sku, size, qty) {
    var c = getCart(); var max = BY_SKU[sku].sizes[size] || 0;
    var ex = c.filter(function (i) { return i.sku === sku && i.size === size; })[0];
    if (ex) ex.qty = Math.min(ex.qty + qty, max); else c.push({ sku: sku, size: size, qty: Math.min(qty, max) });
    setCart(c);
  }
  function cartTotals(c) {
    var sub = 0, n = 0;
    c.forEach(function (i) { sub += BY_SKU[i.sku].p.p * i.qty; n += i.qty; });
    return { sub: sub, n: n };
  }
  function renderBadge() {
    var n = cartTotals(getCart()).n;
    $$('[data-cart-count]').forEach(function (el) { el.textContent = n; });
  }
  function lineHTML(it, i) {
    var v = BY_SKU[it.sku], p = v.p, max = v.sizes[it.size];
    return '<div class="line" data-i="' + i + '">' +
      '<a href="' + ROOT + p.u + '?c=' + encodeURIComponent(v.sku) + '"><img src="' + img(v.img) + '" alt="' + esc(p.n + ', ' + v.color) + '" loading="lazy"></a>' +
      '<div><a href="' + ROOT + p.u + '?c=' + encodeURIComponent(v.sku) + '">' + esc(p.n) + '</a>' +
      '<div class="v">' + esc(v.color) + ' · размер ' + esc(sizeLabel(it.size, p)) + ' · ' + fmt(p.p) + '</div>' +
      '<div class="qty" aria-label="Количество"><button type="button" data-q="-1" aria-label="Меньше">−</button>' +
      '<input type="number" inputmode="numeric" min="1" max="' + max + '" value="' + it.qty + '" aria-label="Количество">' +
      '<button type="button" data-q="1" aria-label="Больше">+</button></div></div>' +
      '<div class="end"><b>' + fmt(p.p * it.qty) + '</b><button type="button" class="rm">Удалить</button></div></div>';
  }
  function bindLines(box) {
    $$('.line', box).forEach(function (row) {
      var i = +row.getAttribute('data-i');
      function setQ(q) { var c = getCart(); if (!c[i]) return; var max = BY_SKU[c[i].sku].sizes[c[i].size]; c[i].qty = Math.max(1, Math.min(max, q || 1)); if (q > max) toast('В наличии только ' + max + ' шт'); setCart(c); }
      $$('[data-q]', row).forEach(function (b) { b.onclick = function () { var c = getCart(); setQ(c[i].qty + (+b.getAttribute('data-q'))); }; });
      $('input', row).onchange = function () { setQ(parseInt(this.value, 10)); };
      $('.rm', row).onclick = function () { var c = getCart(); c.splice(i, 1); setCart(c); };
    });
  }
  function delivery(zoneId, sub) {
    var z = (CFG.delivery.zones || []).filter(function (z) { return z.id === zoneId; })[0];
    if (!z) return { zone: null, price: 0, text: 'выберите район' };
    if (z.price === null || z.price === undefined) return { zone: z, price: 0, text: 'отдельно', tbd: true };
    if (CFG.delivery.free_from && sub >= CFG.delivery.free_from) return { zone: z, price: 0, text: 'бесплатно' };
    return { zone: z, price: z.price, text: fmt(z.price) };
  }
  function freeBar(sub) {
    var f = CFG.delivery.free_from; if (!f) return '';
    if (sub >= f) return '<div class="free-bar">Доставка по Астане и пригороду — <b>бесплатно</b><div class="bar"><i style="width:100%"></i></div></div>';
    return '<div class="free-bar">До бесплатной доставки осталось <b>' + fmt(f - sub) + '</b><div class="bar"><i style="width:' + Math.round(sub / f * 100) + '%"></i></div></div>';
  }
  function renderDrawer() {
    var d = $('#drawer'); if (!d) return;
    var c = getCart(), t = cartTotals(c);
    $('.items', d).innerHTML = c.length ? c.map(lineHTML).join('') :
      '<div class="empty"><p>Корзина пока пустая.</p><a class="btn alt" href="' + ROOT + 'katalog/">Перейти в каталог</a></div>';
    bindLines($('.items', d));
    $('footer', d).hidden = !c.length;
    $('[data-sub]', d).textContent = fmt(t.sub);
    $('[data-free]', d).innerHTML = freeBar(t.sub);
  }
  function openDrawer() { var d = $('#drawer'); if (!d) return; renderDrawer(); d.classList.add('open'); document.body.style.overflow = 'hidden'; $('.x', d).focus(); }
  function closeDrawer() { var d = $('#drawer'); if (!d) return; d.classList.remove('open'); document.body.style.overflow = ''; }
  $$('[data-open-cart]').forEach(function (b) { b.addEventListener('click', function (e) { if (location.pathname.indexOf('/korzina') > -1) return; e.preventDefault(); openDrawer(); }); });
  $$('#drawer .shade, #drawer .x').forEach(function (b) { b.addEventListener('click', closeDrawer); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeDrawer(); var f = $('.filters.open'); if (f) f.classList.remove('open'); } });

  // ---------- каталог: фильтры ----------
  var cat = $('#catalog');
  if (cat) (function () {
    var cards = $$('.card', cat), grid = $('.grid', cat);
    var state = { g: [], c: [], s: [], cf: [], pr: '', q: '', sort: '' };
    var preset = cat.getAttribute('data-preset'); // например "c=dresses" или "g=women"
    function readURL() {
      var sp = new URLSearchParams(location.search);
      ['g', 'c', 's', 'cf'].forEach(function (k) { state[k] = sp.get(k) ? sp.get(k).split(',') : []; });
      state.pr = sp.get('pr') || ''; state.q = sp.get('q') || ''; state.sort = sp.get('sort') || '';
      if (preset && !location.search) { var kv = preset.split('='); state[kv[0]] = [kv[1]]; }
    }
    function writeURL() {
      var sp = new URLSearchParams();
      ['g', 'c', 's', 'cf'].forEach(function (k) { if (state[k].length) sp.set(k, state[k].join(',')); });
      if (state.pr) sp.set('pr', state.pr); if (state.q) sp.set('q', state.q); if (state.sort) sp.set('sort', state.sort);
      var qs = sp.toString();
      try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { }
    }
    function syncUI() {
      $$('[data-f]', cat).forEach(function (b) {
        var k = b.getAttribute('data-f'), v = b.getAttribute('data-v');
        var on = k === 'pr' ? state.pr === v : state[k].indexOf(v) > -1;
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var si = $('#q-cat'); if (si && si.value !== state.q) si.value = state.q;
      $$('.hdr-search input').forEach(function (i) { if (document.activeElement !== i) i.value = state.q; });
      var so = $('#sort', cat); if (so) so.value = state.sort;
    }
    function inPrice(p) {
      if (!state.pr) return true; var r = state.pr.split('-'); var lo = +r[0] || 0, hi = r[1] ? +r[1] : Infinity;
      return p >= lo && p < hi;
    }
    function apply() {
      var q = state.q.trim().toLowerCase().split(/\s+/).filter(Boolean), shown = 0;
      cards.forEach(function (el) {
        var d = el.dataset, ok = true;
        if (state.g.length && state.g.indexOf(d.g) < 0 && !(d.g === 'unisex' && (state.g.indexOf('women') > -1 || state.g.indexOf('men') > -1))) ok = false;
        if (ok && state.c.length && state.c.indexOf(d.c) < 0) ok = false;
        if (ok && state.s.length) { var ss = d.s.split(' '); ok = state.s.some(function (s) { return ss.indexOf(s) > -1; }); }
        if (ok && state.cf.length) { var cf = d.cf.split(' '); ok = state.cf.some(function (s) { return cf.indexOf(s) > -1; }); }
        if (ok && !inPrice(+d.p)) ok = false;
        if (ok && q.length) ok = q.every(function (w) { return d.n.indexOf(w) > -1; });
        el.hidden = !ok; if (ok) shown++;
      });
      var sorted = cards.slice();
      if (state.sort === 'cheap') sorted.sort(function (a, b) { return a.dataset.p - b.dataset.p; });
      else if (state.sort === 'expensive') sorted.sort(function (a, b) { return b.dataset.p - a.dataset.p; });
      else if (state.sort === 'choice') sorted.sort(function (a, b) { return b.dataset.vc - a.dataset.vc; });
      else sorted.sort(function (a, b) { return a.dataset.i - b.dataset.i; });
      sorted.forEach(function (el) { grid.appendChild(el); });
      var cn = $('[data-count]', cat); if (cn) cn.textContent = shown + ' ' + plural(shown, 'товар', 'товара', 'товаров');
      var em = $('.empty', cat); if (em) em.hidden = shown > 0;
      var ap = $('.f-apply', cat); if (ap) ap.textContent = 'Показать ' + shown + ' ' + plural(shown, 'товар', 'товара', 'товаров');
      syncUI(); writeURL();
    }
    $$('[data-f]', cat).forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        var k = b.getAttribute('data-f'), v = b.getAttribute('data-v');
        if (k === 'pr') state.pr = state.pr === v ? '' : v;
        else { var i = state[k].indexOf(v); if (i > -1) state[k].splice(i, 1); else state[k].push(v); }
        apply();
      });
    });
    var so = $('#sort', cat); if (so) so.onchange = function () { state.sort = so.value; apply(); };
    var reset = $$('[data-reset]', cat);
    reset.forEach(function (r) { r.onclick = function () { state = { g: [], c: [], s: [], cf: [], pr: '', q: '', sort: state.sort }; preset = null; apply(); }; });
    var fo = $('.f-open', cat), fl = $('.filters', cat);
    if (fo) fo.onclick = function () { fl.classList.add('open'); };
    $$('.f-close, .f-apply', cat).forEach(function (b) { b.onclick = function () { fl.classList.remove('open'); grid.scrollIntoView(); }; });
    // поиск из шапки — живой на странице каталога
    $$('.hdr-search').forEach(function (f) {
      var inp = $('input', f);
      inp.addEventListener('input', function () { state.q = inp.value; apply(); });
      f.addEventListener('submit', function (e) { e.preventDefault(); state.q = inp.value; apply(); cat.scrollIntoView(); });
    });
    readURL(); apply();
    if (state.q && location.search.indexOf('q=') > -1) setTimeout(function () { cat.scrollIntoView(); }, 50);
  })();
  function plural(n, a, b, c) { n = Math.abs(n) % 100; var n1 = n % 10; if (n > 10 && n < 20) return c; if (n1 > 1 && n1 < 5) return b; if (n1 === 1) return a; return c; }

  // ---------- карточка товара ----------
  var pdp = $('#pdp');
  if (pdp) (function () {
    var p = SHOP.products[pdp.getAttribute('data-id')]; if (!p) return;
    document.body.classList.add('is-pdp');
    var sel = { v: null, size: null, qty: 1 };
    var startSku = new URLSearchParams(location.search).get('c');
    var mainImg = $('.gal-main img', pdp), colorName = $('[data-color-name]', pdp), sizeBox = $('.size-btns', pdp),
      hint = $('.size-hint', pdp), msg = $('.buy-msg', pdp), qIn = $('.buy .qty input', pdp), skuEls = $$('[data-sku-text]', pdp);
    function variant(sku) { return BY_SKU[sku]; }
    function pickColor(sku, keepSize) {
      var v = variant(sku); if (!v) return; sel.v = v;
      $$('.colors button', pdp).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-sku') === sku ? 'true' : 'false'); });
      $$('.gal-thumbs button', pdp).forEach(function (b) { b.setAttribute('aria-current', b.getAttribute('data-sku') === sku ? 'true' : 'false'); });
      mainImg.src = img(v.img); mainImg.alt = p.n + ', цвет ' + v.color;
      colorName.textContent = v.color; skuEls.forEach(function (el) { el.textContent = v.sku; });
      var sizes = Object.keys(v.sizes);
      sizeBox.innerHTML = sizes.map(function (s) {
        var q = v.sizes[s]; var low = q <= 5;
        return '<button type="button" data-size="' + s + '" aria-pressed="false"' + (q ? '' : ' disabled') + '>' + esc(sizeLabel(s, p)) +
          '<small class="' + (low ? 'low' : '') + '">' + (q === 0 ? 'нет' : low ? 'осталось ' + q : 'есть') + '</small></button>';
      }).join('');
      if (!(keepSize && v.sizes[sel.size])) sel.size = sizes.length === 1 ? sizes[0] : null;
      $$('button', sizeBox).forEach(function (b) {
        if (b.getAttribute('data-size') === sel.size) b.setAttribute('aria-pressed', 'true');
        b.onclick = function () { sel.size = b.getAttribute('data-size'); $$('button', sizeBox).forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }); updQty(); msg.textContent = ''; msg.className = 'buy-msg'; };
      });
      updQty();
      try { history.replaceState(null, '', location.pathname + '?c=' + encodeURIComponent(sku)); } catch (e) { }
    }
    function updQty() {
      var max = sel.size ? sel.v.sizes[sel.size] : 99;
      sel.qty = Math.max(1, Math.min(sel.qty, max)); qIn.value = sel.qty; qIn.max = max;
      hint.textContent = sel.size ? ('Размер ' + sizeLabel(sel.size, p) + ': в наличии ' + max + ' шт') : 'Выберите размер';
    }
    $$('.colors button, .gal-thumbs button', pdp).forEach(function (b) { b.onclick = function () { pickColor(b.getAttribute('data-sku'), true); }; });
    $$('.buy .qty [data-q]', pdp).forEach(function (b) { b.onclick = function () { sel.qty += +b.getAttribute('data-q'); updQty(); }; });
    qIn.onchange = function () { sel.qty = parseInt(qIn.value, 10) || 1; updQty(); };
    function tryAdd() {
      if (!sel.size) { msg.textContent = 'Сначала выберите размер'; msg.className = 'buy-msg err'; sizeBox.scrollIntoView({ block: 'center' }); return false; }
      addToCart(sel.v.sku, sel.size, sel.qty);
      msg.textContent = 'Добавлено: ' + sel.v.color + ', ' + sizeLabel(sel.size, p) + ' × ' + sel.qty; msg.className = 'buy-msg ok';
      return true;
    }
    $$('[data-add]', pdp.parentNode).forEach(function (b) { b.onclick = function () { if (tryAdd()) openDrawer(); }; });
    var one = $('[data-buy-now]', pdp); if (one) one.onclick = function () { if (tryAdd()) location.href = ROOT + 'korzina/'; };
    pickColor(variant(startSku) && variant(startSku).p === p ? startSku : p.v[0][0]);
    window.__pdpRefresh = function () { if (sel.v) pickColor(sel.v.sku, true); };
    // липкая кнопка на мобильном
    var sb = $('.sticky-buy'), anchor = $('.buy', pdp);
    if (sb && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (en) { var vis = en[0].isIntersecting || en[0].boundingClientRect.top > 0; sb.classList.toggle('show', !vis); document.body.classList.toggle('has-sticky', !vis); }).observe(anchor);
    }
  })();

  // ---------- оформление заказа ----------
  var co = $('#checkout');
  if (co) (function () {
    var form = $('form', co), list = $('[data-lines]', co);
    var zoneBox = $('[data-zones]', co);
    zoneBox.innerHTML = (CFG.delivery.zones || []).map(function (z, i) {
      return '<label class="radio"><input type="radio" name="zone" value="' + z.id + '"' + (i === 0 ? ' checked' : '') + '><span><b>' + esc(z.name) + '</b><small>' + (CFG.delivery.carrier || '') + ', ' + esc(z.eta || '') + '</small></span><span class="pr" data-zp="' + z.id + '"></span></label>';
    }).join('') + (CFG.delivery.pickup && CFG.delivery.pickup.enabled ? '<label class="radio"><input type="radio" name="zone" value="pickup"><span><b>Самовывоз</b><small>' + esc(CFG.delivery.pickup.address || '') + '</small></span><span class="pr">0 ₸</span></label>' : '');
    var payBox = $('[data-pay]', co);
    payBox.innerHTML = (CFG.payment_methods || []).map(function (m, i) { return '<label class="radio"><input type="radio" name="pay" value="' + esc(m) + '"' + (i === 0 ? ' checked' : '') + '><span><b>' + esc(m) + '</b></span></label>'; }).join('');
    var saved = store('sardar_buyer') || {};
    ['name', 'phone', 'street', 'flat', 'city'].forEach(function (k) { if (saved[k] && form[k]) form[k].value = saved[k]; });
    if (saved.zone) { var r = form.querySelector('input[name=zone][value="' + saved.zone + '"]'); if (r) r.checked = true; }

    function zoneVal() { var r = form.querySelector('input[name=zone]:checked'); return r ? r.value : ''; }
    function calc() {
      var c = getCart(), t = cartTotals(c), z = zoneVal();
      var d = z === 'pickup' ? { price: 0, text: 'самовывоз' } : delivery(z, t.sub);
      return { c: c, sub: t.sub, n: t.n, d: d, total: t.sub + d.price, zone: z };
    }
    function render() {
      var r = calc();
      $('[data-empty]', co).hidden = r.c.length > 0; $('[data-full]', co).hidden = r.c.length === 0;
      list.innerHTML = r.c.map(lineHTML).join(''); bindLines(list);
      (CFG.delivery.zones || []).forEach(function (z) { var el = $('[data-zp="' + z.id + '"]', co); if (el) el.textContent = delivery(z.id, r.sub).text; });
      $('[data-s-sub]', co).textContent = fmt(r.sub) + ' (' + r.n + ' шт)';
      $('[data-s-del]', co).textContent = r.d.tbd ? 'оплачивается отдельно' : (r.d.price ? fmt(r.d.price) : (r.d.text || '0 ₸'));
      $('[data-s-total]', co).textContent = fmt(r.total);
      var dn = $('[data-s-delnote]', co); if (dn) dn.hidden = !r.d.tbd;
      $('[data-s-free]', co).innerHTML = freeBar(r.sub);
      var cityF = $('[data-city-field]', co); if (cityF) cityF.hidden = r.zone !== 'kz';
      var adrF = $('[data-addr]', co); if (adrF) adrF.hidden = r.zone === 'pickup';
    }
    window.__renderCheckout = render;
    form.addEventListener('change', function (e) { if (e.target.name === 'zone') render(); });

    // маска телефона +7 (7XX) XXX-XX-XX
    var ph = form.phone;
    ph.addEventListener('input', function () {
      var d = ph.value.replace(/\D/g, ''); if (d[0] === '8') d = '7' + d.slice(1); if (d && d[0] !== '7') d = '7' + d; d = d.slice(0, 11);
      var o = '+7'; if (d.length > 1) o += ' (' + d.slice(1, 4); if (d.length >= 4) o += ') ' + d.slice(4, 7); if (d.length >= 7) o += '-' + d.slice(7, 9); if (d.length >= 9) o += '-' + d.slice(9, 11);
      ph.value = d ? o : '';
    });
    function bad(name, on) { var f = form[name] && form[name].closest('.field'); if (f) f.classList.toggle('bad', on); return on; }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var r = calc(); if (!r.c.length) return;
      var errs = 0;
      errs += bad('name', form.name.value.trim().length < 2) ? 1 : 0;
      errs += bad('phone', form.phone.value.replace(/\D/g, '').length !== 11) ? 1 : 0;
      if (r.zone !== 'pickup') errs += bad('street', form.street.value.trim().length < 3) ? 1 : 0;
      if (r.zone === 'kz') errs += bad('city', form.city.value.trim().length < 2) ? 1 : 0;
      if (errs) { var f = $('.field.bad', form); if (f) { f.scrollIntoView({ block: 'center' }); $('input', f).focus(); } return; }
      var now = new Date();
      var num = 'SD-' + String(now.getDate()).padStart(2, '0') + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(Math.floor(1000 + Math.random() * 9000));
      var zone = (CFG.delivery.zones || []).filter(function (z) { return z.id === r.zone; })[0];
      var place = r.zone === 'pickup' ? 'Самовывоз' : (r.zone === 'kz' ? form.city.value.trim() : zone.name);
      var pay = (form.querySelector('input[name=pay]:checked') || {}).value || '';
      var L = [];
      L.push('Здравствуйте! Новый заказ ' + num + ' с сайта ' + (CFG.store_name || ''));
      L.push('');
      r.c.forEach(function (it, i) {
        var v = BY_SKU[it.sku];
        L.push((i + 1) + ') ' + v.p.n + ' — ' + v.color + ', размер ' + sizeLabel(it.size, v.p) + ', ' + it.qty + ' шт × ' + fmt(v.p.p) + ' = ' + fmt(v.p.p * it.qty) + ' [арт. ' + v.sku + ']');
      });
      L.push('');
      L.push('Товары: ' + fmt(r.sub));
      L.push('Доставка (' + (r.zone === 'pickup' ? 'самовывоз' : (CFG.delivery.carrier + ', ' + place)) + '): ' + (r.d.tbd ? 'оплачивается отдельно по тарифу СДЭК' : (r.d.price ? fmt(r.d.price) : 'бесплатно')));
      L.push('ИТОГО за товары: ' + fmt(r.total) + (r.d.tbd ? ' (+ доставка СДЭК отдельно)' : ''));
      L.push('');
      L.push('Имя: ' + form.name.value.trim());
      L.push('Телефон: ' + form.phone.value.trim());
      if (r.zone !== 'pickup') L.push('Адрес: ' + place + ', ' + form.street.value.trim() + (form.flat.value.trim() ? ', кв./офис ' + form.flat.value.trim() : ''));
      if (pay) L.push('Оплата: ' + pay);
      if (form.comment.value.trim()) L.push('Комментарий: ' + form.comment.value.trim());
      var text = L.join('\n');
      var waUrl = 'https://wa.me/' + String(CFG.whatsapp || '').replace(/\D/g, '') + '?text=' + encodeURIComponent(text);

      store('sardar_buyer', { name: form.name.value, phone: form.phone.value, street: form.street.value, flat: form.flat.value, city: form.city.value, zone: r.zone });
      if (CFG.order_webhook) {
        try {
          fetch(CFG.order_webhook, { method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
            body: JSON.stringify({ number: num, created: now.toISOString(), name: form.name.value.trim(), phone: form.phone.value.trim(), place: place, address: form.street.value.trim() + ' ' + form.flat.value.trim(), payment: pay, comment: form.comment.value.trim(), subtotal: r.sub, delivery: r.d.price, total: r.total,
              source: 'Сайт', items: r.c.map(function (it) { var v = BY_SKU[it.sku]; return { key: v.sku + '-' + it.size, sku: v.sku, name: v.p.n, color: v.color, size: it.size, qty: it.qty, price: v.p.p }; }), text: text }) });
          try { localStorage.removeItem(STOCK_KEY); } catch (e2) { }
        } catch (err) { }
      }
      store('sardar_last_order', { num: num, text: text, wa: waUrl });
      setCart([]);
      showDone({ num: num, text: text, wa: waUrl });
      window.open(waUrl, '_blank') || (location.href = waUrl);
    });
    function showDone(o) {
      $('[data-full]', co).hidden = true; $('[data-empty]', co).hidden = true;
      var d = $('[data-done]', co); d.hidden = false;
      $('[data-num]', d).textContent = o.num;
      $('[data-wa-again]', d).href = o.wa;
      $('[data-copy]', d).onclick = function () {
        (navigator.clipboard ? navigator.clipboard.writeText(o.text) : Promise.reject()).then(function () { toast('Текст заказа скопирован'); }, function () { prompt('Скопируйте текст заказа:', o.text); });
      };
      window.scrollTo(0, 0);
    }
    render();
  })();

  renderBadge();
})();
