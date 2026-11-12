
#!/usr/bin/env python3
# Read-only verification tool. Prints the live state of the lab.
import os
import sys
import subprocess


def show(title, cmd):
    print("\n==== %s ====" % title)
    print("$ " + " ".join(cmd))
    try:
        print(subprocess.run(cmd, capture_output=True, text=True).stdout.rstrip())
    except Exception as e:
        print("(error: %s)" % e)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run with sudo (bridge vlan / nft need root).")
        sys.exit(1)
    show("Namespaces", ["ip", "netns", "list"])
    for ns in ("corp", "db", "dmz", "guest"):
        show("IP in namespace '%s'" % ns,
             ["ip", "netns", "exec", ns, "ip", "-brief", "addr", "show"])
    show("Bridge VLAN membership", ["bridge", "vlan", "show"])
    show("Firewall (our table only)", ["nft", "list", "table", "inet", "ztna_lab"])
