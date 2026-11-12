
echo "[*] Stopping demo services in lab namespaces ..."
for NS in dmz db; do
  for PID in $(ip netns pids "$NS" 2>/dev/null); do
    kill "$PID" 2>/dev/null || true
  done
done

#!/usr/bin/env bash
# Reverses EVERYTHING this lab created. Leaves the rest of the system untouched.
set -uo pipefail
BR="ztna-br0"
if [[ $EUID -ne 0 ]]; then echo "Run with sudo."; exit 1; fi

echo "[*] Stopping demo services ..."
pkill -f "http.server 80"   2>/dev/null || true
pkill -f "http.server 5432" 2>/dev/null || true

echo "[*] Removing our firewall table only ..."
nft list table inet ztna_lab >/dev/null 2>&1 && nft delete table inet ztna_lab

echo "[*] Removing VLAN gateways ..."
for VID in 10 20 30 40; do ip link del "${BR}.$VID" 2>/dev/null || true; done

echo "[*] Removing namespaces ..."
for NS in corp db dmz guest; do ip netns del "$NS" 2>/dev/null || true; done

echo "[*] Removing leftover veths and bridge ..."
for V in veth-corp veth-db veth-dmz veth-guest; do ip link del "$V" 2>/dev/null || true; done
ip link del "$BR" 2>/dev/null || true

echo "[*] Restoring IP forwarding ..."
if [[ -f /tmp/ztna_ipfwd.bak ]]; then
  sysctl -w net.ipv4.ip_forward="$(cat /tmp/ztna_ipfwd.bak)" >/dev/null || true
  rm -f /tmp/ztna_ipfwd.bak
else
  sysctl -w net.ipv4.ip_forward=0 >/dev/null || true
fi

echo "[+] Cleanup complete. System restored."
