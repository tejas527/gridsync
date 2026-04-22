#!/usr/bin/env bash
# dast-scan.sh — OWASP ZAP baseline scan against the running K3s NodePort service
# Runs in Jenkins Stage: DAST. Uses ZAP Docker image (no install needed).
# --exit-code 0 means the pipeline won't fail on ZAP findings — just reports them.

set -euo pipefail

APP_NAME="gridsync-payload"
NAMESPACE="${DAST_NAMESPACE:-virginia-dirty}"
REPORT_DIR="${REPORT_DIR:-/tmp/zap-reports}"
mkdir -p "$REPORT_DIR"

echo "=================================================="
echo "🔍 DAST: OWASP ZAP Baseline Scan"
echo "   Namespace : $NAMESPACE"
echo "=================================================="

# ── 1. Resolve the NodePort ───────────────────────────────────────────────────
NODE_PORT=$(sudo k3s kubectl get svc gridsync-payload-svc \
    -n "$NAMESPACE" \
    -o=jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")

if [ -z "$NODE_PORT" ]; then
    echo "   [WARN] Could not find NodePort for gridsync-payload-svc in $NAMESPACE."
    echo "   [WARN] Skipping DAST — service may not be deployed yet."
    exit 0
fi

TARGET="http://localhost:${NODE_PORT}"
echo "   Target URL : $TARGET"

# ── 2. Verify target is reachable ────────────────────────────────────────────
if ! curl -sf --max-time 5 "$TARGET" > /dev/null; then
    echo "   [WARN] Target $TARGET is not responding. Skipping DAST."
    exit 0
fi

echo "   [OK] Target is reachable. Launching ZAP baseline scan..."

# ── 3. Run ZAP baseline scan ─────────────────────────────────────────────────
# -t = target URL
# -J = JSON report path inside the container (mapped via volume)
# -r = HTML report path inside the container
# --exit-code 0 = never fail the build (informational only in portfolio context)
docker run --rm \
    --network host \
    -v "$REPORT_DIR":/zap/wrk/:rw \
    --user root \
    ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py \
        -t "$TARGET" \
        -J zap-report.json \
        -r zap-report.html \
        -I 2>&1 | tee /tmp/zap-output.txt

echo ""
echo "   [DAST] ZAP scan complete."
echo "   Reports written to: $REPORT_DIR"

# ── 4. Print a summary from the JSON report ───────────────────────────────────
if command -v python3 &>/dev/null && [ -f "$REPORT_DIR/zap-report.json" ]; then
    python3 - <<'PYEOF'
import json, sys
try:
    with open("/tmp/zap-reports/zap-report.json") as f:
        data = json.load(f)
    alerts = data.get("site", [{}])[0].get("alerts", [])
    counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
    for a in alerts:
        risk = a.get("riskdesc", "").split(" ")[0]
        counts[risk] = counts.get(risk, 0) + 1
    print("   DAST Summary:")
    for level, count in counts.items():
        flag = "⚠️ " if level in ("High", "Medium") and count > 0 else "   "
        print(f"   {flag}{level}: {count}")
except Exception as e:
    print(f"   (Could not parse ZAP JSON report: {e})")
PYEOF
fi

echo "   Full HTML report: $REPORT_DIR/zap-report.html"
