import subprocess
import time
import random

# --- CONFIGURATION ---
APP_NAME = "gridsync-payload"
DIRTY_REGION = "virginia-dirty"
GREEN_REGION = "sweden-green"

def get_mock_carbon_intensity(region):
    if region == DIRTY_REGION:
        return random.randint(300, 500)
    else:
        return random.randint(10, 50)

def scale_pods(namespace, replicas):
    command = f"sudo k3s kubectl scale deployment {APP_NAME} --replicas={replicas} -n {namespace}"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL)
        print(f"   [K8S] Successfully scaled {namespace} to {replicas} pods.")
    except subprocess.CalledProcessError as e:
        print(f"   [ERROR] Failed to scale {namespace}: {e}")

def get_current_pods(namespace):
    command = f"sudo k3s kubectl get deployment {APP_NAME} -n {namespace} -o=jsonpath='{{{{.spec.replicas}}}}'"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return int(result.stdout.strip())
    except Exception:
        return 0

def run_scheduler():
    print("==================================================")
    print("🌍 GridSync Carbon Scheduler Initializing...")
    print("==================================================")

    va_carbon = get_mock_carbon_intensity(DIRTY_REGION)
    se_carbon = get_mock_carbon_intensity(GREEN_REGION)

    print(f"📊 Current Grid Telemetry:")
    print(f"   - Virginia (US-East) : {va_carbon} gCO2/kWh")
    print(f"   - Sweden (EU-North)  : {se_carbon} gCO2/kWh")
    print("\n🧠 Evaluating Workload Placement...")

    if va_carbon > se_carbon:
        print(f"   [ALERT] Virginia carbon intensity is too high! Triggering migration...")
        if get_current_pods(GREEN_REGION) == 0:
            print("   [ACTION] Spinning up 3 Pods in Sweden-Green...")
            scale_pods(GREEN_REGION, 3)
            time.sleep(2)
            print("   [ACTION] Draining Workloads from Virginia-Dirty...")
            scale_pods(DIRTY_REGION, 0)
            print("\n✅ MIGRATION COMPLETE: Workloads are now running on 100% clean energy.")
        else:
            print("   [INFO] Workloads are already optimized in the Green region.")
        return "migrate"
    else:
        print("   [INFO] Current region is optimal. No migration needed.")
        return "no_action"

if __name__ == "__main__":
    run_scheduler()
