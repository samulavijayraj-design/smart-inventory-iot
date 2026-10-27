"""Runs the evaluation of the smart inventory prototype.

1. End-to-end run: sensor nodes -> MQTT broker -> backend for one quarter
   (counting accuracy, latency, reorder alerts, stock trend for Figure 6).
2. Policy comparison: IoT continuous review vs. weekly manual count over
   REPLICATIONS demand scenarios (stock-outs, fill rate, average inventory).

Usage:  python run_simulation.py      (results are written to ./results,
        measurements and alerts additionally to results/inventory.db)
"""
import csv
import json
import os
import statistics
import subprocess
import sys
import time

import config
from backend import InventoryBackend
from inventory_logic import (DemandGenerator, periodic_reorder_level,
                             reorder_point, safety_stock, simulate_iot,
                             simulate_manual)
from sensor_node import SensorNode

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = config.RESULTS_DIR


def start_broker():
    """Starts the TLS-secured amqtt broker (creates certificates if missing)."""
    if not os.path.exists(config.CA_CERT):
        import setup_security
        os.makedirs(config.CERT_DIR, exist_ok=True)
        setup_security.create_certificates()
        setup_security.create_password_file()
    exe = os.path.join(os.path.dirname(sys.executable), "amqtt")
    proc = subprocess.Popen([exe, "-c", "broker.yaml"], cwd=HERE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    return proc


def end_to_end_run():
    items = config.ITEMS
    demand = DemandGenerator(config.SEED)
    backend = InventoryBackend(items)
    nodes = {i["id"]: SensorNode(i, config.SEED + 100 + k) for k, i in enumerate(items)}
    stock = {i["id"]: round(reorder_point(i) + i["Q"]) for i in items}
    pipeline = {i["id"]: {} for i in items}
    truth = []                         # (item, sim_time, true_qty, measured_qty)
    sent = 0
    for day in range(config.WORKING_DAYS):
        hourly = {}
        for i in items:
            if pipeline[i["id"]].pop(day, 0):
                stock[i["id"]] += i["Q"]
                backend.delivered(i["id"])
            nodes[i["id"]].cell.new_day()
            hourly[i["id"]] = demand.day(i)
        for h in range(config.HOURS_PER_DAY):
            sim_time = day + (h + 1) / config.HOURS_PER_DAY
            for i in items:
                stock[i["id"]] -= min(stock[i["id"]], hourly[i["id"]][h])
                p = nodes[i["id"]].publish(stock[i["id"]], sim_time)
                truth.append((i["id"], sim_time, stock[i["id"]], p["qty"]))
                sent += 1
            backend.wait_for(sent)                      # lockstep with the backend
            for a in backend.alerts:
                if a["sim_time"] == sim_time:
                    lead = next(x["L"] for x in items if x["id"] == a["item"])
                    pipeline[a["item"]][day + lead] = a["order_qty"]
    for n in nodes.values():
        n.close()
    backend.close()
    return truth, backend.records, backend.alerts


def alert_delays(truth, alerts):
    """Hours between the true stock reaching the ROP and the alert."""
    rops = {i["id"]: reorder_point(i) for i in config.ITEMS}
    delays, false_alerts = [], 0
    for a in alerts:
        series = [t for t in truth if t[0] == a["item"] and t[1] <= a["sim_time"]]
        true_at_alert = series[-1][2]
        if true_at_alert > rops[a["item"]]:
            false_alerts += 1
            continue
        first = a["sim_time"]
        for t in reversed(series):
            if t[2] <= rops[a["item"]]:
                first = t[1]
            else:
                break
        delays.append((a["sim_time"] - first) * config.HOURS_PER_DAY)
    return delays, false_alerts


def main():
    os.makedirs(OUT, exist_ok=True)
    broker = start_broker()
    try:
        truth, records, alerts = end_to_end_run()
    finally:
        broker.terminate()

    summary = {"messages": len(records), "items": {}}
    lat = sorted(r["latency_ms"] for r in records)
    summary["latency_ms"] = {"median": round(statistics.median(lat), 2),
                             "p95": round(lat[int(0.95 * len(lat)) - 1], 2),
                             "max": round(lat[-1], 2)}
    for i in config.ITEMS:
        rows = [t for t in truth if t[0] == i["id"]]
        err = [m - q for _, _, q, m in rows]
        summary["items"][i["id"]] = {
            "rop": round(reorder_point(i)), "safety_stock": round(safety_stock(i)),
            "manual_level": round(periodic_reorder_level(i, config.REVIEW_PERIOD_MANUAL)),
            "exact_share_pct": round(100 * sum(e == 0 for e in err) / len(err), 1),
            "within_1_pct": round(100 * sum(abs(e) <= 1 for e in err) / len(err), 1),
            "mae_pieces": round(statistics.mean(abs(e) for e in err), 2),
            "max_abs_error": max(abs(e) for e in err),
            "alerts": sum(a["item"] == i["id"] for a in alerts),
        }
    delays, false_alerts = alert_delays(truth, alerts)
    summary["alert_delay_h"] = {"mean": round(statistics.mean(delays), 2), "max": max(delays)}
    summary["false_alerts"] = false_alerts

    # Policy comparison over several demand scenarios
    comp = {}
    for i in config.ITEMS:
        res = {"iot": [], "manual": []}
        for s in range(config.REPLICATIONS):
            res["iot"].append(simulate_iot(i, 1000 + s, 5000 + s))
            res["manual"].append(simulate_manual(i, 1000 + s))
        comp[i["id"]] = {}
        for pol, runs in res.items():
            dem = sum(r["demanded"] for r in runs)
            comp[i["id"]][pol] = {
                "fill_rate_pct": round(100 * (1 - sum(r["unmet"] for r in runs) / dem), 2),
                "runs_with_stockout_pct": round(100 * sum(r["unmet"] > 0 for r in runs) / len(runs), 1),
                "avg_inventory": round(statistics.mean(r["avg_inventory"] for r in runs)),
            }
    summary["policy_comparison"] = comp

    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(OUT, "alerts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "sim_time", "qty", "rop", "order_qty"])
        w.writeheader()
        w.writerows(alerts)
    # Figure 6: stock of the first item, one value per measurement
    first = config.ITEMS[0]
    with open(os.path.join(OUT, "stock_trend.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "true_qty", "measured_qty", "rop"])
        for item_id, t, q, m in truth:
            if item_id == first["id"]:
                w.writerow([round(t, 3), q, m, round(reorder_point(first))])
    with open(os.path.join(OUT, "alerts_first_item.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "qty"])
        for a in alerts:
            if a["item"] == first["id"]:
                w.writerow([round(a["sim_time"], 3), a["qty"]])
    print_summary(summary)


def print_summary(d):
    """Prints the main results as readable tables (full data in summary.json)."""
    lat = d["latency_ms"]
    print(f"Messages processed : {d['messages']}")
    print(f"Latency (TLS)      : median {lat['median']} ms, p95 {lat['p95']} ms, max {lat['max']} ms")
    print(f"Alert delay        : mean {d['alert_delay_h']['mean']} h, max {d['alert_delay_h']['max']} h")
    print(f"False alerts       : {d['false_alerts']}\n")
    print(f"{'Item':10s} {'ROP':>5s} {'SS':>4s} {'exact %':>8s} {'+-1 %':>6s} {'MAE':>5s} {'alerts':>6s}")
    for k, v in d["items"].items():
        print(f"{k:10s} {v['rop']:5d} {v['safety_stock']:4d} {v['exact_share_pct']:8.1f} "
              f"{v['within_1_pct']:6.1f} {v['mae_pieces']:5.2f} {v['alerts']:6d}")
    print(f"\nPolicy comparison over {config.REPLICATIONS} demand scenarios:")
    print(f"{'Item':10s} {'IoT inv.':>9s} {'Manual inv.':>11s} {'Change':>7s} {'IoT fill %':>10s} {'Man. fill %':>11s}")
    for k, v in d["policy_comparison"].items():
        i, m = v["iot"], v["manual"]
        change = 100 * (i["avg_inventory"] / m["avg_inventory"] - 1)
        print(f"{k:10s} {i['avg_inventory']:9d} {m['avg_inventory']:11d} {change:6.0f}% "
              f"{i['fill_rate_pct']:10.2f} {m['fill_rate_pct']:11.2f}")
    print("\nResults written to results/ (summary.json, inventory.db, CSV files)")


if __name__ == "__main__":
    main()
