#!/usr/bin/env python3
"""
MilliSec Blue Team — QRadar Extension Deployer
GitHub → QRadar REST API Pipeline

Deploys rules packed as an Extension (.zip) via:
  POST /api/config/extension_management/extensions

Author: Rihad Ebilov — MilliSec Blue Team
"""

import os
import sys
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
        "Accept": "application/json",
        "Version": "12.0"
    }

# ── Extension Deployment ───────────────────────────────────────────────────────
def deploy_extension(zip_path: Path) -> bool:
    print(f"\n  [Deploying Extension] {zip_path.name}")
    url = f"{BASE_URL}/config/extension_management/extensions"
    
    with open(zip_path, 'rb') as f:
        files = {'file': (zip_path.name, f, 'application/zip')}
        resp = requests.post(url, headers=get_headers(), files=files, verify=False)
        
    if resp.status_code in (200, 201, 202):
        print(f"  ✅ Extension uploaded successfully! Status: {resp.status_code}")
        return True
    else:
        print(f"  ❌ FAILED [{resp.status_code}]")
        print(f"     Raw: {resp.text[:400]}")
        return False

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    rules_dir  = Path(__file__).parent / "rules"
    zip_files = sorted(rules_dir.glob("*.zip"))

    print("=" * 60)
    print("  MilliSec Blue Team — QRadar Extension Deployer")
    print("=" * 60)
    print(f"  Target  : {QRADAR_HOST}:{QRADAR_PORT}")
    print(f"  Auth    : SEC Token")
    print(f"  Files   : {len(zip_files)} .zip packages found")
    print(f"  Mode    : Extension Management (/api/config/extension_management/extensions)")
    print("=" * 60)

    if not zip_files:
        print("\n❌ No .zip extension files found in qradar/rules/")
        sys.exit(1)

    success = failed = 0
    for zf in zip_files:
        if deploy_extension(zf):
            success += 1
        else:
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
