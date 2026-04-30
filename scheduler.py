import subprocess
import time
import random
import yaml
import os

# --- CONFIGURATION ---
APP_NAME = "gridsync-payload"
REGIONS_FILE = os.environ.get("REGIONS_FILE", "regions.yaml")

# Keep these for backward-compatibility with test imports
DIRTY_REGION = "virginia-dirty"
GREEN_REGION = "sweden-green"

CARBON_PROFILES = {
    "high":   (300, 500),
    "medium": (100, 250),
    "low":    (10,  50),
}


def load_regions():
    with open(REGIONS_FILE, "r") as f:
        config = yaml.safe_load(f)
    return config["regions"]


def get_mock_carbon_intensity(region_name_or_profile):
    if region_name_or_profile in CARBON_PROFILES:
        low, high = CARBON_PROFILES[region_name_or_profile]
        return random.randint(low, high)
    try:
        regions = load_regions()
        for r in regions:
            if r["name"] == region_name_or_profile:
                low, high = CARBON_PROFILES[r["carbon_profile"]]
                return random.randint(low, high)
    except Exception:
        pass
    return random.randint(100, 300)


def scale_pods(namespace, replicas):
    command = f"k3s kubectl scale deployment {APP_NAME} --replicas={replicas} -n {namespace}"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL)
        print(f"   [K8S] Scaled {namespace} → {replicas} pod(s).")
    except subprocess.CalledProcessError as e:
        print(f"   [ERROR] Failed to scale {namespace}: {e}")


def get_current_pods(namespace):
    command = f"k3s kubectl get deployment {APP_NAME} -n {namespace} -o=jsonpath='{{{{.spec.replicas}}}}'"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return int(result.stdout.strip())
    except Exception:
        return 0


def ensure_namespace(namespace):
    check = f"k3s kubectl get namespace {namespace}"
    create = f"k3s kubectl create namespace {namespace}"
    result = subprocess.run(check, shell=True, capture_output=True)
    if result.returncode != 0:
        subprocess.run(create, shell=True, check=True)
        print(f"   [K8S] Created namespace: {namespace}")


def run_scheduler():
    print("==================================================")
    print("🌍 GridSync Carbon Scheduler Initializing...")
    print("==================================================")

    try:
        regions = load_regions()
    except FileNotFoundError:
        print(f"   [ERROR] Could not find {REGIONS_FILE}. Falling back to defaults.")
        regions = [
            {"name": DIRTY_REGION, "display": "Virginia (US-East)", "namespace": DIRTY_REGION, "carbon_profile": "high"},
            {"name": GREEN_REGION,  "display": "Sweden (EU-North)",  "namespace": GREEN_REGION,  "carbon_profile": "low"},
        ]

    print(f"\n📊 Live Grid Telemetry ({len(regions)} regions):")
    readings = []
    for region in regions:
        intensity = get_mock_carbon_intensity(region["name"])
        readings.append({**region, "intensity": intensity})
        bar = "█" * (intensity // 25)
        print(f"   {region['display']:<28} {intensity:>4} gCO2/kWh  {bar}")

    best = min(readings, key=lambda r: r["intensity"])
    worst = max(readings, key=lambda r: r["intensity"])

    print(f"\n🧠 Decision Engine:")
    print(f"   Greenest region  → {best['display']} ({best['intensity']} gCO2/kWh)")
    print(f"   Dirtiest region  → {worst['display']} ({worst['intensity']} gCO2/kWh)")

    current_pods_in_best = get_current_pods(best["namespace"])

    if current_pods_in_best > 0:
        dirty_active = [
            r for r in readings
            if r["namespace"] != best["namespace"] and get_current_pods(r["namespace"]) > 0
        ]
        if not dirty_active:
            print(f"\n   [INFO] Workloads already in greenest region. No action needed.")
            return "no_action"

    print(f"\n   [ALERT] Triggering migration to {best['display']}...")

    ensure_namespace(best["namespace"])
    print(f"   [ACTION] Spinning up 3 pods in {best['namespace']}...")
    scale_pods(best["namespace"], 3)

    print(f"   [ACTION] Waiting for pods to stabilize...")
    time.sleep(3)

    for region in readings:
        if region["namespace"] != best["namespace"]:
            print(f"   [ACTION] Draining {region['namespace']}...")
            scale_pods(region["namespace"], 0)

    print(f"\n✅ MIGRATION COMPLETE: Workloads running on {best['display']} ({best['intensity']} gCO2/kWh)")
    print(f"   Carbon reduction vs dirtiest: {worst['intensity'] - best['intensity']} gCO2/kWh saved per kWh consumed.")
    return "migrate"


if __name__ == "__main__":
    run_scheduler()
