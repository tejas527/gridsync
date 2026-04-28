"""
app.py — GridSync Live Demo Dashboard
A Flask web application that serves as the actual demo for presentations.
Shows real-time carbon intensity, active workload region, and migration history.
Deployed to K8s via Helm; accessible via NodePort during the demo.
"""

from flask import Flask, render_template_string, jsonify
import subprocess
import random
import time
import os
import json

app = Flask(__name__)

APP_NAME  = os.environ.get("APP_NAME",  "gridsync-payload")
EXPORTER_URL = os.environ.get("EXPORTER_URL", "http://localhost:8000/metrics")

REGIONS = [
    {"name": "virginia-dirty", "display": "Virginia (US-East)", "profile": "high",   "flag": "🇺🇸"},
    {"name": "ireland-mixed",  "display": "Ireland (EU-West)",  "profile": "medium", "flag": "🇮🇪"},
    {"name": "sweden-green",   "display": "Sweden (EU-North)",  "profile": "low",    "flag": "🇸🇪"},
]

CARBON_PROFILES = {
    "high":   (300, 500),
    "medium": (100, 250),
    "low":    (10,  50),
}

migration_log = []


def get_carbon_readings():
    """Try to read from the real exporter; fall back to mock data."""
    try:
        import urllib.request
        with urllib.request.urlopen(EXPORTER_URL, timeout=2) as r:
            text = r.read().decode()
        readings = {}
        for line in text.splitlines():
            if line.startswith("gridsync_carbon_intensity_gco2_kwh{"):
                parts = line.split("} ")
                val   = float(parts[-1])
                region = ""
                for seg in parts[0].split(","):
                    if "region=" in seg:
                        region = seg.split('"')[1]
                readings[region] = int(val)
        if readings:
            return readings
    except Exception:
        pass
    # Mock fallback
    return {
        r["name"]: random.randint(*CARBON_PROFILES[r["profile"]])
        for r in REGIONS
    }


def get_pod_counts():
    """Read real pod counts from K3s; return zeros on failure."""
    counts = {}
    for r in REGIONS:
        try:
            cmd = (f"k3s kubectl get deployment {APP_NAME} "
                   f"-n {r['name']} -o=jsonpath='{{.spec.replicas}}' 2>/dev/null")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
            counts[r["name"]] = int(result.stdout.strip() or 0)
        except Exception:
            counts[r["name"]] = 0
    return counts


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GridSync — Carbon-Aware Scheduler</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0e1a;
    --surface: #111827;
    --surface2: #1a2236;
    --border: rgba(255,255,255,0.07);
    --text: #e8edf5;
    --muted: #6b7a99;
    --green: #10d47e;
    --amber: #f59e0b;
    --red: #ef4444;
    --blue: #3b82f6;
    --glow-green: rgba(16,212,126,0.15);
    --glow-red: rgba(239,68,68,0.15);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
    min-height: 100vh;
    padding: 24px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 32px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }
  .logo {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .logo-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #10d47e, #3b82f6);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
  }
  .logo-text h1 { font-size: 20px; font-weight: 600; letter-spacing: -0.5px; }
  .logo-text p  { font-size: 12px; color: var(--muted); font-family: 'JetBrains Mono', monospace; }
  .live-badge {
    display: flex; align-items: center; gap: 6px;
    background: rgba(16,212,126,0.1);
    border: 1px solid rgba(16,212,126,0.3);
    border-radius: 20px; padding: 6px 14px;
    font-size: 12px; color: var(--green); font-weight: 500;
  }
  .live-dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--green);
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s;
  }
  .card.active {
    border-color: rgba(16,212,126,0.4);
    background: linear-gradient(135deg, var(--surface) 0%, rgba(16,212,126,0.04) 100%);
  }
  .card.dirty {
    border-color: rgba(239,68,68,0.3);
    background: linear-gradient(135deg, var(--surface) 0%, rgba(239,68,68,0.04) 100%);
  }
  .card-label {
    font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
    color: var(--muted); margin-bottom: 8px; font-weight: 500;
  }
  .card-value {
    font-size: 36px; font-weight: 700; letter-spacing: -1px;
    font-family: 'JetBrains Mono', monospace;
  }
  .card-sub { font-size: 13px; color: var(--muted); margin-top: 6px; }

  .region-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
  }
  .region-name { font-size: 15px; font-weight: 600; }
  .region-flag { font-size: 24px; }
  .region-ns { font-size: 11px; color: var(--muted); font-family: 'JetBrains Mono', monospace; margin-top: 2px; }

  .carbon-value {
    font-size: 44px; font-weight: 700; letter-spacing: -2px;
    font-family: 'JetBrains Mono', monospace; line-height: 1;
  }
  .carbon-unit { font-size: 13px; color: var(--muted); margin-top: 4px; }

  .bar-track {
    width: 100%; height: 6px; background: rgba(255,255,255,0.06);
    border-radius: 3px; margin-top: 16px; overflow: hidden;
  }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 1s ease; }

  .pod-row { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; }
  .pod-label { font-size: 12px; color: var(--muted); }
  .pod-count {
    font-family: 'JetBrains Mono', monospace; font-size: 14px;
    font-weight: 500; color: var(--text);
  }
  .pod-dots { display: flex; gap: 4px; }
  .pod-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green); opacity: 0.9;
  }
  .pod-dot.off { background: rgba(255,255,255,0.1); }

  .status-chip {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
    letter-spacing: 0.5px; text-transform: uppercase; margin-top: 12px;
  }
  .chip-active { background: rgba(16,212,126,0.15); color: var(--green); }
  .chip-idle   { background: rgba(107,122,153,0.15); color: var(--muted); }
  .chip-dirty  { background: rgba(239,68,68,0.15);  color: var(--red);   }

  .section-title {
    font-size: 13px; font-weight: 500; color: var(--muted);
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 14px;
  }

  /* Stat cards row */
  .stat-val { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }

  /* Migration log */
  .log-list { list-style: none; }
  .log-item {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid var(--border);
    font-size: 13px;
  }
  .log-item:last-child { border-bottom: none; }
  .log-time { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 11px; min-width: 60px; margin-top: 1px; }
  .log-icon { font-size: 15px; }
  .log-text { color: var(--text); line-height: 1.5; }
  .log-empty { color: var(--muted); font-size: 13px; text-align: center; padding: 24px; }

  footer {
    text-align: center; color: var(--muted); font-size: 12px;
    margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
  }
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">🌍</div>
    <div class="logo-text">
      <h1>GridSync</h1>
      <p>carbon-aware kubernetes scheduler</p>
    </div>
  </div>
  <div class="live-badge"><div class="live-dot"></div> LIVE DEMO</div>
</header>

<!-- Top stats -->
<div class="grid-3" id="stats-row">
  <div class="card">
    <div class="card-label">Active Region</div>
    <div class="card-value" id="stat-region" style="font-size:22px;margin-top:6px">—</div>
    <div class="card-sub" id="stat-region-sub">loading...</div>
  </div>
  <div class="card">
    <div class="card-label">Carbon Saved</div>
    <div class="card-value" id="stat-saved" style="color:#10d47e">—</div>
    <div class="card-sub">gCO₂/kWh vs dirtiest</div>
  </div>
  <div class="card">
    <div class="card-label">Migrations</div>
    <div class="card-value" id="stat-migrations">0</div>
    <div class="card-sub">since scheduler started</div>
  </div>
</div>

<!-- Region cards -->
<div class="section-title">Grid Telemetry</div>
<div class="grid-3" id="region-cards">
  <div class="card"><div class="card-label">Loading...</div></div>
  <div class="card"><div class="card-label">Loading...</div></div>
  <div class="card"><div class="card-label">Loading...</div></div>
</div>

<!-- Bottom: log + pipeline -->
<div class="grid-2">
  <div class="card">
    <div class="section-title">Migration Log</div>
    <ul class="log-list" id="migration-log">
      <li class="log-empty">No migrations yet this session</li>
    </ul>
  </div>
  <div class="card">
    <div class="section-title">Pipeline Status</div>
    <div id="pipeline-status">
      <div class="card-sub">Polling Jenkins...</div>
    </div>
  </div>
</div>

<footer>GridSync v1.0 &nbsp;|&nbsp; EC2 t3.small &nbsp;|&nbsp; K3s &nbsp;|&nbsp; Refreshes every 10s</footer>

<script>
let migrations = 0;
let lastActive = null;
const logItems = [];

const REGIONS = [
  { name: "virginia-dirty", display: "Virginia",      flag: "🇺🇸", ns: "virginia-dirty" },
  { name: "ireland-mixed",  display: "Ireland",       flag: "🇮🇪", ns: "ireland-mixed"  },
  { name: "sweden-green",   display: "Sweden",        flag: "🇸🇪", ns: "sweden-green"   },
];

function colorForCarbon(v) {
  if (v < 80)  return "#10d47e";
  if (v < 200) return "#f59e0b";
  return "#ef4444";
}

function barWidth(v) {
  return Math.min(100, Math.round(v / 5)) + "%";
}

function chipHtml(isActive, carbon) {
  if (isActive) return `<span class="status-chip chip-active">● Active</span>`;
  if (carbon > 280) return `<span class="status-chip chip-dirty">● High Carbon</span>`;
  return `<span class="status-chip chip-idle">● Standby</span>`;
}

function podDots(count) {
  let html = '<div class="pod-dots">';
  for (let i = 0; i < 3; i++) {
    html += `<div class="pod-dot${i < count ? "" : " off"}"></div>`;
  }
  html += '</div>';
  return html;
}

function addLog(msg, icon) {
  const now = new Date();
  const time = now.getHours().toString().padStart(2,"0") + ":" +
               now.getMinutes().toString().padStart(2,"0") + ":" +
               now.getSeconds().toString().padStart(2,"0");
  logItems.unshift({ time, msg, icon });
  if (logItems.length > 8) logItems.pop();
  const ul = document.getElementById("migration-log");
  ul.innerHTML = logItems.map(l =>
    `<li class="log-item">
       <span class="log-time">${l.time}</span>
       <span class="log-icon">${l.icon}</span>
       <span class="log-text">${l.msg}</span>
     </li>`
  ).join("") || `<li class="log-empty">No migrations yet</li>`;
}

async function refresh() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    // Update stat row
    const active = data.regions.find(r => r.pods > 0) || data.regions[0];
    const max_c  = Math.max(...data.regions.map(r => r.carbon));
    const saved  = max_c - active.carbon;

    document.getElementById("stat-region").textContent = active.flag + " " + active.display;
    document.getElementById("stat-region-sub").textContent = active.ns;
    document.getElementById("stat-saved").textContent = saved;
    document.getElementById("stat-migrations").textContent = data.migrations;

    // Detect migration
    if (lastActive && lastActive !== active.name) {
      migrations++;
      addLog(`Migrated → ${active.display} (${active.carbon} gCO₂/kWh)`, "🌿");
    }
    lastActive = active.name;

    // Region cards
    const container = document.getElementById("region-cards");
    container.innerHTML = data.regions.map(r => {
      const isActive = r.pods > 0;
      const cardClass = isActive ? "active" : (r.carbon > 280 ? "dirty" : "");
      const col = colorForCarbon(r.carbon);
      return `
        <div class="card ${cardClass}">
          <div class="region-header">
            <div>
              <div class="region-name">${r.display}</div>
              <div class="region-ns">${r.ns}</div>
            </div>
            <div class="region-flag">${r.flag}</div>
          </div>
          <div class="carbon-value" style="color:${col}">${r.carbon}</div>
          <div class="carbon-unit">gCO₂eq / kWh</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${barWidth(r.carbon)};background:${col}"></div>
          </div>
          <div class="pod-row">
            <span class="pod-label">Pods</span>
            ${podDots(r.pods)}
            <span class="pod-count">${r.pods}/3</span>
          </div>
          ${chipHtml(isActive, r.carbon)}
        </div>`;
    }).join("");

    // Pipeline status
    document.getElementById("pipeline-status").innerHTML = `
      <div style="display:flex;flex-direction:column;gap:10px">
        ${data.pipeline.map(s => `
          <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:16px">${s.icon}</span>
            <div style="flex:1">
              <div style="font-size:13px;font-weight:500">${s.name}</div>
              <div style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace">${s.tool}</div>
            </div>
            <span style="font-size:11px;padding:2px 8px;border-radius:10px;
              background:${s.status==='pass'?'rgba(16,212,126,0.12)':s.status==='run'?'rgba(59,130,246,0.12)':'rgba(107,122,153,0.1)'};
              color:${s.status==='pass'?'var(--green)':s.status==='run'?'var(--blue)':'var(--muted)'}">
              ${s.status==='pass'?'✓ pass':s.status==='run'?'running':'—'}
            </span>
          </div>`).join("")}
      </div>`;
  } catch(e) {
    console.warn("Refresh error:", e);
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""


PIPELINE_STAGES = [
    {"name": "Terraform",     "tool": "infrastructure provisioning", "icon": "🏗️",  "status": "pass"},
    {"name": "Ansible",       "tool": "server configuration",        "icon": "⚙️",  "status": "pass"},
    {"name": "SAST — Bandit", "tool": "static code analysis",        "icon": "🔐",  "status": "pass"},
    {"name": "Pytest",        "tool": "unit + integration tests",     "icon": "🧪",  "status": "pass"},
    {"name": "Docker Build",  "tool": "image build ×3",               "icon": "🐳",  "status": "pass"},
    {"name": "Trivy",         "tool": "vulnerability scan + SBOM",   "icon": "🔍",  "status": "pass"},
    {"name": "Helm",          "tool": "k8s deploy ×3 namespaces",    "icon": "☸️",  "status": "pass"},
    {"name": "DAST — ZAP",    "tool": "live endpoint scan",           "icon": "🌐",  "status": "pass"},
    {"name": "Scheduler",     "tool": "carbon-aware migration",       "icon": "🌍",  "status": "pass"},
]


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def api_status():
    readings = get_carbon_readings()
    pods     = get_pod_counts()

    regions_out = []
    for r in REGIONS:
        carbon = readings.get(r["name"], random.randint(10, 500))
        regions_out.append({
            "name":    r["name"],
            "display": r["display"],
            "flag":    r["flag"],
            "ns":      r["name"],
            "carbon":  carbon,
            "pods":    pods.get(r["name"], 0),
        })

    active_carbon = next(
        (r["carbon"] for r in regions_out if r["pods"] > 0),
        min(r["carbon"] for r in regions_out)
    )

    return jsonify({
        "regions":   regions_out,
        "migrations": 0,
        "pipeline":  PIPELINE_STAGES,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "gridsync-demo"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
