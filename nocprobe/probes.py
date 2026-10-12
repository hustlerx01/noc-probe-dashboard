"""Probe implementations. Each returns (up: bool, latency_s: float|None, extra: dict)."""
from __future__ import annotations
import json, re, shutil, socket, subprocess, time, urllib.request

def tcp(target: str, timeout: float = 2.0):
    host, port = target.rsplit(":", 1)
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, time.perf_counter() - t0, {}
    except OSError as e:
        return False, None, {"error": type(e).__name__}

def http(target: str, timeout: float = 2.0, expect: int = 200):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(target, timeout=timeout) as r:
            return r.status == expect, time.perf_counter() - t0, {"status": r.status}
    except urllib.error.HTTPError as e:
        return e.code == expect, time.perf_counter() - t0, {"status": e.code}
    except Exception as e:
        return False, None, {"error": type(e).__name__}

def icmp(target: str, timeout: float = 2.0):
    """Uses system ping (raw sockets need root). Reports unavailable rather than faking."""
    if not shutil.which("ping"):
        return False, None, {"error": "ping_unavailable"}
    p = subprocess.run(["ping", "-c", "1", "-W", str(int(timeout)), target], capture_output=True, text=True)
    m = re.search(r"time=([\d.]+) ms", p.stdout)
    return p.returncode == 0, (float(m.group(1)) / 1000 if m else None), {}

def snmp_sim(target: str, timeout: float = 2.0):
    """SNMP-style poll of IF-MIB/SYSTEM-MIB values over HTTP JSON from the lab device simulator.
    Swap for pysnmp GET of 1.3.6.1.2.1.1.3.0 (sysUpTime) / 1.3.6.1.2.1.2.2.1.10 (ifInOctets) in real use."""
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(target.rstrip("/") + "/snmp", timeout=timeout) as r:
            d = json.load(r)
        return True, time.perf_counter() - t0, d
    except Exception as e:
        return False, None, {"error": type(e).__name__}

PROBES = {"tcp": tcp, "http": http, "icmp": icmp, "snmp": snmp_sim}
