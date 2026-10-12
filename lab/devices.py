"""Simulated network devices for the lab: each port is one 'device'.
Modes: ok, down (not listening), slow (latency), flap (alternates 503/200 every N s), reboot (sysUpTime resets)."""
import json, sys, threading, time, random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

START = time.time()
def make(mode, name):
    state = {"boot": time.time(), "octets": random.randint(10**6, 10**7)}
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if mode == "slow": time.sleep(0.8)
            if mode == "flap" and int(time.time() - START) // 20 % 2 == 1:
                self.send_response(503); self.end_headers(); return
            if mode == "reboot" and time.time() - state["boot"] > 45:
                state["boot"] = time.time()                     # device reboots every 45 s
            if self.path == "/snmp":
                state["octets"] += random.randint(10**5, 10**6) if mode != "saturated" else 600_000_000  # ~960 Mbps at 5 s polls (v1 used 120 MB = only 192 Mbps)
                body = {"sysName": name, "sysUpTime": round(time.time() - state["boot"], 1),
                        "interfaces": [{"ifName": "Gi0/1", "ifInOctets": state["octets"], "ifSpeed": 1_000_000_000}]}
            else:
                body = {"device": name, "ok": True}
            b = json.dumps(body).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    return H

DEVICES = {9101: ("ok", "core-sw-01"), 9102: ("slow", "wan-rtr-01"), 9103: ("flap", "branch-ap-07"),
           9104: ("reboot", "edge-fw-01"), 9105: ("saturated", "dist-sw-02")}   # 9106 intentionally down
if __name__ == "__main__":
    for port, (mode, name) in DEVICES.items():
        s = ThreadingHTTPServer(("127.0.0.1", port), make(mode, name))
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print("devices up:", DEVICES, flush=True)
    while True: time.sleep(3600)
