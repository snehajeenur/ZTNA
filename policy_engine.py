
# policy_engine.py
# The zero-trust decision point. Every request is checked here, every time.

from data import DEVICES, RESOURCES, SEGMENT_ACCESS


def check_nac(device):
    """NAC posture: a device is admitted only if fully compliant."""
    reasons = []
    if not device["antivirus"]:
        reasons.append("antivirus missing")
    if not device["os_patched"]:
        reasons.append("OS not patched")
    if not device["encrypted"]:
        reasons.append("disk not encrypted")
    return (len(reasons) == 0), reasons


def evaluate_access(username, user, device_id, resource_id):
    """Run ALL zero-trust checks. Granted only if every check passes."""
    device = DEVICES.get(device_id)
    resource = RESOURCES.get(resource_id)
    checks = []

    # 1. Identity
    checks.append({
        "name": "Identity verification", "passed": True,
        "detail": "Authenticated as '%s' (role: %s)" % (username, user["role"]),
    })

    # 2. Device ownership
    owns = bool(device) and device["owner"] == username
    checks.append({
        "name": "Device ownership", "passed": owns,
        "detail": ("'%s' is registered to %s" % (device_id, username)) if owns
                  else ("'%s' is NOT registered to %s" % (device_id, username)),
    })

    # 3. NAC posture
    if device:
        compliant, reasons = check_nac(device)
    else:
        compliant, reasons = False, ["unknown device"]
    checks.append({
        "name": "Device posture (NAC)", "passed": compliant,
        "detail": "Compliant (antivirus, patched, encrypted)" if compliant
                  else "Non-compliant: " + ", ".join(reasons),
    })

    # 4. Network segmentation
    dev_seg = device["segment"] if device else None
    res_seg = resource["segment"] if resource else None
    seg_ok = dev_seg is not None and res_seg in SEGMENT_ACCESS.get(dev_seg, [])
    checks.append({
        "name": "Network segmentation", "passed": seg_ok,
        "detail": ("Segment '%s' may reach '%s'" % (dev_seg, res_seg)) if seg_ok
                  else ("Segment '%s' is NOT allowed to reach '%s'" % (dev_seg, res_seg)),
    })

    # 5. Least privilege / role authorization
    role_ok = bool(resource) and user["role"] in resource["allowed_roles"]
    checks.append({
        "name": "Role authorization (least privilege)", "passed": role_ok,
        "detail": ("Role '%s' is permitted for '%s'" % (user["role"], resource_id)) if role_ok
                  else ("Role '%s' is NOT permitted for '%s'" % (user["role"], resource_id)),
    })

    decision = all(c["passed"] for c in checks)
    return decision, checks
