"""NOC probe exporter: runs probes on an interval, exposes Prometheus metrics + a status page."""
from __future__ import annotations
import argparse, collections, html, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import yaml
from prometheus_client import CollectorRegistry, Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from .probes import PROBES

class Monitor:
    def __init__(self, targets: list[dict], window: int = 60):
        self.targets = targets
        self.hist = {t["name"]: collections.deque(maxlen=window) for t in targets}
        self.last: dict[str, dict] = {}
        self.reg = CollectorRegistry()
        L = ["target", "type", "site"]
        self.up = Gauge("noc_probe_up", "1 if last probe succeeded", L, registry=self.reg)
        self.lat = Gauge("noc_probe_latency_seconds", "Last probe latency", L, registry=self.reg)
        self.ratio = Gauge("noc_probe_uptime_ratio", "Success ratio over rolling window", L, registry=self.reg)
        self.total = Counter("noc_probes_total", "Probes executed", L + ["result"], registry=self.reg)
        self.dev_up = Gauge("noc_device_uptime_seconds", "sysUpTime from SNMP-style poll", ["target"], registry=self.reg)
        self.if_in = Gauge("noc_if_in_octets", "ifInOctets counter value (as reported)", ["target", "ifname"], registry=self.reg)
        self.if_speed = Gauge("noc_if_speed_bits", "ifSpeed", ["target", "ifname"], registry=self.reg)

    def run_once(self):
        for t in self.targets:
            up, lat, extra = PROBES[t["type"]](t["target"], t.get("timeout", 2.0))
            lbl = dict(target=t["name"], type=t["type"], site=t.get("site", "lab"))
            self.hist[t["name"]].append(1 if up else 0)
            h = self.hist[t["name"]]
            self.up.labels(**lbl).set(1 if up else 0)
            self.lat.labels(**lbl).set(lat if lat is not None else float("nan"))
            self.ratio.labels(**lbl).set(sum(h) / len(h))
            self.total.labels(**lbl, result="ok" if up else "fail").inc()
            if t["type"] == "snmp" and up:
                self.dev_up.labels(t["name"]).set(extra["sysUpTime"])
                for i in extra.get("interfaces", []):
                    self.if_in.labels(t["name"], i["ifName"]).set(i["ifInOctets"])
                    self.if_speed.labels(t["name"], i["ifName"]).set(i["ifSpeed"])
            self.last[t["name"]] = {"up": up, "lat": lat, "ratio": sum(h) / len(h), "extra": extra, **lbl}

    def status_html(self) -> str:
        rows = "".join(
            f"<tr class={'up' if v['up'] else 'down'}><td>{html.escape(k)}</td><td>{v['type']}</td><td>{v['site']}</td>"
            f"<td>{'UP' if v['up'] else 'DOWN'}</td><td>{'' if v['lat'] is None else f'{v['lat']*1000:.1f} ms'}</td>"
            f"<td>{v['ratio']*100:.1f}%</td><td>{html.escape(str(v['extra'].get('error','')))}</td></tr>"
            for k, v in sorted(self.last.items(), key=lambda kv: kv[1]["up"]))
        return ("<html><head><meta http-equiv=refresh content=5><style>body{font-family:monospace;background:#111;color:#ddd}"
                ".up{color:#4c4}.down{color:#f44;font-weight:bold}td,th{padding:4px 12px}</style></head><body>"
                f"<h2>NOC status</h2><table><tr><th>target</th><th>type</th><th>site</th><th>state</th><th>latency</th><th>uptime</th><th>error</th></tr>{rows}</table></body></html>")

def serve(mon: Monitor, port: int, interval: float):
    def loop():
        while True:
            mon.run_once(); time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path.startswith("/metrics"):
                body, ct = generate_latest(mon.reg), CONTENT_TYPE_LATEST
            else:
                body, ct = mon.status_html().encode(), "text/html"
            self.send_response(200); self.send_header("Content-Type", ct); self.end_headers(); self.wfile.write(body)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", default="targets.yml")
    ap.add_argument("--port", type=int, default=9469); ap.add_argument("--interval", type=float, default=5)
    a = ap.parse_args()
    serve(Monitor(yaml.safe_load(open(a.config))["targets"]), a.port, a.interval)

if __name__ == "__main__":
    main()
