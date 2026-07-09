#!/usr/bin/env python3
"""
MilliSec Blue Team — QRadar On-The-Fly Extension Deployer
GitHub (XML) → Auto-Zip in Memory → QRadar Extension API

Author: Rihad Ebilov — MilliSec Blue Team
"""

import os
import sys
import requests
import urllib3
import zipfile
import io
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

# ── On-The-Fly Compression & Deployment ────────────────────────────────────────
def deploy_xml_as_zip(xml_path: Path) -> bool:
    print(f"\n  [Processing] Reading XML: {xml_path.name}")
    
    # Python ilə faylı RAM mühitində sıxıb ZIP halına salırıq
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # XML faylını orijinal adı ilə arxivin daxilinə yazırıq
            zip_file.write(xml_path, arcname=xml_path.name)
        zip_buffer.seek(0)
        print(f"  📦 Compressed {xml_path.name} into an in-memory ZIP package.")
    except Exception as e:
        print(f"  ❌ Compression failed: {e}")
        return False

    url = f"{BASE_URL}/config/extension_management/extensions"
    zip_filename = f"{xml_path.stem}.zip"
    
    print(f"  🚀 Sending generated {zip_filename} to QRadar Extension API...")
    files = {'file': (zip_filename, zip_buffer, 'application/zip')}
    
    try:
        resp = requests.post(url, headers=get_headers(), files=files, verify=False)
        if resp.status_code in (200, 201, 202):
            print(f"  ✅ Extension uploaded successfully! Status: {resp.status_code}")
            return True
        else:
            print(f"  ❌ FAILED [{resp.status_code}]")
            print(f"     Raw: {resp.text[:400]}")
            return False
    except Exception as e:
        print(f"  ❌ API Connection failed: {e}")
        return False

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    rules_dir  = Path(__file__).parent / "rules"
    xml_files = sorted(rules_dir.glob("*.xml"))

    print("=" * 60)
    print("  MilliSec Blue Team — QRadar On-The-Fly Extension Deployer")
    print("=" * 60)
    print(f"  Target  : {QRADAR_HOST}:{QRADAR_PORT}")
    print(f"  Auth    : SEC Token")
    print(f"  Files   : {len(xml_files)} .xml rules file(s) found")
    print(f"  Mode    : Dynamic Zipping & Extension Management API")
    print("=" * 60)

    if not xml_files:
        print("\n❌ No .xml rule files found in qradar/rules/")
        sys.exit(1)

    success = failed = 0
    for xf in xml_files:
        if deploy_xml_as_zip(xf):
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
