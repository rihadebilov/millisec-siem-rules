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

QRADAR_HOST  = os.environ.get("QRADAR_HOST", "")
QRADAR_PORT  = os.environ.get("QRADAR_PORT", "443")
QRADAR_TOKEN = os.environ.get("QRADAR_TOKEN", "")

if not QRADAR_HOST or not QRADAR_TOKEN:
    print("❌ ERROR: QRADAR_HOST and QRADAR_TOKEN environment variables are required.")
    sys.exit(1)

BASE_URL = f"https://{QRADAR_HOST}:{QRADAR_PORT}/api"

def get_headers():
    return {
        "SEC": QRADAR_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "12.0"
    }

def get_existing_rule(rule_name: str):
    url = f"{BASE_URL}/analytics/rules"
    resp = requests.get(url, headers=get_headers(), params={"filter": f'name="{rule_name}"'}, verify=False)
    if resp.status_code == 200:
        results = resp.json()
        if isinstance(results, list) and len(results) > 0:
            return results[0]
    return None

def build_payload(rule: dict) -> dict:
    # Claude-un JSON-dan məlumatları çəkirik
    rule_name = rule.get("name", "Unnamed Rule")
    desc = rule.get("description", "")
    if "mitre_attack" in rule:
        desc += f"\n\nMITRE: {rule['mitre_attack'].get('technique', '')}"
        
    return {
        "name": rule_name,
        "description": desc,
        "type": "STANDARD",
        "enabled": False # Qaydanı sıfırdan yaratdığımız üçün default olaraq söndürülmüş formada atırıq
    }

def create_rule(payload: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}/analytics/rules", headers=get_headers(), json=payload, verify=False)

def update_rule(rule_id: int, payload: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}/analytics/rules/{rule_id}", headers=get_headers(), json=payload, verify=False)

def deploy_rule(rule_path: Path) -> bool:
    with open(rule_path, "r", encoding="utf-8") as f:
        rule_data = json.load(f)

    rule_name = rule_data.get("name", "")
    print(f"\n  [Deploying] {rule_name}")

    if not rule_name:
        print("  ❌ SKIPPED: Missing 'name' field")
        return False

    existing = get_existing_rule(rule_name)
    payload = build_payload(rule_data)

    if existing:
        resp   = update_rule(existing["id"], payload)
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
            err = resp.json()
            print(f"     Error: {err.get('message', str(err))}")
        except Exception:
            print(f"     Raw: {resp.text[:200]}")
        return False

def main():
    rules_dir  = Path(__file__).parent / "rules"
    rule_files = sorted([f for f in rules_dir.glob("*.json") if f.name != ".gitkeep"])

    print("=" * 60)
    print("  MilliSec Blue Team — QRadar Analytics Rule Deployer")
    print(f"  Target  : {QRADAR_HOST}:{QRADAR_PORT}")
    print(f"  Rules   : {len(rule_files)} files found")
    print(f"  Mode    : Analytics Rules (/api/analytics/rules)")
    print("=" * 60)

    if not rule_files:
        print("\n❌ No .json rule files found.")
        sys.exit(1)

    success = failed = 0
    for rf in rule_files:
        if deploy_rule(rf): success += 1
        else: failed += 1

    print("\n" + "=" * 60)
    print(f"  ✅ Success : {success} | ❌ Failed : {failed}")
    
    if failed > 0: sys.exit(1)

if __name__ == "__main__":
    main()
