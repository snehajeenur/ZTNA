
# app.py
import os
import sys
import json
import subprocess
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash

from data import (USERS, DEVICES, RESOURCES, SEGMENTS, SEGMENT_ACCESS,
                  VLANS, LAB_DEVICES, LAB_SCENARIOS)
from policy_engine import evaluate_access

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NET_DIR = os.path.join(BASE_DIR, "networking")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            flash("Welcome, %s!" % username, "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials. Zero-trust: access denied.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    username = session["user"]
    user = USERS[username]
    my_devices = {d: i for d, i in DEVICES.items() if i["owner"] == username}
    return render_template("dashboard.html", username=username, user=user, devices=my_devices)


@app.route("/access", methods=["GET", "POST"])
@login_required
def access():
    username = session["user"]
    user = USERS[username]
    my_devices = {d: i for d, i in DEVICES.items() if i["owner"] == username}
    decision, checks, selected = None, None, {}
    if request.method == "POST":
        device_id = request.form.get("device")
        resource_id = request.form.get("resource")
        selected = {"device": device_id, "resource": resource_id}
        decision, checks = evaluate_access(username, user, device_id, resource_id)
    return render_template("access.html", devices=my_devices, resources=RESOURCES,
                           decision=decision, checks=checks, selected=selected)


@app.route("/network")
@login_required
def network():
    seg_devices = {s: [] for s in SEGMENTS}
    for name, i in DEVICES.items():
        seg_devices[i["segment"]].append((name, i))
    seg_resources = {s: [] for s in SEGMENTS}
    for name, i in RESOURCES.items():
        seg_resources[i["segment"]].append((name, i))
    return render_template("network.html", segments=SEGMENTS, access=SEGMENT_ACCESS,
                           seg_devices=seg_devices, seg_resources=seg_resources)


# ---------- Network Lab (real Kali tests) ----------

def _run_network_test(scenario_key):
    """Call the real TCP test script. Root is required for 'ip netns exec'."""
    script = os.path.join(NET_DIR, "network_tests.py")
    cmd = [sys.executable, script, scenario_key]
    if os.geteuid() != 0:                 # not root -> try passwordless sudo
        cmd = ["sudo", "-n"] + cmd
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if proc.returncode not in (0, 1) and not proc.stdout.strip():
            return {"error": (proc.stderr.strip() or "test failed")[:300]}
        return json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        return {"error": str(e)}


@app.route("/network-lab", methods=["GET", "POST"])
@login_required
def network_lab():
    result = None
    if request.method == "POST":
        key = request.form.get("scenario", "")
        if key not in LAB_SCENARIOS:          # strict whitelist — never trust input
            flash("Unknown scenario.", "error")
            return redirect(url_for("network_lab"))
        sc = LAB_SCENARIOS[key]

        # 1) Application-layer ZTNA decision
        z = sc["ztna"]
        ztna_decision, ztna_checks = evaluate_access(
            z["user"], USERS[z["user"]], z["device"], z["resource"])

        # 2) Real network-layer connectivity result
        net = _run_network_test(key)

        result = {"key": key, "label": sc["label"],
                  "expected_net": sc["expected_net"],
                  "ztna_decision": ztna_decision, "ztna_checks": ztna_checks,
                  "net": net}
    return render_template("network_lab.html", vlans=VLANS, devices=LAB_DEVICES,
                           scenarios=LAB_SCENARIOS, result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
