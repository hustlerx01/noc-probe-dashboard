#!/usr/bin/env bash
# Start simulated devices + exporter + real Prometheus, wait, dump firing alerts and uptime.
set -u; cd "$(dirname "$0")/.."; PY=${PYTHON:-python3}; DUR=${DUR:-150}; D=$(mktemp -d)
$PY lab/devices.py > $D/dev.log 2>&1 & P1=$!
$PY -m nocprobe.exporter --config targets.yml --interval 5 > $D/exp.log 2>&1 & P2=$!
prometheus --config.file=prometheus/prometheus.yml --storage.tsdb.path=$D/tsdb --web.listen-address=127.0.0.1:${PROM_PORT:-19090} > $D/prom.log 2>&1 & P3=$!
trap 'kill $P1 $P2 $P3 2>/dev/null' EXIT
sleep "$DUR"
mkdir -p results
curl -s 127.0.0.1:9469/metrics | grep -E '^noc_(probe_up|probe_uptime_ratio|probe_latency)' > results/metrics_snapshot.txt
curl -s 127.0.0.1:9469/ > results/status_page.html
curl -s "127.0.0.1:${PROM_PORT:-19090}/api/v1/alerts" > results/alerts.json
curl -s "127.0.0.1:${PROM_PORT:-19090}/api/v1/query?query=noc:if_in_bps:rate1m" > results/if_bps.json
tail -n 3 $D/prom.log $D/exp.log >&2
$PY - <<'PY'
import json
a=json.load(open("results/alerts.json"))["data"]["alerts"]
for x in sorted(a,key=lambda x:(x["labels"]["alertname"],x["labels"].get("target",""))):
    print(f'{x["state"]:8} {x["labels"]["alertname"]:20} {x["labels"].get("target","")}')
for r in json.load(open("results/if_bps.json"))["data"]["result"]:
    print("if_bps", r["metric"]["target"], round(float(r["value"][1])/1e6,1), "Mbps")
PY
