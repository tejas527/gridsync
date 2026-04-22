#!/usr/bin/env bash
# local-dev/setup-minikube.sh
# ──────────────────────────────────────────────────────────────────────────────
# Sets up a local GridSync development environment using Minikube.
# This mirrors the production K3s setup on EC2, letting you iterate locally
# before pushing changes that Jenkins will pick up.
#
# Prerequisites: Docker Desktop (or HyperKit/VirtualBox), curl, helm, kubectl
# Usage: bash local-dev/setup-minikube.sh

set -euo pipefail

MINIKUBE_CPUS="${MINIKUBE_CPUS:-2}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-3072}"   # 3 GB — enough for Prometheus + Grafana
HELM_VERSION="v3.14.0"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

echo "=================================================="
echo "  GridSync — Minikube Local Dev Setup"
echo "=================================================="

# ── 1. Install Minikube if missing ────────────────────────────────────────────
if ! command -v minikube &>/dev/null; then
    info "Installing Minikube..."
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64
else
    info "Minikube already installed: $(minikube version --short)"
fi

# ── 2. Install Helm if missing ────────────────────────────────────────────────
if ! command -v helm &>/dev/null; then
    info "Installing Helm ${HELM_VERSION}..."
    curl -fsSL https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz | tar xz
    sudo mv linux-amd64/helm /usr/local/bin/helm
    rm -rf linux-amd64
else
    info "Helm already installed: $(helm version --short)"
fi

# ── 3. Start Minikube cluster ─────────────────────────────────────────────────
if minikube status | grep -q "Running"; then
    warn "Minikube is already running — skipping start."
else
    info "Starting Minikube (${MINIKUBE_CPUS} CPUs, ${MINIKUBE_MEMORY} MB RAM)..."
    minikube start \
        --cpus="${MINIKUBE_CPUS}" \
        --memory="${MINIKUBE_MEMORY}" \
        --driver=docker \
        --addons=ingress,metrics-server
fi

info "Minikube status:"
minikube status

# ── 4. Create GridSync namespaces ─────────────────────────────────────────────
info "Creating region namespaces..."
for NS in virginia-dirty ireland-mixed sweden-green monitoring; do
    kubectl get namespace "$NS" 2>/dev/null || kubectl create namespace "$NS"
    echo "   ✓ $NS"
done

# ── 5. Install Prometheus + Grafana via Helm ──────────────────────────────────
info "Adding prometheus-community Helm repo..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update

info "Installing kube-prometheus-stack (this takes ~2 min)..."
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
    -n monitoring \
    -f monitoring/prometheus-values.yaml \
    --wait \
    --timeout 5m || warn "Helm install timed out — cluster may still be starting. Re-run when pods are ready."

# ── 6. Deploy Helm chart to all 3 namespaces ─────────────────────────────────
info "Deploying gridsync-payload chart to each region..."
helm upgrade --install gridsync-payload-va  ./charts/gridsync-payload -n virginia-dirty --set replicaCount=3
helm upgrade --install gridsync-payload-ie  ./charts/gridsync-payload -n ireland-mixed  --set replicaCount=0
helm upgrade --install gridsync-payload-se  ./charts/gridsync-payload -n sweden-green   --set replicaCount=0

# ── 7. Apply monitoring manifests ────────────────────────────────────────────
info "Applying PrometheusRules and Grafana dashboard..."
kubectl apply -f monitoring/alert-rules.yaml
kubectl apply -f monitoring/grafana-dashboard.yaml
kubectl apply -f monitoring/servicemonitor.yaml

# ── 8. Run tests locally against the Minikube cluster ────────────────────────
info "Running Pytest suite..."
pip3 install pytest pyyaml --quiet
python3 -m pytest test_scheduler.py -v

# ── 9. Print access URLs ──────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo "  ✅ GridSync local dev ready!"
echo "=================================================="
MINIKUBE_IP=$(minikube ip)
info "Grafana   → http://${MINIKUBE_IP}:30030  (admin / gridsync-admin)"
info "Metrics   → http://localhost:8000/metrics  (run docker compose up -d carbon-exporter)"
echo ""
info "To simulate the scheduler locally:"
echo "   REGIONS_FILE=regions.yaml python3 scheduler.py"
echo ""
info "To tear down:"
echo "   minikube delete"
