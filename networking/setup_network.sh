
#!/usr/bin/env bash
# Creates 4 namespaces, veth cables, one VLAN-filtering bridge
# and four VLAN gateways.
# The lab is isolated and is NOT attached to eth0.
# Automatically rolls back if setup fails.

set -Eeuo pipefail

BR="ztna-br0"
BACKUP="/tmp/ztna_ipfwd.bak"
SETUP_STARTED=0
BACKUP_CREATED=0

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo."
    exit 1
fi

# Check required networking tools.
for CMD in ip bridge nft sysctl python3; do
    if ! command -v "$CMD" >/dev/null 2>&1; then
        echo "[ERROR] Required command missing: $CMD"
        exit 1
    fi
done

# Prevent accidental overlap with another lab instance.
if ip link show "$BR" >/dev/null 2>&1; then
    echo "[ERROR] Bridge $BR already exists. Aborting."
    exit 1
fi

for NS in corp db dmz guest; do
    if ip netns list | awk '{print $1}' | grep -Fxq "$NS"; then
        echo "[ERROR] Namespace $NS already exists. Aborting."
        exit 1
    fi
done

for V in veth-corp veth-db veth-dmz veth-guest; do
    if ip link show "$V" >/dev/null 2>&1; then
        echo "[ERROR] Interface $V already exists. Aborting."
        exit 1
    fi
done

if [[ -e "$BACKUP" ]]; then
    echo "[ERROR] Previous IP-forwarding backup exists: $BACKUP"
    echo "Inspect it before proceeding. Do not overwrite it."
    exit 1
fi

# Roll back only resources belonging to this lab.
rollback() {
    echo
    echo "[!] Setup failed. Rolling back ZTNA lab resources ..."

    for NS in dmz db corp guest; do
        for PID in $(ip netns pids "$NS" 2>/dev/null || true); do
            kill "$PID" 2>/dev/null || true
        done
    done

    sleep 1

    for NS in corp db dmz guest; do
        ip netns del "$NS" 2>/dev/null || true
    done

    for VID in 10 20 30 40; do
        ip link del "${BR}.${VID}" 2>/dev/null || true
    done

    for V in veth-corp veth-db veth-dmz veth-guest; do
        ip link del "$V" 2>/dev/null || true
    done

    ip link del "$BR" 2>/dev/null || true

    if [[ $BACKUP_CREATED -eq 1 && -f "$BACKUP" ]]; then
        sysctl -w net.ipv4.ip_forward="$(cat "$BACKUP")" >/dev/null || true
        rm -f "$BACKUP"
    fi

    echo "[!] Rollback finished."
}

on_error() {
    local STATUS=$?
    trap - ERR INT TERM
    if [[ $SETUP_STARTED -eq 1 ]]; then
        rollback
    fi
    exit "$STATUS"
}

trap on_error ERR INT TERM

# Save the original IP forwarding value.
cat /proc/sys/net/ipv4/ip_forward > "$BACKUP"
BACKUP_CREATED=1
SETUP_STARTED=1

echo "[*] Creating VLAN-aware bridge $BR ..."
ip link add name "$BR" type bridge vlan_filtering 1 vlan_default_pvid 0
ip link set "$BR" up

# create_host <ns> <host-veth> <ns-veth> <ip/cidr> <gw> <vlan-id>
create_host() {
    local NS=$1
    local VH=$2
    local VN=$3
    local IP=$4
    local GW=$5
    local VID=$6

    echo "[*] Creating device '$NS' on VLAN $VID ($IP) ..."

    ip netns add "$NS"
    ip link add "$VH" type veth peer name "$VN"
    ip link set "$VN" netns "$NS"
    ip link set "$VH" master "$BR"
    ip link set "$VH" up

    bridge vlan del dev "$VH" vid 1 2>/dev/null || true
    bridge vlan add dev "$VH" vid "$VID" pvid untagged

    ip netns exec "$NS" ip link set lo up
    ip netns exec "$NS" ip link set "$VN" up
    ip netns exec "$NS" ip addr add "$IP" dev "$VN"
    ip netns exec "$NS" ip route add default via "$GW"
}

create_host corp  veth-corp  corp0  192.168.10.10/24 192.168.10.1 10
create_host db    veth-db    db0    192.168.20.10/24 192.168.20.1 20
create_host dmz   veth-dmz   dmz0   192.168.30.10/24 192.168.30.1 30
create_host guest veth-guest guest0 192.168.40.10/24 192.168.40.1 40

echo "[*] Creating VLAN gateways (router-on-a-stick) ..."

for VID in 10 20 30 40; do
    bridge vlan add dev "$BR" vid "$VID" self
done

add_gw() {
    ip link add link "$BR" name "${BR}.$1" type vlan id "$1"
    ip addr add "$2" dev "${BR}.$1"
    ip link set "${BR}.$1" up
}

add_gw 10 192.168.10.1/24
add_gw 20 192.168.20.1/24
add_gw 30 192.168.30.1/24
add_gw 40 192.168.40.1/24

echo "[*] Enabling IP forwarding ..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo "[*] Starting demo services ..."

ip netns exec dmz python3 -m http.server 80 \
    >/tmp/ztna_dmz.log 2>&1 &

ip netns exec db python3 -m http.server 5432 \
    >/tmp/ztna_db.log 2>&1 &

sleep 1

# Verify that both services accept TCP connections.
ip netns exec corp python3 -c '
import socket
for ip, port in [("192.168.30.10", 80), ("192.168.20.10", 5432)]:
    s = socket.create_connection((ip, port), timeout=3)
    s.close()
    print("Service reachable:", ip, port)
'

echo
echo "[+] ZTNA network setup completed successfully."
echo "[+] Bridge: $BR"
echo "[+] Namespaces: corp, db, dmz, guest"
echo "[+] Original IP forwarding value saved in $BACKUP"
echo "[+] Kali eth0 was not attached to the lab bridge."

trap - ERR INT TERM
