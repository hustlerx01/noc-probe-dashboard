# Interview talking points: noc-probe-dashboard
1. **`for:` clauses prevent pager fatigue.** branch-ap-07 was down half the time, but TargetDown stayed *pending*. The Flapping alert is the right signal for it, not 20 down/up pages.
2. **Alert rules are code, so test them.** `promtool test rules` with synthetic series proves each alert fires at the right time. CI runs it.
3. **Reboot detection.** `resets(sysUpTime[2m]) > 0` catches a device that rebooted between polls even if it never looked "down". Field engineers love this one.
4. **Utilisation math.** octets × 8 / ifSpeed, from a recording rule. My own simulator bug (192 Mbps instead of 900) shows why you check units.
5. **Honesty about ICMP.** No root means no raw sockets. The probe reports `ping_unavailable` instead of pretending, and the rule excludes it.
6. **Label cardinality.** Labels are target/site/type. Never use per-request values.
7. **Production path.** Use blackbox_exporter plus snmp_exporter (generator from MIBs), Alertmanager routing by site, and inhibition when an upstream router is down.
