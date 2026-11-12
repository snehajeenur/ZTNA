
#!/usr/bin/env bash
# Applies the zero-trust firewall in its OWN table 'inet ztna_lab'.
# Does not flush or modify any other firewall tables.
# Restricts only traffic involving the four ZTNA lab subnets.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo."
    exit 1
fi

# Replace only our own table (idempotent).
nft list table inet ztna_lab >/dev/null 2>&1 && nft delete table inet ztna_lab

nft -f - <<'EOF'
table inet ztna_lab {
    chain forward {
        type filter hook forward priority 0; policy accept;

        # Allow replies to permitted connections between lab subnets.
        ip saddr { 192.168.10.0/24, 192.168.20.0/24, 192.168.30.0/24, 192.168.40.0/24 } ip daddr { 192.168.10.0/24, 192.168.20.0/24, 192.168.30.0/24, 192.168.40.0/24 } ct state established,related accept

        # Corporate -> DMZ web service (80,443) = ALLOW
        ip saddr 192.168.10.0/24 ip daddr 192.168.30.10 tcp dport { 80, 443 } accept

        # Guest -> DMZ public web (80) = ALLOW
        ip saddr 192.168.40.0/24 ip daddr 192.168.30.10 tcp dport 80 accept

        # Drop and log all other forwarded traffic originating from lab subnets.
        ip saddr { 192.168.10.0/24, 192.168.20.0/24, 192.168.30.0/24, 192.168.40.0/24 } counter log prefix "ZTNA_LAB_DROP " drop

        # Drop and log traffic forwarded towards lab subnets from outside.
        ip daddr { 192.168.10.0/24, 192.168.20.0/24, 192.168.30.0/24, 192.168.40.0/24 } counter log prefix "ZTNA_LAB_DROP " drop
    }
}
EOF

echo "[+] Firewall applied (table inet ztna_lab)."
echo "    View dropped traffic with: sudo journalctl -k -g ZTNA_LAB_DROP"
