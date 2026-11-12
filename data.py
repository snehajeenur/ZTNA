
# data.py
# Single source of truth: identities, devices, segments, resources, policy,
# plus the VLAN / network-lab configuration used by the Kali networking scripts.

# ----------------------------------------------------------------------------
# APPLICATION LAYER (identity / role / device posture)
# ----------------------------------------------------------------------------

USERS = {
    "alice": {"password": "alice123", "role": "admin",      "department": "IT"},
    "bob":   {"password": "bob123",   "role": "employee",   "department": "Finance"},
    "carol": {"password": "carol123", "role": "contractor", "department": "Marketing"},
    "dave":  {"password": "dave123",  "role": "guest",      "department": "External"},
}

# 4 segments = the 4 VLANs below.
SEGMENTS = {
    "corporate": {"description": "Internal corporate apps", "trust_level": 4},
    "database":  {"description": "Sensitive databases",     "trust_level": 5},
    "dmz":       {"description": "Public-facing services",  "trust_level": 2},
    "guest":     {"description": "Untrusted guest network", "trust_level": 1},
}

# App-layer segmentation policy. MUST mirror the nftables firewall policy.
SEGMENT_ACCESS = {
    "corporate": ["corporate", "dmz"],
    "database":  ["database"],
    "dmz":       ["dmz"],
    "guest":     ["guest", "dmz"],
}

# User endpoints (with NAC posture). 'ns' links an endpoint to a Kali namespace.
DEVICES = {
    "laptop-alice": {"owner": "alice", "segment": "corporate", "ns": "corp",
                     "antivirus": True, "os_patched": True,  "encrypted": True},
    "laptop-bob":   {"owner": "bob",   "segment": "corporate", "ns": "corp",
                     "antivirus": True, "os_patched": True,  "encrypted": True},
    "laptop-carol": {"owner": "carol", "segment": "corporate", "ns": "corp",
                     "antivirus": True, "os_patched": False, "encrypted": True},  # fails NAC
    "phone-dave":   {"owner": "dave",  "segment": "guest",     "ns": "guest",
                     "antivirus": True, "os_patched": True,  "encrypted": True},
}

# Protected resources (services). 'ip'/'port' map to a real listener in the lab.
RESOURCES = {
    "internal-crm": {"segment": "corporate", "allowed_roles": ["admin", "employee", "contractor"],
                     "ip": "192.168.10.10", "port": 8000},
    "payroll-db":   {"segment": "database",  "allowed_roles": ["admin"],
                     "ip": "192.168.20.10", "port": 5432},
    "web-portal":   {"segment": "dmz",       "allowed_roles": ["admin", "employee", "contractor", "guest"],
                     "ip": "192.168.30.10", "port": 80},
}

# ----------------------------------------------------------------------------
# NETWORK LAYER (the real Kali lab: VLANs, namespaces, IPs)
# ----------------------------------------------------------------------------

VLANS = {
    "corporate": {"vlan_id": 10, "subnet": "192.168.10.0/24", "gateway": "192.168.10.1"},
    "database":  {"vlan_id": 20, "subnet": "192.168.20.0/24", "gateway": "192.168.20.1"},
    "dmz":       {"vlan_id": 30, "subnet": "192.168.30.0/24", "gateway": "192.168.30.1"},
    "guest":     {"vlan_id": 40, "subnet": "192.168.40.0/24", "gateway": "192.168.40.1"},
}

# Virtual devices implemented as Linux network namespaces inside Kali.
LAB_DEVICES = {
    "corp":  {"name": "Alice-PC",        "segment": "corporate", "ip": "192.168.10.10"},
    "db":    {"name": "Database-Server", "segment": "database",  "ip": "192.168.20.10", "listen_port": 5432},
    "dmz":   {"name": "Web-Server",      "segment": "dmz",       "ip": "192.168.30.10", "listen_port": 80},
    "guest": {"name": "Guest-PC",        "segment": "guest",     "ip": "192.168.40.10"},
}

# Whitelisted demo scenarios. Flask can ONLY choose one of these keys.
# No IP/port/command is ever taken from the browser.
LAB_SCENARIOS = {
    "corp_to_dmz": {
        "label": "Corporate -> DMZ  (Web-Server:80)",
        "src_ns": "corp", "dst_ip": "192.168.30.10", "dst_port": 80,
        "expected_net": "CONNECTED",
        "ztna": {"user": "alice", "device": "laptop-alice", "resource": "web-portal"},
    },
    "corp_to_dmz_unhealthy": {
        "label": "Corporate (unpatched device) -> DMZ  (Web-Server:80)",
        "src_ns": "corp", "dst_ip": "192.168.30.10", "dst_port": 80,
        "expected_net": "CONNECTED",
        "ztna": {"user": "carol", "device": "laptop-carol", "resource": "web-portal"},
    },
    "guest_to_dmz": {
        "label": "Guest -> DMZ  (Web-Server:80)",
        "src_ns": "guest", "dst_ip": "192.168.30.10", "dst_port": 80,
        "expected_net": "CONNECTED",
        "ztna": {"user": "dave", "device": "phone-dave", "resource": "web-portal"},
    },
    "corp_to_db": {
        "label": "Corporate -> Database  (Database-Server:5432)",
        "src_ns": "corp", "dst_ip": "192.168.20.10", "dst_port": 5432,
        "expected_net": "BLOCKED",
        "ztna": {"user": "bob", "device": "laptop-bob", "resource": "payroll-db"},
    },
    "guest_to_db": {
        "label": "Guest -> Database  (Database-Server:5432)",
        "src_ns": "guest", "dst_ip": "192.168.20.10", "dst_port": 5432,
        "expected_net": "BLOCKED",
        "ztna": {"user": "dave", "device": "phone-dave", "resource": "payroll-db"},
    },
}
