#!/usr/bin/env python3
"""
MilliSec Blue Team — QRadar Analytics Rule Deployer
GitHub → QRadar REST API Pipeline

Deploys rules as Analytics Rules (Offense triggers) via:
  POST /api/analytics/rules         (create)
  POST /api/analytics/rules/{id}    (update)

Author: Rihad Ebilov — MilliSec Blue Team
"""

import os
import sys
import json
import requests
import urllib3
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ─────────────────────────────────────────────────────────────
QRADAR_HOST  = os.environ.get("QRADAR_HOST", "")
QRADAR_PORT  = os.environ.get("QRADAR_PORT", "443")
QRADAR_TOKEN = os.environ.get("QRADAR_TOKEN", "")

if not QRADAR_HOST or not QRADAR_TOKEN:
    print("❌ ERROR: QRADAR_HOST and QRADAR_TOKEN environment variables are required.")
    sys.exit(1)

BASE_URL = f"https://{QRADAR_HOST}:{QRADAR_PORT}/api"

# ── Authentication ─────────────────────────────────────────────────────────────
def get_headers():
    return {
        "SEC": QRADAR_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "12.0"
    }

# ── QRadar API Helpers ─────────────────────────────────────────────────────────
def get_existing_rule(rule_name: str):
    url = f"{BASE_URL}/analytics/rules"
    resp = requests.get(
        url,
        headers=get_headers(),
        params={"filter": f'name="{rule_name}"'},
        verify=False
    )
    if resp.status_code == 200:
        results = resp.json()
        if isinstance(results, list) and len(results) > 0:
            return results[0]
    return None

def create_rule(payload: dict) -> requests.Response:
    url = f"{BASE_URL}/analytics/rules"
    return requests.post(url, headers=get_headers(), json=payload, verify=False)

def update_rule(rule_id: int, payload: dict) -> requests.Response:
    url = f"{BASE_URL}/analytics/rules/{rule_id}"
    return requests.post(url, headers=get_headers(), json=payload, verify=False)

# ── Rule Deployment ────────────────────────────────────────────────────────────
def deploy_rule(rule_path: Path) -> bool:
    with open(rule_path, "r", encoding="utf-8") as f:
        rule_data = json.load(f)

    # Payloadın QRadar obyektindən çıxarılması
    payload = rule_data.get("qradar", rule_data)
    rule_name = payload.get("name", rule_data.get("name", ""))

    print(f"\n  [Deploying] {rule_name}")

    if not rule_name:
        print("  ❌ SKIPPED: Missing 'name' field in JSON payload")
        return False

    existing = get_existing_rule(rule_name)

    if existing:
        rule_id = existing.get("id")
        payload.pop('id', None) # Update zamanı ID göndərilməməlidir
        resp   = update_rule(rule_id, payload)
        action = "UPDATED"
    else:
        resp   = create_rule(payload)
        action = "CREATED"

    if resp.status_code in (200, 201):
        result_id = resp.json().get("id", "?")
        print(f"  ✅ {action} — QRadar Rule ID: {result_id}")
        return True
    else:
        print(f"  ❌ FAILED [{resp.status_code}]")
        try:
            err  = resp.json()
            msgs = err.get("message", err.get("description", str(err)))
            print(f"     Error: {msgs}")
        except Exception:
            print(f"     Raw: {resp.text[:400]}")
        return False

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    rules_dir  = Path(__file__).parent / "rules"
    rule_files = sorted([f for f in rules_dir.glob("*.json") if f.name != ".gitkeep"])

    print("=" * 60)
    print("  MilliSec Blue Team — QRadar Analytics Rule Deployer")
    print("=" * 60)
    print(f"  Target  : {QRADAR_HOST}:{QRADAR_PORT}")
    print(f"  Auth    : SEC Token")
    print(f"  Rules   : {len(rule_files)} files found")
    print(f"  Mode    : Analytics Rules (/api/analytics/rules)")
    print("=" * 60)

    if not rule_files:
        print("\n❌ No .json rule files found in qradar/rules/")
        sys.exit(1)

    success = 0
    failed  = 0

    for rule_file in rule_files:
        try:
            if deploy_rule(rule_file):
                success += 1
            else:
                failed += 1
        except json.JSONDecodeError as e:
            print(f"\n  ❌ JSON parse error in {rule_file.name}: {e}")
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
