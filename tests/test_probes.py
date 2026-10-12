import json, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from prometheus_client import generate_latest
from nocprobe import probes
from nocprobe.exporter import Monitor

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/bad": self.send_response(503); self.end_headers(); return
        body = {"sysUpTime": 42.0, "interfaces": [{"ifName": "Gi0/1", "ifInOctets": 1000, "ifSpeed": 10**9}]} if self.path == "/snmp" else {}
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())

@pytest.fixture(scope="module")
def srv():
    s = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]; s.shutdown()

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def test_tcp_up_and_down(srv):
    assert probes.tcp(f"127.0.0.1:{srv}")[0] is True
    up, lat, extra = probes.tcp(f"127.0.0.1:{free_port()}", timeout=0.5)
    assert not up and lat is None and extra["error"] == "ConnectionRefusedError"

def test_http_status(srv):
    assert probes.http(f"http://127.0.0.1:{srv}/")[0]
    up, _, extra = probes.http(f"http://127.0.0.1:{srv}/bad")
    assert not up and extra["status"] == 503

def test_snmp_sim(srv):
    up, _, d = probes.snmp_sim(f"http://127.0.0.1:{srv}")
    assert up and d["sysUpTime"] == 42.0

def test_monitor_uptime_ratio_and_metrics(srv):
    dead = free_port()
    m = Monitor([{"name": "a", "type": "tcp", "target": f"127.0.0.1:{srv}"},
                 {"name": "b", "type": "tcp", "target": f"127.0.0.1:{dead}", "timeout": 0.3},
                 {"name": "s", "type": "snmp", "target": f"http://127.0.0.1:{srv}"}], window=4)
    for _ in range(4): m.run_once()
    out = generate_latest(m.reg).decode()
    assert 'noc_probe_uptime_ratio{site="lab",target="a",type="tcp"} 1.0' in out
    assert 'noc_probe_uptime_ratio{site="lab",target="b",type="tcp"} 0.0' in out
    assert 'noc_if_in_octets{ifname="Gi0/1",target="s"} 1000.0' in out
    assert "DOWN" in m.status_html()

def test_status_page_escapes_names(srv):
    m = Monitor([{"name": "<script>x</script>", "type": "tcp", "target": f"127.0.0.1:{srv}"}]); m.run_once()
    assert "<script>" not in m.status_html()
