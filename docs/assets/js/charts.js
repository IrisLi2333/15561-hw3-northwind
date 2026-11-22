/* Draws every chart and fills every computed sentence on the page from the
   JSON files written by the Python analysis (python src/run_all.py).
   This file only formats and draws: it computes no metrics.
   Chart style adapted from Lieflat Charts
   (https://github.com/larashero3-dotcom/lieflat-charts), licensed under the
   PolyForm Noncommercial License 1.0.0:
   https://polyformproject.org/licenses/noncommercial/1.0.0 */
(function () {
  'use strict';
  const C = window.CLASS;
  const NS = 'http://www.w3.org/2000/svg';
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const NAVY = '#0B4F9E';            // waterfall totals
  const LIGHT = C.BLUE_RAMP[2];      // prior period
  const STAGGER = 45;

  /* ---------- formatting ---------- */
  const K = (v) => { const a = Math.abs(v); return (v < 0 ? '−' : '') + (a >= 1000 ? '$' + (a / 1000).toFixed(1) + 'K' : '$' + Math.round(a)); };
  const SK = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + K(Math.abs(v));
  const tickK = (v) => (v === 0 ? '$0' : (v < 0 ? '−' : '') + '$' + +(Math.abs(v) / 1000).toFixed(1) + 'K');
  const P = (v, d = 0) => (v * 100).toFixed(d) + '%';
  const SP = (v, d = 0) => (v == null ? 'new' : (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(d) + '%');
  const N = (v) => Math.round(v).toLocaleString('en-US');
  const monthLabel = (m) => { const [y, mo] = m.split('-'); return `${MONTHS[+mo - 1]} ${y}`; };

  /* ---------- SVG helpers ---------- */
  const el = (p, t, a = {}) => {
    const n = document.createElementNS(NS, t);
    for (const k in a) if (a[k] != null) n.setAttribute(k, a[k]);
    if (p) p.appendChild(n);
    return n;
  };
  const tx = (p, x, y, s, a = {}) => { const n = el(p, 'text', Object.assign({ x: +x.toFixed(1), y: +y.toFixed(1) }, a)); n.textContent = s; return n; };
  const tip = (n, s) => { el(n, 'title').textContent = s; return n; };
  const S = {
    label: { 'font-size': 12, 'font-weight': 500, fill: C.INK_2 },
    strong: { 'font-size': 12, 'font-weight': 600, fill: C.INK },
    value: { 'font-size': 12, 'font-weight': 700, fill: C.INK },
    tick: { 'font-size': 11, fill: C.FAINT },
    axis: { 'font-size': 11.5, fill: C.MUTED },
    small: { 'font-size': 11, fill: C.MUTED },
    quad: { 'font-size': 10.5, 'font-weight': 600, 'letter-spacing': '.08em', fill: C.FAINT },
  };
  const st = (base, extra) => Object.assign({}, base, extra);
  const delay = (i) => `animation-delay:${i * STAGGER}ms`;
  const lin = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  const nice = (span, n) => {
    const raw = span / n, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  };
  const ticks = (lo, hi, n = 5) => {
    const s = nice(hi - lo, n), out = [];
    for (let v = Math.floor(lo / s) * s; v <= hi + s * 0.999; v += s) out.push(+v.toFixed(6));
    return out;
  };
  // Ticks from the data minimum upward: no empty stretch below the smallest value.
  const ticksFrom = (lo, hi, n = 5) => {
    const t = ticks(Math.min(0, lo), hi, n);
    return { ticks: t.filter((v) => v >= lo || v === 0), lo: Math.min(0, lo) * 1.12, hi: t[t.length - 1] };
  };
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const ramp = (cols, t) => {
    t = Math.max(0, Math.min(1, t));
    const s = t * (cols.length - 1), i = Math.min(Math.floor(s), cols.length - 2), f = s - i;
    const a = hex(cols[i]), b = hex(cols[i + 1]);
    return `rgb(${a.map((v, j) => Math.round(v + (b[j] - v) * f)).join(',')})`;
  };
  const width = (box, min = 320) => Math.round(Math.max(min, box.clientWidth || 560));
  const frame = (box, W, H, label) => {
    box.innerHTML = '';
    return el(box, 'svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label });
  };
  const measure = (s, text, attrs) => {
    const n = tx(s, 0, 0, text, attrs); const w = n.getComputedTextLength(); n.remove(); return w;
  };
  const fit = (s, text, attrs, max) => {
    if (measure(s, text, attrs) <= max) return text;
    let t = text;
    while (t.length > 3 && measure(s, t + '…', attrs) > max) t = t.slice(0, -1);
    return t.trimEnd() + '…';
  };
  const legend = (s, x, y, items) => {
    let cx = x;
    items.forEach(([color, label, shape]) => {
      if (shape === 'line') el(s, 'line', { x1: cx, x2: cx + 16, y1: y - 4, y2: y - 4, stroke: color, 'stroke-width': 2.5, 'stroke-linecap': 'round' });
      else el(s, 'circle', { cx: cx + 5, cy: y - 4, r: 5, fill: color });
      const t = tx(s, cx + (shape === 'line' ? 22 : 15), y, label, S.small);
      cx += (shape === 'line' ? 22 : 15) + t.getComputedTextLength() + 18;
    });
  };
  // Place point labels without overlapping each other or the marks.
  const placeLabels = (s, items, b, avoid = []) => {
    const marks = items.map((i) => ({ x: i.x - i.r, y: i.y - i.r, w: i.r * 2, h: i.r * 2 }));
    const fixed = avoid.map((n) => { const r = n.getBBox(); return { x: r.x - 2, y: r.y - 2, w: r.width + 4, h: r.height + 4 }; });
    const placed = [];
    const over = (a, o) => !(a.x + a.w <= o.x || o.x + o.w <= a.x || a.y + a.h <= o.y || o.y + o.h <= a.y);
    items.map((it, j) => [it, j]).sort((a, c) => c[0].priority - a[0].priority).forEach(([it, j]) => {
      const w = measure(s, it.text, it.attrs), h = 15;
      const cands = [
        [it.x + it.r + 4, it.y - h / 2, 'start'], [it.x - it.r - 4 - w, it.y - h / 2, 'end'],
        [it.x - w / 2, it.y - it.r - 3 - h, 'middle'], [it.x - w / 2, it.y + it.r + 3, 'middle'],
      ];
      for (const [cx, cy, anchor] of cands) {
        const box = { x: cx, y: cy, w, h };
        if (cx < b.x0 || cx + w > b.x1 || cy < b.y0 || cy + h > b.y1) continue;
        if (placed.some((o) => over(box, o)) || fixed.some((o) => over(box, o)) || marks.some((o, k) => k !== j && over(box, o))) continue;
        placed.push(box);
        const x = anchor === 'start' ? cx : anchor === 'end' ? cx + w : cx + w / 2;
        tx(s, x, cy + h - 3.5, it.text, st(it.attrs, { 'text-anchor': anchor, class: 'fade', style: 'animation-delay:500ms' }));
        return;
      }
    });
  };
  const xAxis = (s, xs, x, y0, y1, fmt, yLabel) => xs.forEach((v) => {
    el(s, 'line', { x1: x(v), x2: x(v), y1: y0, y2: y1, stroke: v === 0 ? C.AXIS : C.GRID });
    tx(s, x(v), yLabel, fmt(v), st(S.tick, { 'text-anchor': 'middle' }));
  });
  const yAxis = (s, ys, y, x0, x1, fmt) => ys.forEach((v) => {
    el(s, 'line', { x1: x0, x2: x1, y1: y(v), y2: y(v), stroke: v === 0 ? C.AXIS : C.GRID });
    tx(s, x0 - 8, y(v) + 4, fmt(v), st(S.tick, { 'text-anchor': 'end' }));
  });

  /* ---------- Q1 ---------- */
  function monthly(box, q) {
    const d = q.monthly, W = width(box), H = W < 600 ? 280 : 340, m = { l: 52, r: 14, t: 30, b: 46 };
    const s = frame(box, W, H, 'Monthly net revenue with 3-month rolling average');
    const yt = ticks(0, Math.max(...d.map((r) => r.revenue)), 4);
    const y = lin(0, yt[yt.length - 1], H - m.b, m.t);
    const band = (W - m.l - m.r) / d.length, bw = band * 0.64, x = (i) => m.l + band * i + band / 2;
    yAxis(s, yt, y, m.l, W - m.r, tickK);
    tx(s, 0, 14, 'Net revenue (US$ thousands)', S.axis);
    const every = W < 600 ? 6 : 3;
    d.forEach((r, i) => {
      const yy = y(r.revenue);
      tip(el(s, 'rect', { x: x(i) - bw / 2, y: yy, width: bw, height: y(0) - yy, rx: Math.min(4, bw / 2),
        fill: C.BLUE, 'fill-opacity': 0.85, class: 'mark grow grow--up', style: delay(i) }),
        `${monthLabel(r.month)}: ${K(r.revenue)} net revenue from ${r.orders} orders` +
        (r.rolling_3m ? `, 3-month average ${K(r.rolling_3m)}` : ''));
      const mo = +r.month.split('-')[1];
      if ((mo - 7 + 12) % every === 0) tx(s, x(i), H - m.b + 17, `${MONTHS[mo - 1]} ’${r.month.slice(2, 4)}`, st(S.tick, { 'text-anchor': 'middle' }));
    });
    const pts = d.map((r, i) => (r.rolling_3m == null ? null : `${x(i).toFixed(1)} ${y(r.rolling_3m).toFixed(1)}`)).filter(Boolean);
    el(s, 'path', { d: 'M' + pts.join('L'), fill: 'none', stroke: C.ORANGE, 'stroke-width': 2.5, 'stroke-linejoin': 'round',
      'stroke-linecap': 'round', pathLength: 1, class: 'draw', style: 'animation-delay:500ms' });
    const first = d[0], last = d[d.length - 1];
    tx(s, x(0) - bw / 2, y(first.revenue) - 8, K(first.revenue), st(S.value, { class: 'fade' }));
    tx(s, x(d.length - 1) + bw / 2, y(last.revenue) - 8, K(last.revenue), st(S.value, { 'text-anchor': 'end', class: 'fade' }));
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Month of order', st(S.axis, { 'text-anchor': 'middle' }));
  }

  function waterfall(box, steps, label) {
    const W = width(box), row = 30, labW = Math.min(196, W * 0.38), m = { l: labW + 12, r: 66, t: 6, b: 42 };
    const H = m.t + row * steps.length + m.b;
    const s = frame(box, W, H, label);
    let run = 0;
    const bars = steps.map((b) => {
      if (b.kind === 'total') { run = b.value; return Object.assign({}, b, { a: 0, b: b.value }); }
      const a = run; run += b.value; return Object.assign({}, b, { a, b: run });
    });
    const xt = ticks(0, Math.max(...bars.map((b) => Math.max(b.a, b.b))), W < 480 ? 3 : 4);
    const x = lin(0, xt[xt.length - 1], m.l, W - m.r);
    xAxis(s, xt, x, m.t, H - m.b, tickK, H - m.b + 17);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Net revenue (US$ thousands)', st(S.axis, { 'text-anchor': 'middle' }));
    bars.forEach((b, i) => {
      const yc = m.t + row * i + row / 2, lo = Math.min(b.a, b.b), hi = Math.max(b.a, b.b);
      if (i > 0) {
        const at = b.kind === 'total' ? b.b : b.a;
        el(s, 'line', { x1: x(at), x2: x(at), y1: yc - row + 8, y2: yc - 8, stroke: C.AXIS, 'stroke-dasharray': '2 3' });
      }
      const total = b.kind === 'total';
      const fill = total ? NAVY : b.kind === 'up' ? C.BLUE : C.ORANGE;
      tip(el(s, 'rect', { x: x(lo), y: yc - 8, width: Math.max(x(hi) - x(lo), 2), height: 16, rx: 6, fill,
        class: `mark grow grow--${b.kind === 'down' ? 'left' : 'right'}`, style: delay(i) }),
        `${b.label}: ${total ? K(b.value) : SK(b.value)}`);
      const attrs = total ? S.strong : S.label;
      tx(s, m.l - 12, yc + 4, fit(s, b.label, attrs, labW), st(attrs, { 'text-anchor': 'end' }));
      tx(s, x(hi) + 6, yc + 4, total ? K(b.value) : SK(b.value), st(S.value, { class: 'fade', style: delay(i) }));
    });
  }

  function pareto(box, q) {
    const W = width(box), H = Math.round(Math.min(420, Math.max(300, W * 0.72))), m = { l: 48, r: 18, t: 28, b: 46 };
    const s = frame(box, W, H, 'Customer concentration Pareto curve');
    const x = lin(0, 1, m.l, W - m.r), y = lin(0, 1, H - m.b, m.t);
    const t5 = [0, 0.25, 0.5, 0.75, 1];
    xAxis(s, t5, x, m.t, H - m.b, (v) => P(v), H - m.b + 17);
    yAxis(s, t5, y, m.l, W - m.r, (v) => P(v));
    tx(s, 0, 14, 'Cumulative share of revenue', S.axis);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Share of customers, largest first', st(S.axis, { 'text-anchor': 'middle' }));
    el(s, 'line', { x1: x(0), y1: y(0), x2: x(1), y2: y(1), stroke: C.AXIS, 'stroke-dasharray': '3 4' });
    const path = (curve) => 'M' + [[0, 0]].concat(curve.map((c) => [c.customer_share, c.revenue_share]))
      .map(([a, b]) => `${x(a).toFixed(1)} ${y(b).toFixed(1)}`).join('L');
    const pr = q.concentration.prior, cu = q.concentration.current;
    el(s, 'path', { d: path(pr.curve), fill: 'none', stroke: LIGHT, 'stroke-width': 2, pathLength: 1, class: 'draw' });
    el(s, 'path', { d: path(cu.curve), fill: 'none', stroke: C.BLUE, 'stroke-width': 2.75, pathLength: 1, class: 'draw', style: 'animation-delay:200ms' });
    // 80% of revenue
    const p80 = cu.curve[cu.customers_for_80pct - 1];
    el(s, 'line', { x1: x(0), x2: x(p80.customer_share), y1: y(0.8), y2: y(0.8), stroke: C.MUTED, 'stroke-dasharray': '2 3' });
    el(s, 'line', { x1: x(p80.customer_share), x2: x(p80.customer_share), y1: y(0.8), y2: y(0), stroke: C.MUTED, 'stroke-dasharray': '2 3' });
    tip(el(s, 'circle', { cx: x(p80.customer_share), cy: y(p80.revenue_share), r: 4.5, fill: C.BLUE, stroke: '#fff', 'stroke-width': 1.5, class: 'fade' }),
      `${cu.customers_for_80pct} of ${cu.customers} customers bring 80% of revenue`);
    const note = W < 480 ? `${cu.customers_for_80pct} of ${cu.customers} customers → 80%`
      : `${cu.customers_for_80pct} of ${cu.customers} customers (${P(cu.share_of_customers_for_80pct)}) → 80% of revenue`;
    const nw = measure(s, note, S.small), nx = Math.min(x(p80.customer_share) + 8, W - m.r - nw);
    tx(s, nx, y(0.8) + 16, note, st(S.small, { class: 'fade' }));
    // top 10
    const t10 = cu.curve[9];
    tip(el(s, 'circle', { cx: x(t10.customer_share), cy: y(t10.revenue_share), r: 6, fill: C.ORANGE, stroke: '#fff', 'stroke-width': 1.5, class: 'fade' }),
      `Top 10 customers: ${P(cu.top10_share, 1)} of revenue (prior period ${P(pr.top10_share, 1)})`);
    tx(s, x(t10.customer_share) + 10, y(t10.revenue_share) + 16, `Top 10: ${P(cu.top10_share, 1)}`, st(S.value, { class: 'fade' }));
  }

  function cohortColumns(box, q) {
    const co = q.cohort_revenue, n = co.quarters.length, W = width(box), H = W < 600 ? 300 : 340;
    const m = { l: 52, r: 14, t: 30, b: 48 };
    const s = frame(box, W, H, 'Quarterly revenue by customer cohort');
    const totals = co.quarters.map((_, j) => co.cohorts.reduce((a, c) => a + c.revenue[j], 0));
    const yt = ticks(0, Math.max(...totals), 4);
    const y = lin(0, yt[yt.length - 1], H - m.b, m.t);
    const band = (W - m.l - m.r) / n, bw = Math.min(band * 0.56, 90), x = (j) => m.l + band * j + band / 2;
    yAxis(s, yt, y, m.l, W - m.r, tickK);
    tx(s, 0, 14, 'Net revenue (US$ thousands)', S.axis);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Quarter of order', st(S.axis, { 'text-anchor': 'middle' }));
    co.quarters.forEach((qt, j) => {
      let base = 0;
      co.cohorts.forEach((c, i) => {
        const v = c.revenue[j];
        if (v <= 0) return;
        const y0 = y(base + v), h = y(base) - y(base + v);
        tip(el(s, 'rect', { x: x(j) - bw / 2, y: y0, width: bw, height: Math.max(h - 1, 0.5), rx: 3,
          fill: C.CATEGORICAL[i], class: 'mark grow grow--up', style: delay(j * 2 + i) }),
          `${qt}, ${c.cohort} cohort: ${K(v)} (${P(v / totals[j])} of the quarter)`);
        base += v;
      });
      const narrow = band < 64;
      if (!narrow || j === 0 || j === n - 1) {
        const ax = narrow ? (j === 0 ? x(j) - bw / 2 : x(j) + bw / 2) : x(j);
        tx(s, ax, y(totals[j]) - 8, K(totals[j]), st(S.value, { 'text-anchor': j === n - 1 && narrow ? 'end' : j === 0 && narrow ? 'start' : 'middle',
          class: 'fade', style: delay(j * 2) }));
      }
      if (narrow) {
        const [yr, qq] = qt.split(' ');
        tx(s, x(j), H - m.b + 15, qq, st(S.tick, { 'text-anchor': 'middle' }));
        tx(s, x(j), H - m.b + 27, `’${yr.slice(2)}`, st(S.tick, { 'text-anchor': 'middle' }));
      } else tx(s, x(j), H - m.b + 17, qt, st(S.tick, { 'text-anchor': 'middle' }));
    });
  }

  /* ---------- Q2 ---------- */
  function bubbles(box, q) {
    const W = width(box), H = Math.round(Math.min(480, Math.max(320, W * 0.48))), m = { l: 58, r: 20, t: 30, b: 48 };
    const s = frame(box, W, H, 'Market portfolio: size against dollar growth');
    const d = q.markets;
    const lo = Math.min(...d.map((r) => r.current)) * 0.75, hi = Math.max(...d.map((r) => r.current)) * 1.3;
    const x = (v) => m.l + ((Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))) * (W - m.l - m.r);
    const yt = ticks(Math.min(...d.map((r) => r.change)) - 4000, Math.max(...d.map((r) => r.change)) + 6000, 5);
    const y = lin(yt[0], yt[yt.length - 1], H - m.b, m.t);
    yAxis(s, yt, y, m.l, W - m.r, tickK);
    [2500, 5000, 10000, 20000, 50000, 100000, 200000].filter((v) => v >= lo && v <= hi).forEach((v) => {
      el(s, 'line', { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b, stroke: C.GRID });
      tx(s, x(v), H - m.b + 17, tickK(v), st(S.tick, { 'text-anchor': 'middle' }));
    });
    tx(s, 0, 14, 'Change vs Jul 1996–Apr 1997 (US$ thousands)', S.axis);
    tx(s, (m.l + W - m.r) / 2, H - 6, W < 600 ? 'Net revenue (US$ thousands, log scale)'
      : 'Net revenue, Jul 1997–Apr 1998 (US$ thousands, log scale)', st(S.axis, { 'text-anchor': 'middle' }));
    const med = q.market_medians, dash = { stroke: C.MUTED, 'stroke-opacity': 0.55, 'stroke-dasharray': '4 4' };
    el(s, 'line', st(dash, { x1: x(med.current), x2: x(med.current), y1: m.t, y2: H - m.b }));
    el(s, 'line', st(dash, { x1: m.l, x2: W - m.r, y1: y(med.change), y2: y(med.change) }));
    const quads = [
      tx(s, W - m.r - 4, m.t + 12, 'INVEST', st(S.quad, { 'text-anchor': 'end' })),
      tx(s, m.l + 6, m.t + 12, 'DEVELOP', S.quad),
      tx(s, W - m.r - 4, H - m.b - 8, 'DEFEND', st(S.quad, { 'text-anchor': 'end' })),
      tx(s, m.l + 6, H - m.b - 8, 'DEPRIORITIZE', S.quad),
    ];
    const items = [];
    d.slice().sort((a, b) => b.customers - a.customers).forEach((r, i) => {
      const cx = x(r.current), cy = y(r.change), rad = 4 + Math.sqrt(r.customers) * (W < 600 ? 2.6 : 3.6);
      tip(el(s, 'circle', { cx, cy, r: rad, fill: r.account_led ? C.ORANGE : C.BLUE, 'fill-opacity': 0.8, stroke: '#fff',
        'stroke-width': 1.5, class: 'mark fade', style: delay(i) }),
        `${r.market} (${r.quadrant})\nNet revenue ${K(r.current)} (${SK(r.change)}, ${SP(r.growth)})\n` +
        `${r.customers} active customers, top customer brings ${P(r.top_customer_share)} of market revenue\n` +
        `${r.category_depth.toFixed(1)} of 8 categories per customer, priority score ${Math.round(r.score)}`);
      items.push({ x: cx, y: cy, r: rad, text: r.market, priority: r.current, attrs: S.label });
    });
    placeLabels(s, items, { x0: m.l, x1: W - m.r, y0: m.t, y1: H - m.b }, quads);
  }

  function dumbbell(box, q) {
    const d = q.categories.slice().sort((a, b) => b.current - a.current);
    const W = width(box), row = 50, labW = Math.min(120, W * 0.3), m = { l: labW + 12, r: 112, t: 8, b: 42 };
    const H = m.t + row * d.length + m.b;
    const s = frame(box, W, H, 'Category revenue, prior vs current');
    const xt = ticks(0, Math.max(...d.map((r) => r.current)), W < 480 ? 3 : 4);
    const x = lin(0, xt[xt.length - 1], m.l, W - m.r);
    xAxis(s, xt, x, m.t, H - m.b, tickK, H - m.b + 17);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Net revenue (US$ thousands)', st(S.axis, { 'text-anchor': 'middle' }));
    d.forEach((r, i) => {
      const yc = m.t + row * i + row / 2;
      tx(s, m.l - 12, yc + 4, fit(s, r.category, S.label, labW), st(S.label, { 'text-anchor': 'end' }));
      el(s, 'line', { x1: x(r.prior), x2: x(r.current), y1: yc, y2: yc, stroke: C.BLUE_RAMP[1], 'stroke-width': 4,
        'stroke-linecap': 'round', class: 'grow grow--right', style: delay(i) });
      el(s, 'circle', { cx: x(r.prior), cy: yc, r: 5, fill: LIGHT, class: 'fade', style: delay(i) });
      tip(el(s, 'circle', { cx: x(r.current), cy: yc, r: 7, fill: C.BLUE, class: 'mark fade', style: delay(i) }),
        `${r.category}: ${K(r.prior)} → ${K(r.current)} (${SK(r.change)}, ${SP(r.growth)})\n${r.customers} customers, ${P(r.share)} of revenue`);
      const v = tx(s, x(r.current) + 12, yc + 4, K(r.current), st(S.value, { class: 'fade', style: delay(i) }));
      tx(s, x(r.current) + 18 + v.getComputedTextLength(), yc + 4, SP(r.growth), st(S.small, { class: 'fade', style: delay(i) }));
    });
  }

  function heatmap(box, q) {
    const g = q.grid, W = Math.max(760, width(box)), labW = 118, top = 52, row = 24;
    const colW = (W - labW - 8) / g.categories.length, H = top + row * g.markets.length + 6;
    const s = frame(box, W, H, 'Revenue by market and category');
    s.style.minWidth = W + 'px';
    const max = Math.max(...g.revenue.flat());
    const gaps = new Set(q.cross_sell_gaps.map((c) => c.market + '|' + c.category));
    const priority = new Set(q.priority_markets);
    g.categories.forEach((c, j) => {
      const cx = labW + colW * j + colW / 2, parts = measure(s, c, S.label) > colW - 6 ? c.replace('/', '/ ').split(' ') : [c];
      const lines = parts.length > 2 ? [parts[0], parts.slice(1).join(' ')] : parts;
      lines.forEach((ln, k) => tx(s, cx, top - 10 - (lines.length - 1 - k) * 14, ln.trim(), st(S.label, { 'text-anchor': 'middle' })));
    });
    g.markets.forEach((mk, i) => {
      const y0 = top + row * i, total = g.revenue[i].reduce((a, b) => a + b, 0);
      tx(s, labW - 10, y0 + row / 2 + 4, mk, st(priority.has(mk) ? S.strong : S.label, { 'text-anchor': 'end' }));
      g.categories.forEach((c, j) => {
        const v = g.revenue[i][j], t = Math.sqrt(v / max), x0 = labW + colW * j;
        tip(el(s, 'rect', { x: x0 + 1.5, y: y0 + 1.5, width: colW - 3, height: row - 3, rx: 4,
          fill: v > 0 ? ramp(C.BLUE_RAMP, 0.08 + t * 0.92) : '#F3F6FA', class: 'mark fade', style: `animation-delay:${(i + j) * 18}ms` }),
          `${mk}, ${c}: ${K(v)}\n${P(total ? v / total : 0)} of the market's revenue vs ${P(g.company_share[j])} company-wide`);
        if (gaps.has(mk + '|' + c)) el(s, 'rect', { x: x0 + 2.5, y: y0 + 2.5, width: colW - 5, height: row - 5, rx: 3.5,
          fill: 'none', stroke: C.ORANGE, 'stroke-width': 2, 'pointer-events': 'none' });
        tx(s, x0 + colW / 2, y0 + row / 2 + 4, v > 0 ? K(v) : '—', st(S.tick, { 'text-anchor': 'middle', 'pointer-events': 'none',
          fill: v > 0 && t > 0.55 ? '#fff' : v > 0 ? C.INK_2 : C.FAINT }));
      });
    });
  }

  function teamTable(box, q) {
    const rows = q.team.map((r) => `<tr>
        <td><strong>${r.name}</strong><span>${r.title}</span></td><td>${r.based_in}</td>
        <td class="num">${r.orders_prior} → <b>${r.orders}</b></td>
        <td class="num">${r.customers_prior} → <b>${r.customers}</b></td>
        <td class="num">${r.countries_prior} → <b>${r.countries}</b></td>
        <td class="num"><b>${K(r.revenue)}</b></td></tr>`).join('');
    const t = q.team_summary;
    box.innerHTML = `<div class="ctable-wrap"><table class="ctable">
      <thead><tr><th>Employee</th><th>Based in</th><th class="num">Orders</th><th class="num">Customers</th>
      <th class="num">Countries</th><th class="num">Revenue</th></tr></thead><tbody>${rows}</tbody>
      <tfoot><tr><td>Average per employee</td><td></td>
      <td class="num">${t.avg_orders.prior.toFixed(0)} → <b>${t.avg_orders.current.toFixed(0)}</b></td>
      <td class="num">${t.avg_customers.prior.toFixed(0)} → <b>${t.avg_customers.current.toFixed(0)}</b></td>
      <td class="num">${t.avg_countries.prior.toFixed(0)} → <b>${t.avg_countries.current.toFixed(0)}</b></td><td></td></tr></tfoot>
      </table></div>`;
  }

  /* ---------- Q3 ---------- */
  function products(box, q) {
    const d = q.product_movers, gains = d.filter((r) => r.change >= 0);
    const W = width(box), row = 24, gap = 16, labW = Math.min(204, W * 0.42), m = { l: labW + 12, r: 64, t: 6, b: 42 };
    const H = m.t + row * d.length + gap + m.b;
    const s = frame(box, W, H, 'Largest product gains and every decline');
    const tf = ticksFrom(Math.min(...d.map((r) => r.change)), Math.max(...d.map((r) => r.change)), W < 480 ? 3 : 4);
    const x = lin(tf.lo, tf.hi, m.l, W - m.r);
    xAxis(s, tf.ticks, x, m.t, H - m.b, tickK, H - m.b + 17);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Change in net revenue (US$ thousands)', st(S.axis, { 'text-anchor': 'middle' }));
    d.forEach((r, i) => {
      const yc = m.t + row * i + row / 2 + (i >= gains.length ? gap : 0), up = r.change >= 0;
      const x0 = up ? x(0) : x(r.change), x1 = up ? x(r.change) : x(0);
      tx(s, m.l - 12, yc + 4, fit(s, r.product, S.label, labW), st(S.label, { 'text-anchor': 'end' }));
      tip(el(s, 'rect', { x: x0, y: yc - 6, width: Math.max(x1 - x0, 2), height: 12, rx: 6, fill: up ? C.BLUE : C.ORANGE,
        class: `mark grow grow--${up ? 'right' : 'left'}`, style: delay(i) }),
        `${r.product} (${r.category}): ${K(r.prior)} → ${K(r.current)} (${SK(r.change)})`);
      tx(s, (up ? x1 : x(0)) + 6, yc + 4, SK(r.change), st(S.value, { class: 'fade', style: delay(i) }));
    });
    if (gains.length < d.length) {
      const ys = m.t + row * gains.length + gap / 2;
      el(s, 'line', { x1: 0, x2: W, y1: ys, y2: ys, stroke: C.GRID });
    }
  }

  function marketDecline(box, q) {
    const d = q.declining_markets, W = width(box), row = 56, labW = Math.min(250, W * 0.48), m = { l: labW + 12, r: 70, t: 8, b: 42 };
    const H = m.t + row * d.length + m.b;
    const s = frame(box, W, H, 'Declining markets split into customer and spend effects');
    const lo = Math.min(...d.map((r) => Math.min(0, r.customer_effect) + Math.min(0, r.spend_effect)));
    const hi = Math.max(0, ...d.map((r) => Math.max(0, r.customer_effect) + Math.max(0, r.spend_effect)));
    const xt = ticks(lo, hi, W < 480 ? 3 : 4);
    const x = lin(xt[0], xt[xt.length - 1], m.l, W - m.r);
    xAxis(s, xt, x, m.t, H - m.b, tickK, H - m.b + 17);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Change in net revenue (US$ thousands)', st(S.axis, { 'text-anchor': 'middle' }));
    d.forEach((r, i) => {
      const yc = m.t + row * i + row / 2;
      const lead = q.declining_market_customers[r.market][0];
      tx(s, m.l - 12, yc - 3, `${r.market}: ${SK(r.change)} (${SP(r.growth)})`, st(S.strong, { 'text-anchor': 'end' }));
      tx(s, m.l - 12, yc + 13, fit(s, `Led by ${lead.customer} (${SK(lead.change)})`, S.small, labW), st(S.small, { 'text-anchor': 'end' }));
      let neg = 0, pos = 0;
      [[r.customer_effect, C.BLUE, 'Customer-count effect'], [r.spend_effect, C.ORANGE, 'Spend-per-customer effect']].forEach(([v, color, name], k) => {
        if (Math.abs(v) < 0.5) return;
        const a = v < 0 ? neg + v : pos, b = v < 0 ? neg : pos + v;
        if (v < 0) neg += v; else pos += v;
        tip(el(s, 'rect', { x: x(a), y: yc - 9, width: Math.max(x(b) - x(a), 2), height: 18, rx: 5, fill: color,
          class: `mark grow grow--${v < 0 ? 'left' : 'right'}`, style: delay(i * 2 + k) }),
          `${r.market}, ${name}: ${SK(v)}\n${r.customers_prior} → ${r.customers} active customers`);
        if (x(b) - x(a) > 46) tx(s, (x(a) + x(b)) / 2, yc + 4, SK(v), st(S.tick, { 'text-anchor': 'middle', fill: '#fff', 'font-weight': 600, 'pointer-events': 'none' }));
      });
    });
  }

  function rhythm(box, q) {
    const R = q.rhythm, d = R.customers.filter((r) => r.status !== 'Too few orders');
    const W = width(box), H = Math.round(Math.min(440, Math.max(300, W * 0.42))), m = { l: 52, r: 20, t: 30, b: 48 };
    const s = frame(box, W, H, 'Customer order rhythm');
    // Square-root scales: they spread the dense cluster of frequent buyers and keep
    // the proportional reference lines (1x and 2x the usual gap) straight.
    const STEPS = [0, 10, 25, 50, 100, 200, 300, 400];
    const xm = STEPS.find((v) => v >= Math.max(...d.map((r) => r.median_gap)));
    const ym = STEPS.find((v) => v >= Math.max(...d.map((r) => r.days_since_last)));
    const sq = (d1, r0, r1) => (v) => r0 + (Math.sqrt(Math.max(0, v)) / Math.sqrt(d1)) * (r1 - r0);
    const x = sq(xm, m.l, W - m.r), y = sq(ym, H - m.b, m.t);
    xAxis(s, STEPS.filter((v) => v <= xm), x, m.t, H - m.b, (v) => String(v), H - m.b + 17);
    yAxis(s, STEPS.filter((v) => v <= ym), y, m.l, W - m.r, (v) => String(v));
    tx(s, 0, 14, W < 600 ? 'Days since last order (square-root scale)' : 'Days since last order, at 6 May 1998 (square-root scale)', S.axis);
    tx(s, (m.l + W - m.r) / 2, H - 6, 'Usual days between orders, median (square-root scale)', st(S.axis, { 'text-anchor': 'middle' }));
    const e1 = Math.min(xm, ym), e2 = Math.min(xm, ym / 2);
    el(s, 'line', { x1: x(0), y1: y(0), x2: x(e1), y2: y(e1), stroke: C.AXIS, 'stroke-dasharray': '2 4' });
    el(s, 'line', { x1: x(0), y1: y(0), x2: x(e2), y2: y(e2 * 2), stroke: C.ORANGE, 'stroke-width': 1.5, 'stroke-dasharray': '5 4' });
    // Line labels only where there is room; the legend explains both lines.
    const refs = W < 600 ? [] : [
      tx(s, x(e2) + 6, y(e2 * 2) + 12, '2× usual gap', st(S.small, { fill: C.ORANGE, 'font-weight': 600 })),
      tx(s, x(e1) - 8, y(e1) + 16, '1× usual gap', st(S.small, { 'text-anchor': 'end' })),
    ];
    const maxT = Math.max(...d.map((r) => r.trailing_12m_revenue));
    const items = [];
    d.slice().sort((a, b) => b.trailing_12m_revenue - a.trailing_12m_revenue).forEach((r, i) => {
      const over = r.status === 'Overdue', rad = 3 + Math.sqrt(r.trailing_12m_revenue / maxT) * 11;
      const cx = x(r.median_gap), cy = y(r.days_since_last);
      tip(el(s, 'circle', { cx, cy, r: rad, fill: over ? C.ORANGE : C.BLUE, 'fill-opacity': over ? 0.9 : 0.4,
        stroke: '#fff', 'stroke-width': 1, class: 'mark fade', style: `animation-delay:${i * 12}ms` }),
        `${r.customer} (${r.market})\nOrders every ${r.median_gap} days; last order ${r.days_since_last} days ago ` +
        `(${r.overdue_ratio.toFixed(1)}× usual gap)\n${K(r.trailing_12m_revenue)} in the last 12 months`);
      if (over) items.push({ x: cx, y: cy, r: rad, text: r.customer, priority: r.trailing_12m_revenue, attrs: S.label });
    });
    placeLabels(s, items, { x0: m.l, x1: W - m.r, y0: m.t, y1: H - m.b }, refs);
    const table = document.createElement('div');
    table.className = 'ctable-wrap';
    table.innerHTML = `<table class="ctable"><thead><tr><th>Overdue customer</th><th>Market</th><th class="num">Usual gap</th>
      <th class="num">Days since last order</th><th class="num">× usual gap</th><th class="num">Revenue, last 12 months</th></tr></thead><tbody>` +
      R.overdue.map((r) => `<tr><td><strong>${r.customer}</strong></td><td>${r.market}</td><td class="num">${r.median_gap} days</td>
      <td class="num">${r.days_since_last}</td><td class="num">${r.overdue_ratio.toFixed(1)}×</td><td class="num"><b>${K(r.trailing_12m_revenue)}</b></td></tr>`).join('') +
      `</tbody><tfoot><tr><td>Total at risk</td><td></td><td></td><td></td><td></td><td class="num"><b>${K(R.revenue_at_risk)}</b> (${P(R.revenue_at_risk_share, 1)})</td></tr></tfoot></table>`;
    box.appendChild(table);
  }

  function cohort(box, q) {
    const c = q.cohort_retention, d = c.cohorts.filter((r) => c.shown.includes(r.cohort));
    const offsets = Math.max(...d.map((r) => r.retention.length)) - 1;
    const W = width(box), labW = W < 480 ? 96 : 132, top = 42, row = 44, colW = (W - labW - 6) / offsets;
    const H = top + row * d.length + 8;
    const s = frame(box, W, H, 'Cohort retention by quarter');
    tx(s, labW + (W - labW) / 2, 13, 'Quarters after the first order', st(S.axis, { 'text-anchor': 'middle' }));
    for (let o = 1; o <= offsets; o++) tx(s, labW + colW * (o - 0.5), top - 8, `+${o}`, st(S.label, { 'text-anchor': 'middle' }));
    d.forEach((r, i) => {
      const y0 = top + row * i;
      tx(s, labW - 10, y0 + row / 2 - 1, r.cohort.replace('Q', ' Q'), st(S.strong, { 'text-anchor': 'end' }));
      tx(s, labW - 10, y0 + row / 2 + 13, `${r.size} customers`, st(S.small, { 'text-anchor': 'end' }));
      const partial = c.partial_offsets[r.cohort];
      for (let o = 1; o <= offsets; o++) {
        const v = r.retention[o];
        if (v == null) continue;
        const x0 = labW + colW * (o - 1);
        tip(el(s, 'rect', { x: x0 + 2, y: y0 + 2, width: colW - 4, height: row - 4, rx: 6, fill: ramp(C.BLUE_RAMP, v),
          class: 'mark fade', style: `animation-delay:${(i + o) * 30}ms` }),
          `${r.cohort} cohort (${r.size} customers): ${P(v)} ordered in quarter +${o}` + (o === partial ? ' (quarter to 6 May 1998 only)' : ''));
        tx(s, x0 + colW / 2, y0 + row / 2 + 4, P(v) + (o === partial ? '*' : ''), st(S.value, { 'text-anchor': 'middle',
          fill: v > 0.55 ? '#fff' : C.INK, 'pointer-events': 'none' }));
      }
    });
  }

  /* ---------- legends ---------- */
  // A subtitle arrives as lines: the measure first, then one legend item per line
  // ("Blue: ...", "Dashed orange line: ..."). Each item gets a swatch drawn from its key.
  const swatch = (key) => {
    const k = key.toLowerCase();
    const color = k.includes('light orange') ? C.CATEGORICAL[3] : k.includes('light blue') ? LIGHT : k.includes('darker blue') ? 'ramp'
      : k.includes('dark blue') ? NAVY : k.includes('orange') ? C.ORANGE : k.includes('blue') ? C.BLUE
      : (k.includes('dashed') || k.includes('dotted') || k.includes('grey line')) ? C.MUTED : null;
    if (!color || k.includes('text')) return '<i class="sw sw--none"></i>';
    const dashed = k.includes('dashed') || k.includes('dotted');
    const shape = k.includes('outline') ? 'outline' : (k.includes('line') || k.includes('diagonal')) ? 'line'
      : (k.includes('dot') || k.includes('bubble')) ? 'dot' : 'square';
    const style = shape === 'line' ? `border-top: 2.5px ${dashed ? 'dashed' : 'solid'} ${color}`
      : shape === 'outline' ? `border: 2px solid ${color}`
      : `background: ${color === 'ramp' ? `linear-gradient(90deg, ${C.BLUE_RAMP[1]}, ${C.BLUE_RAMP[5]})` : color}`;
    return `<i class="sw sw--${shape}" style="${style}"></i>`;
  };
  const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  function renderSub(node, text) {
    const [lead, ...items] = text.split('\n');
    node.innerHTML = `<span class="chart__lead">${esc(lead)}</span>` + (items.length
      ? `<span class="chart__legend-list${items.length > 4 ? ' is-multi' : ''}">` + items.map((line) => {
        const i = line.indexOf(': ');
        if (i < 0 || i > 40) return `<span class="lg"><i class="sw sw--none"></i><span>${esc(line)}</span></span>`;
        const key = line.slice(0, i);
        return `<span class="lg">${swatch(key)}<span><b>${esc(key)}:</b> ${esc(line.slice(i + 2))}</span></span>`;
      }).join('') + '</span>' : '');
    node.classList.remove('tbd');
  }

  function fillMethods(D) {
    document.querySelectorAll('[data-method]').forEach((dl) => {
      dl.innerHTML = D[dl.dataset.method].text.method
        .map(([term, def]) => `<div><dt>${esc(term)}</dt><dd>${esc(def)}</dd></div>`).join('');
    });
  }

  /* ---------- page wiring ---------- */
  const get = (obj, path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);

  function fillText(D) {
    document.querySelectorAll('[data-text]').forEach((n) => {
      const v = get(D, n.dataset.text);
      if (typeof v !== 'string') return;
      if (n.classList.contains('chart__sub')) renderSub(n, v);
      else { n.textContent = v; n.classList.remove('tbd'); }
    });
    const k = D.q1.kpis, fmt = { revenue: K, orders: N, customers: N, aov: (v) => '$' + N(v) };
    document.querySelectorAll('[data-kpi]').forEach((n) => {
      const key = n.dataset.kpi, v = k[key];
      n.querySelector('.kpi__value').textContent = fmt[key](v.current);
      const delta = n.querySelector('.kpi__delta');
      delta.textContent = `${SP(v.growth)} vs ${fmt[key](v.prior)}`;
      delta.classList.remove('tbd');
    });
  }

  const RENDER = {
    'q1-monthly': (b, D) => monthly(b, D.q1),
    'q1-bridge': (b, D) => waterfall(b, D.q1.waterfalls[b.dataset.view || 'drivers'], 'Revenue bridge'),
    'q1-pareto': (b, D) => pareto(b, D.q1),
    'q1-cohorts': (b, D) => cohortColumns(b, D.q1),
    'q2-markets': (b, D) => bubbles(b, D.q2),
    'q2-categories': (b, D) => dumbbell(b, D.q2),
    'q2-team': (b, D) => teamTable(b, D.q2),
    'q2-grid': (b, D) => heatmap(b, D.q2),
    'q3-bridge': (b, D) => waterfall(b, D.q3.waterfall, 'Customer revenue bridge'),
    'q3-products': (b, D) => products(b, D.q3),
    'q3-rhythm': (b, D) => rhythm(b, D.q3),
    'q3-markets': (b, D) => marketDecline(b, D.q3),
    'q3-cohort': (b, D) => cohort(b, D.q3),
  };

  function wireToggles(D) {
    document.querySelectorAll('[data-seg]').forEach((seg) => {
      const box = document.querySelector(`[data-chart="${seg.dataset.seg}"]`);
      const fig = seg.closest('.fig');
      seg.querySelectorAll('button').forEach((btn) => btn.addEventListener('click', () => {
        seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
        const view = btn.dataset.view;
        box.dataset.view = view;
        fig.querySelector('.chart__title').textContent = D.q1.text.bridge[view].title;
        renderSub(fig.querySelector('.chart__sub'), D.q1.text.bridge[view].sub);
        fig.querySelector('.chart__takeaway p').textContent = D.q1.text.bridge[view].takeaway;
        box.classList.remove('chart--static');
        RENDER[box.dataset.chart](box, D);
      }));
    });
  }

  function draw(D) {
    fillText(D);
    fillMethods(D);
    wireToggles(D);
    const boxes = [...document.querySelectorAll('[data-chart]')];
    const drawn = new Map();
    const render = (box) => { RENDER[box.dataset.chart](box, D); drawn.set(box, box.clientWidth); };
    // Draw every chart on the page being shown; pages are short, so no lazy loading is needed.
    const drawPage = () => boxes.forEach((box) => { if (box.offsetParent && !drawn.has(box)) render(box); });
    drawPage();
    window.addEventListener('pagechange', () => setTimeout(drawPage, 0));
    const refit = () => drawn.forEach((w, box) => {
      if (!box.offsetParent || Math.abs(box.clientWidth - w) < 4) return;   // hidden page, or unchanged
      box.classList.add('chart--static');
      render(box);
    });
    let timer;
    window.addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(refit, 150); });
    window.addEventListener('pagechange', () => setTimeout(refit, 0));
  }

  Promise.all(['q1', 'q2', 'q3'].map((n) => fetch(`data/${n}.json`).then((r) => {
    if (!r.ok) throw new Error(`${n}.json: ${r.status}`);
    return r.json();
  })))
    .then(([q1, q2, q3]) => draw({ q1, q2, q3 }))
    .catch((err) => {
      console.error(err);
      document.querySelectorAll('[data-chart]').forEach((b) => {
        b.innerHTML = '<p class="chart__error">Chart data could not be loaded. Serve the docs/ folder over HTTP (see README).</p>';
      });
    });
})();
