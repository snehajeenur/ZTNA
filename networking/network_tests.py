
#!/usr/bin/env python3
# Runs a REAL TCP connection test from a source namespace to a destination.
# Only scenario KEYS from data.py are accepted; no raw IP/port/command input.
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import LAB_SCENARIOS

# Small probe run INSIDE the source namespace: attempts a TCP connect.
PROBE = (
    "import socket,sys\n"
    "ip=sys.argv[1]; port=int(sys.argv[2])\n"
    "try:\n"
    "    s=socket.create_connection((ip,port),timeout=3); s.close()\n"
    "    print('CONNECTED'); sys.exit(0)\n"
    "except Exception:\n"
    "    print('BLOCKED'); sys.exit(1)\n"
)


def run_tcp_test(key):
    sc = LAB_SCENARIOS.get(key)
    if not sc:
        return {"error": "unknown scenario"}
    cmd = ["ip", "netns", "exec", sc["src_ns"],
           sys.executable, "-c", PROBE, sc["dst_ip"], str(sc["dst_port"])]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        result = (proc.stdout.strip() or "BLOCKED")
    except subprocess.TimeoutExpired:
        result = "BLOCKED"
    return {"scenario": key, "src_ns": sc["src_ns"], "dst_ip": sc["dst_ip"],
            "dst_port": sc["dst_port"], "result": result}


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(json.dumps({"error": "must run as root (ip netns exec)"}))
        sys.exit(2)
    if len(sys.argv) != 2 or sys.argv[1] not in LAB_SCENARIOS:
        print(json.dumps({"error": "usage: network_tests.py <valid-scenario-key>"}))
        sys.exit(2)
    print(json.dumps(run_tcp_test(sys.argv[1])))
