#!/usr/bin/env python3
"""
MilliSec Blue Team — QRadar Rule Deployer
GitHub → QRadar REST API Pipeline

Deploys rules as AQL Saved Searches via:
  POST /api/ariel/saved_searches     (create)
  POST /api/ariel/saved_searches/{id} (update)

Usage:
    export QRADAR_HOST="YOUR_QRADAR_IP"
    export QRADAR_PORT="443"
    export QRADAR_TOKEN="your-sec-token"
    python qradar/deploy_qradar.py

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
# QRadar uses SEC token header — NOT Bearer
def get_headers():
    return {
        "SEC": QRADAR_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "12.0"
    }

# ── QRadar API Helpers ─────────────────────────────────────────────────────────
def get_existing_search(search_name: str):
    """
    Returns the existing saved search dict if found, else None.
    Uses filter parameter to search by name.
    """
    encoded_name = requests.utils.quote(search_name, safe="")
    url = f"{BASE_URL}/ariel/saved_searches"
    resp = requests.get(
        url,
        headers=get_headers(),
        params={"filter": f'name="{search_name}"'},
        verify=False
    )
    if resp.status_code == 200:
        results = resp.json()
        if isinstance(results, list) and len(results) > 0:
            return results[0]
    return None


def build_payload(rule: dict) -> dict:
    """
    Constructs the JSON payload for QRadar saved search creation/update.
    """
    qradar  = rule.get("qradar", {})
    mitre   = rule.get("mitre_attack", {})

    description = (
        f"{rule.get('description', '').strip()}\n\n"
        f"Rule ID    : {rule.get('id', '')}\n"
        f"Severity   : {rule.get('severity', '')}\n"
        f"MITRE ATT&CK: {mitre.get('technique', '')} — "
        f"{mitre.get('tactic', '')} / {mitre.get('subtechnique', '')}\n"
        f"Author     : {rule.get('author', '')}\n"
        f"Version    : {rule.get('version', '1.0')}\n"
        f"Tags       : {', '.join(rule.get('tags', []))}"
    )

    return {
        "name":        rule["name"],
        "description": description,
        "aql":         qradar.get("aql", "").strip(),
        "database":    qradar.get("database", "events")
    }


def create_search(rule: dict) -> requests.Response:
    url     = f"{BASE_URL}/ariel/saved_searches"
    payload = build_payload(rule)
    return requests.post(
        url,
        headers=get_headers(),
        json=payload,
        verify=False
    )


def update_search(search_id: int, rule: dict) -> requests.Response:
    url     = f"{BASE_URL}/ariel/saved_searches/{search_id}"
    payload = build_payload(rule)
    return requests.post(
        url,
        headers=get_headers(),
        json=payload,
        verify=False
    )


# ── Rule Deployment ────────────────────────────────────────────────────────────
def deploy_rule(rule_path: Path) -> bool:
    with open(rule_path, "r", encoding="utf-8") as f:
        rule = json.load(f)

    rule_name = rule.get("name", "")
    rule_id   = rule.get("id", "")
    severity  = rule.get("severity", "").upper()
    mitre     = rule.get("mitre_attack", {}).get("technique", "N/A")

    print(f"\n  [{rule_id}] {rule_name}")
    print(f"  Severity: {severity} | MITRE: {mitre}")

    if not rule_name:
        print("  ❌ SKIPPED: Missing 'name' field in JSON")
        return False

    existing = get_existing_search(rule_name)

    if existing:
        search_id = existing.get("id")
        resp      = update_search(search_id, rule)
        action    = "UPDATED"
    else:
        resp   = create_search(rule)
        action = "CREATED"

    if resp.status_code in (200, 201):
        result_id = resp.json().get("id", "?")
        print(f"  ✅ {action} — QRadar Saved Search ID: {result_id}")
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
    rule_files = sorted([
        f for f in rules_dir.glob("*.json")
        if f.name != ".gitkeep"
    ])

    print("=" * 60)
    print("  MilliSec Blue Team — QRadar Rule Deployer")
    print("=" * 60)
    print(f"  Target  : {QRADAR_HOST}:{QRADAR_PORT}")
    print(f"  Auth    : SEC Token")
    print(f"  Rules   : {len(rule_files)} files found")
    print(f"  Mode    : AQL Saved Searches (/api/ariel/saved_searches)")
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
