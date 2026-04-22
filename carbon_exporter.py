"""
carbon_exporter.py — GridSync Prometheus Metrics Exporter
A second container that continuously samples mock carbon intensity
for all configured regions and exposes them at /metrics for Prometheus.

Exposes:
  gridsync_carbon_intensity_gco2_kwh{region, zone}  — current carbon reading
  gridsync_active_region{region, zone}               — 1 if workloads are running here, 0 if not
  gridsync_migration_total                           — counter of migrations triggered
"""

import random
import time
import threading
import yaml
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Config ────────────────────────────────────────────────────────────────────
REGIONS_FILE   = os.environ.get("REGIONS_FILE", "regions.yaml")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "15"))   # seconds
PORT           = int(os.environ.get("EXPORTER_PORT", "8000"))

CARBON_PROFILES = {
    "high":   (300, 500),
    "medium": (100, 250),
    "low":    (10,  50),
}

# ── Shared state (written by background thread, read by HTTP handler) ─────────
state_lock      = threading.Lock()
current_metrics = {}          # {namespace: {"intensity": int, "active": int, "display": str}}
migration_count = 0


def load_regions():
    with open(REGIONS_FILE, "r") as f:
        return yaml.safe_load(f)["regions"]


def sample_carbon(region):
    low, high = CARBON_PROFILES[region["carbon_profile"]]
    return random.randint(low, high)


def update_metrics():
    """Background thread: re-samples all regions every SCRAPE_INTERVAL seconds."""
    global migration_count

    try:
        regions = load_regions()
    except Exception as e:
        print(f"[ERROR] Could not load {REGIONS_FILE}: {e}")
        return

    while True:
        readings = []
        for r in regions:
            intensity = sample_carbon(r)
            readings.append({**r, "intensity": intensity})

        # Determine the greenest region
        best = min(readings, key=lambda r: r["intensity"])

        with state_lock:
            prev_active = {
                ns: d["active"]
                for ns, d in current_metrics.items()
            }

            current_metrics.clear()
            for r in readings:
                is_active = 1 if r["namespace"] == best["namespace"] else 0
                current_metrics[r["namespace"]] = {
                    "intensity": r["intensity"],
                    "active":    is_active,
                    "display":   r["display"],
                }

            # Count a migration if the active region changed
            new_active = {ns: d["active"] for ns, d in current_metrics.items()}
            if prev_active and new_active != prev_active:
                migration_count += 1
                print(f"[SCHEDULER] Migration detected → active region is now {best['display']}")

        print(f"[METRICS] Sampled {len(readings)} regions. Greenest: {best['display']} ({best['intensity']} gCO2/kWh)")
        time.sleep(SCRAPE_INTERVAL)


def build_prometheus_output():
    """Serialises current_metrics into the Prometheus text exposition format."""
    lines = []

    lines.append("# HELP gridsync_carbon_intensity_gco2_kwh Simulated grid carbon intensity in gCO2/kWh")
    lines.append("# TYPE gridsync_carbon_intensity_gco2_kwh gauge")

    lines.append("# HELP gridsync_active_region 1 if workloads are currently scheduled to this region")
    lines.append("# TYPE gridsync_active_region gauge")

    with state_lock:
        for namespace, data in current_metrics.items():
            label = f'region="{namespace}",zone="{data["display"]}"'
            lines.append(f'gridsync_carbon_intensity_gco2_kwh{{{label}}} {data["intensity"]}')
            lines.append(f'gridsync_active_region{{{label}}} {data["active"]}')

        lines.append("# HELP gridsync_migration_total Total number of workload migrations triggered")
        lines.append("# TYPE gridsync_migration_total counter")
        lines.append(f"gridsync_migration_total {migration_count}")

    return "\n".join(lines) + "\n"


# ── HTTP Server ───────────────────────────────────────────────────────────────
class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default access log noise

    def do_GET(self):
        if self.path == "/metrics":
            body = build_prometheus_output().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    print(f"[EXPORTER] GridSync Carbon Exporter starting on :{PORT}")
    print(f"[EXPORTER] Scrape interval: {SCRAPE_INTERVAL}s | Regions file: {REGIONS_FILE}")

    # Start background sampling thread
    t = threading.Thread(target=update_metrics, daemon=True)
    t.start()

    # Give the first sample time to populate before serving
    time.sleep(2)

    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    print(f"[EXPORTER] Listening — curl http://localhost:{PORT}/metrics")
    server.serve_forever()
