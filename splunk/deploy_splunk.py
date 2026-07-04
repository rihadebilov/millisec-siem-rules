#!/usr/bin/env python3
"""
MilliSec Blue Team — Splunk Rule Deployer
GitHub → Splunk REST API Pipeline

Usage:
    export SPLUNK_HOST="34.88.60.227"
    export SPLUNK_PORT="8089"
    export SPLUNK_TOKEN="your-token"
    export ALERT_EMAIL="your-email@gmail.com"
    python splunk/deploy_splunk.py

Author: Rihad Ebilov — MilliSec Blue Team
"""

import os
import sys
import yaml
import requests
import urllib3
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ────────────────────────────────────────────────────────────
SPLUNK_HOST  = os.environ.get("SPLUNK_HOST", "34.88.60.227")
SPLUNK_PORT  = os.environ.get("SPLUNK_PORT", "8089")
SPLUNK_TOKEN = os.environ.get("SPLUNK_TOKEN", "")
SPLUNK_USER  = os.environ.get("SPLUNK_USER", "admin")
SPLUNK_PASS  = os.environ.get("SPLUNK_PASS", "")
ALERT_EMAIL  = os.environ.get("ALERT_EMAIL", "")
APP          = "search"
OWNER        = "nobody"

BASE_URL = f"https://{SPLUNK_HOST}:{SPLUNK_PORT}/servicesNS/{OWNER}/{APP}"

# ── Authentication ────────────────────────────────────────────────────────────
def get_headers():
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if SPLUNK_TOKEN:
        headers["Authorization"] = f"Bearer {SPLUNK_TOKEN}"
    return headers

def get_auth():
    if SPLUNK_TOKEN:
        return None
    if SPLUNK_USER and SPLUNK_PASS:
        return (SPLUNK_USER, SPLUNK_PASS)
    print("❌ ERROR: No auth provided. Set SPLUNK_TOKEN or SPLUNK_USER+SPLUNK_PASS")
    sys.exit(1)

# ── Splunk API Helpers ────────────────────────────────────────────────────────
def rule_exists(rule_name: str) -> bool:
    encoded = requests.utils.quote(rule_name, safe="")
    url = f"{BASE_URL}/saved/searches/{encoded}"
    resp = requests.get(
        url,
        headers=get_headers(),
        auth=get_auth(),
        verify=False,
        params={"output_mode": "json"}
    )
    return resp.status_code == 200


def build_payload(rule: dict, is_update: bool = False) -> dict:
    splunk = rule.get("splunk", {})

    # Fix multi-index search syntax for Splunk
    # e.g. index: "xdr OR waf" → handled in SPL directly
    search_query = splunk.get("search", "").strip()

    payload = {
        "search":                    search_query,
        "description":               rule.get("description", "").strip(),
        "cron_schedule":             splunk.get("cron_schedule", "*/5 * * * *"),
        "is_scheduled":              "1",
        "dispatch.earliest_time":    splunk.get("earliest_time", "-5m@m"),
        "dispatch.latest_time":      splunk.get("latest_time", "now"),
        "alert_type":                "number of events",
        "alert_comparator":          splunk.get("alert_comparator", "greater than"),
        "alert_threshold":           str(splunk.get("alert_threshold", 0)),
        "alert.expires":             "24h",
        "alert.suppress":            "0",
        "disabled":                  "0",

        # ── Alert actions: Telegram (script) ───────────────────
        "actions":                   "script",
        "action.script":             "1",
        "action.script.filename":    "telegram_alert.sh",
    }

    # Əgər ALERT_EMAIL təyin olunubsa, Email aksiyasını da payload-a əlavə et
    if ALERT_EMAIL:
        payload["actions"] = "script,email"
        payload["action.email"] = "1"
        payload["action.email.to"] = ALERT_EMAIL
        payload["action.email.subject"] = f"[MilliSec Alert] {rule.get('name','')}"
        payload["action.email.message.alert"] = rule.get("description", "").strip()
        payload["action.email.sendresults"] = "0"

    if not is_update:
        payload["name"] = rule["name"]

    return payload


def create_rule(rule: dict) -> requests.Response:
    url = f"{BASE_URL}/saved/searches"
    return requests.post(
        url,
        headers=get_headers(),
        auth=get_auth(),
        data=build_payload(rule),
        verify=False
    )


def update_rule(rule: dict) -> requests.Response:
    encoded = requests.utils.quote(rule["name"], safe="")
    url = f"{BASE_URL}/saved/searches/{encoded}"
    return requests.post(
        url,
        headers=get_headers(),
        auth=get_auth(),
        data=build_payload(rule, is_update=True),
        verify=False
    )


# ── Rule Deployment ───────────────────────────────────────────────────────────
def deploy_rule(rule_path: Path) -> bool:
    with open(rule_path, "r", encoding="utf-8") as f:
        rule = yaml.safe_load(f)

    rule_name = rule.get("name", "")
    rule_id   = rule.get("id", "")
    severity  = rule.get("severity", "").upper()

    print(f"\n  [{rule_id}] {rule_name}")
    print(f"  Severity: {severity} | MITRE: {rule.get('mitre_attack', {}).get('technique', 'N/A')}")

    if not rule_name:
        print("  ❌ SKIPPED: Missing 'name' field in YAML")
        return False

    if rule_exists(rule_name):
        resp   = update_rule(rule)
        action = "UPDATED"
    else:
        resp   = create_rule(rule)
        action = "CREATED"

    if resp.status_code in (200, 201):
        print(f"  ✅ {action} successfully")
        return True
    else:
        print(f"  ❌ FAILED [{resp.status_code}]")
        try:
            err = resp.json()
            msgs = err.get("messages", [])
            for m in msgs:
                print(f"     {m.get('type', '')}: {m.get('text', '')}")
        except Exception:
            print(f"     Raw: {resp.text[:400]}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not ALERT_EMAIL:
        print("⚠️  WARNING: ALERT_EMAIL is not set — email alert action will be disabled.")

    rules_dir  = Path(__file__).parent / "rules"
    rule_files = sorted([f for f in rules_dir.glob("*.yaml") if f.name != ".gitkeep"])

    print("=" * 60)
    print("  MilliSec Blue Team — Splunk Rule Deployer")
    print("=" * 60)
    print(f"  Target  : {SPLUNK_HOST}:{SPLUNK_PORT}")
    print(f"  Auth    : {'Token' if SPLUNK_TOKEN else 'User/Pass'}")
    print(f"  Alerts  : Telegram (script) {'+ Email → ' + ALERT_EMAIL if ALERT_EMAIL else ''}")
    print(f"  Rules   : {len(rule_files)} files found")
    print("=" * 60)

    if not rule_files:
        print("\n❌ No .yaml rule files found in splunk/rules/")
        sys.exit(1)

    success = 0
    failed  = 0

    for rule_file in rule_files:
        try:
            if deploy_rule(rule_file):
                success += 1
            else:
                failed += 1
        except yaml.YAMLError as e:
            print(f"\n  ❌ YAML parse error in {rule_file.name}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  ❌ Unexpected error in {rule_file.name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Deployment complete")
    print(f"  ✅ Success : {success}")
    print(f"  ❌ Failed  : {failed}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
