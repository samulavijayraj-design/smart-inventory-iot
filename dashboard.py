"""Web dashboard for the smart inventory system (FR2).

Shows the current stock, reorder point and status of each item, the stock
history with reorder alerts, and the list of alerts. Reads the SQLite
database written by the backend.

Usage:  python dashboard.py      then open http://localhost:8050
"""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config


def query(sql, args=()):
    db = sqlite3.connect(config.DB_PATH)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(sql, args)]
    db.close()
    return rows


def summary():
    items = query("SELECT * FROM items ORDER BY id")
    for it in items:
        last = query("SELECT qty, sim_time FROM measurements WHERE item=? "
                     "ORDER BY sim_time DESC LIMIT 1", (it["id"],))
        it["qty"] = last[0]["qty"] if last else None
        it["sim_time"] = last[0]["sim_time"] if last else None
        it["alerts"] = query("SELECT COUNT(*) AS n FROM alerts WHERE item=?", (it["id"],))[0]["n"]
        if it["qty"] is None:
            it["status"] = "no data"
        elif it["qty"] == 0:
            it["status"] = "out of stock"
        elif it["qty"] <= it["rop"]:
            it["status"] = "reorder"
        else:
            it["status"] = "ok"
    return items


def history(item):
    return {"measurements": query("SELECT sim_time, qty FROM measurements WHERE item=? "
                                  "ORDER BY sim_time", (item,)),
            "alerts": query("SELECT sim_time, qty FROM alerts WHERE item=? "
                            "ORDER BY sim_time", (item,))}


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Inventory Dashboard</title>
<style>
  :root { --ok:#2e8b57; --warn:#d66e14; --bad:#c62828; --blue:#1f77b4;
          --bg:#f4f6f8; --card:#fff; --text:#1d2733; --muted:#5f6b7a; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;
         background:var(--bg); color:var(--text); }
  header { background:var(--blue); color:#fff; padding:14px 24px; }
  header h1 { margin:0; font-size:20px; }
  header p { margin:2px 0 0; font-size:13px; opacity:.85; }
  main { padding:20px 24px; max-width:1100px; margin:auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
  .card { background:var(--card); border-radius:8px; padding:14px 16px; cursor:pointer;
          border-left:6px solid var(--ok); box-shadow:0 1px 3px rgba(0,0,0,.08); }
  .card.reorder { border-left-color:var(--warn); }
  .card.out { border-left-color:var(--bad); }
  .card.sel { outline:2px solid var(--blue); }
  .card h2 { margin:0 0 4px; font-size:15px; }
  .qty { font-size:30px; font-weight:700; }
  .meta { font-size:13px; color:var(--muted); }
  .badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px;
           color:#fff; background:var(--ok); }
  .reorder .badge { background:var(--warn); } .out .badge { background:var(--bad); }
  section { background:var(--card); border-radius:8px; padding:14px 16px; margin-top:16px;
            box-shadow:0 1px 3px rgba(0,0,0,.08); }
  section h3 { margin:0 0 8px; font-size:15px; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th, td { text-align:left; padding:5px 8px; border-bottom:1px solid #e3e7ec; }
  svg text { font-size:11px; fill:var(--muted); }
</style></head><body>
<header><h1>Smart Inventory Dashboard</h1>
<p>Storeroom &middot; weighing shelves &middot; data via MQTT (TLS)</p></header>
<main>
  <div class="cards" id="cards"></div>
  <section><h3 id="chart-title">Stock history</h3><svg id="chart" height="260"></svg></section>
  <section><h3>Reorder alerts</h3><table id="alerts"></table></section>
</main>
<script>
let selected = null;
async function load() {
  const items = await (await fetch('/api/summary')).json();
  if (!selected) selected = items[0].id;
  document.getElementById('cards').innerHTML = items.map(it => {
    const cls = it.status === 'reorder' ? 'reorder' : it.status === 'out of stock' ? 'out' : '';
    return `<div class="card ${cls} ${it.id===selected?'sel':''}" onclick="selected='${it.id}';load()">
      <h2>${it.name}</h2><div class="qty">${it.qty ?? '–'} <span class="meta">pcs</span></div>
      <div class="meta">ROP ${it.rop} pcs &middot; order ${it.order_qty} pcs &middot; ${it.alerts} alerts</div>
      <span class="badge">${it.status}</span></div>`;
  }).join('');
  const it = items.find(i => i.id === selected);
  const h = await (await fetch('/api/history?item=' + selected)).json();
  document.getElementById('chart-title').textContent = 'Stock history – ' + it.name;
  drawChart(h, it.rop);
  document.getElementById('alerts').innerHTML =
    '<tr><th>Working day</th><th>Stock at alert</th><th>ROP</th><th>Order quantity</th></tr>' +
    h.alerts.map(a => `<tr><td>${a.sim_time.toFixed(2)}</td><td>${a.qty}</td>
      <td>${it.rop}</td><td>${it.order_qty}</td></tr>`).join('');
}
function drawChart(h, rop) {
  const svg = document.getElementById('chart'), W = svg.parentElement.clientWidth - 32, H = 260, p = 44;
  svg.setAttribute('width', W);
  const m = h.measurements; if (!m.length) { svg.innerHTML = ''; return; }
  const xmax = Math.ceil(m[m.length-1].sim_time), ymax = Math.max(...m.map(d => d.qty), rop) * 1.1;
  const x = t => p + (W - 2*p) * t / xmax, y = q => H - p + 10 - (H - 2*p) * q / ymax;
  let s = '';
  for (let i = 0; i <= 4; i++) { const v = Math.round(ymax*i/4);
    s += `<line x1="${p}" x2="${W-p}" y1="${y(v)}" y2="${y(v)}" stroke="#e3e7ec"/>
          <text x="${p-6}" y="${y(v)+4}" text-anchor="end">${v}</text>`; }
  for (let d = 0; d <= xmax; d += 10)
    s += `<text x="${x(d)}" y="${H-12}" text-anchor="middle">day ${d}</text>`;
  s += `<line x1="${p}" x2="${W-p}" y1="${y(rop)}" y2="${y(rop)}" stroke="#555" stroke-dasharray="5,4"/>
        <text x="${W-p}" y="${y(rop)-5}" text-anchor="end">ROP ${rop}</text>`;
  s += `<polyline fill="none" stroke="#1f77b4" stroke-width="2" points="${
        m.map(d => x(d.sim_time) + ',' + y(d.qty)).join(' ')}"/>`;
  s += h.alerts.map(a => `<circle cx="${x(a.sim_time)}" cy="${y(a.qty)}" r="5" fill="#d66e14"/>`).join('');
  svg.innerHTML = s;
}
load(); setInterval(load, 5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/summary":
            self._send(json.dumps(summary()), "application/json")
        elif url.path == "/api/history":
            item = parse_qs(url.query).get("item", [""])[0]
            self._send(json.dumps(history(item)), "application/json")
        elif url.path == "/":
            self._send(PAGE, "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", config.DASHBOARD_PORT), Handler)
    print(f"Dashboard running at http://localhost:{config.DASHBOARD_PORT}")
    server.serve_forever()
