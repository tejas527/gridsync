pipeline {
    agent any

    environment {
        SCHEDULER_IMAGE = "gridsync-scheduler"
        EXPORTER_IMAGE  = "gridsync-exporter"
        APP_NAME        = "gridsync-payload"
        SLACK_CHANNEL   = "#gridsync-alerts"
        REPORT_DIR      = "${WORKSPACE}/reports"
    }

    stages {

        // ── Stage 1: Checkout ─────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
                sh 'mkdir -p ${REPORT_DIR}'
            }
        }

        // ── Stage 2: SAST — Bandit static security analysis ──────────────────
        // Scans Python source for security anti-patterns.
        // Archives bandit-report.json as a build artifact.
        stage('SAST — Bandit') {
            steps {
                echo '🔐 Running SAST with Bandit...'
                sh '''
                    pip3 install bandit --quiet

                    bandit -r scheduler.py carbon_exporter.py \
                        --configfile security/.bandit \
                        -f json \
                        -o ${REPORT_DIR}/bandit-report.json \
                        --exit-zero

                    bandit -r scheduler.py carbon_exporter.py \
                        --configfile security/.bandit \
                        --exit-zero

                    HIGH=$(python3 -c "
import json
with open('${REPORT_DIR}/bandit-report.json') as f:
    d = json.load(f)
highs = [r for r in d.get('results', []) if r['issue_severity'] == 'HIGH']
print(len(highs))
")
                    if [ "$HIGH" -gt 0 ]; then
                        echo "SAST FAILED: $HIGH HIGH severity issue(s) found."
                        exit 1
                    fi
                    echo "SAST passed."
                '''
            }
            post {
                always { archiveArtifacts artifacts: 'reports/bandit-report.json', allowEmptyArchive: true }
            }
        }

        // ── Stage 3: Test — Pytest unit + integration ─────────────────────────
        stage('Test — Pytest') {
            steps {
                echo '🧪 Running Pytest unit + integration tests...'
                sh '''
                    pip3 install pytest pyyaml --quiet
                    python3 -m pytest test_scheduler.py -v \
                        --tb=short \
                        --junit-xml=${REPORT_DIR}/pytest-report.xml
                '''
            }
            post {
                always { junit 'reports/pytest-report.xml' }
            }
        }

        // ── Stage 4: Build — Scheduler + Exporter Docker images ──────────────
        stage('Build Docker Images') {
            steps {
                echo '🐳 Building scheduler and exporter images...'
                sh '''
                    docker build -t ${SCHEDULER_IMAGE}:${BUILD_NUMBER} -t ${SCHEDULER_IMAGE}:latest -f Dockerfile .
                    docker build -t ${EXPORTER_IMAGE}:${BUILD_NUMBER}  -t ${EXPORTER_IMAGE}:latest  -f Dockerfile.exporter .
                    docker images | grep -E "gridsync|REPOSITORY"
                '''
            }
        }

        // ── Stage 5: Trivy — Image scan + SBOM ───────────────────────────────
        // SCA for both images. Generates JSON vulnerability report + SPDX SBOM.
        stage('Trivy — Scan + SBOM') {
            steps {
                echo '🔍 Trivy: scanning images and generating SBOMs...'
                sh '''
                    if ! command -v trivy &>/dev/null; then
                        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
                            | sh -s -- -b /usr/local/bin
                    fi

                    for IMAGE in ${SCHEDULER_IMAGE} ${EXPORTER_IMAGE}; do
                        SAFE=$(echo $IMAGE | tr '-' '_')
                        echo "── Scanning $IMAGE ──"
                        trivy image --exit-code 0 --severity HIGH,CRITICAL --format table ${IMAGE}:latest
                        trivy image --format json --output ${REPORT_DIR}/trivy-${SAFE}.json ${IMAGE}:latest
                        trivy image --format spdx-json --output ${REPORT_DIR}/sbom-${SAFE}.spdx.json ${IMAGE}:latest
                    done
                    echo "Trivy scan complete."
                '''
            }
            post {
                always { archiveArtifacts artifacts: 'reports/trivy-*.json,reports/sbom-*.json', allowEmptyArchive: true }
            }
        }

        // ── Stage 6: Helm — Deploy to all 3 namespaces ───────────────────────
        stage('Helm — Deploy K8s') {
            steps {
                echo '☸️  Helm: deploying gridsync-payload to each region namespace...'
                sh '''
                    if ! command -v helm &>/dev/null; then
                        curl -fsSL https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz | tar xz
                        sudo mv linux-amd64/helm /usr/local/bin/helm && rm -rf linux-amd64
                    fi

                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        sudo k3s kubectl get namespace $NS || sudo k3s kubectl create namespace $NS
                    done

                    KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade --install gridsync-payload-va \
                        ./charts/gridsync-payload --kubeconfig /etc/rancher/k3s/k3s.yaml \
                        -n virginia-dirty --set replicaCount=3 --wait --timeout 2m

                    KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade --install gridsync-payload-ie \
                        ./charts/gridsync-payload --kubeconfig /etc/rancher/k3s/k3s.yaml \
                        -n ireland-mixed --set replicaCount=0 --wait --timeout 2m

                    KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade --install gridsync-payload-se \
                        ./charts/gridsync-payload --kubeconfig /etc/rancher/k3s/k3s.yaml \
                        -n sweden-green --set replicaCount=0 --wait --timeout 2m

                    echo "Pre-migration state:"
                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        PODS=$(sudo k3s kubectl get deployment ${APP_NAME} -n $NS -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                        echo "   $NS → $PODS pod(s)"
                    done
                '''
            }
        }

        // ── Stage 7: DAST — OWASP ZAP baseline scan ──────────────────────────
        stage('DAST — OWASP ZAP') {
            steps {
                echo '🌐 DAST: OWASP ZAP baseline scan against running NodePort...'
                sh '''
                    chmod +x security/dast-scan.sh
                    REPORT_DIR=${REPORT_DIR} bash security/dast-scan.sh
                '''
            }
            post {
                always { archiveArtifacts artifacts: 'reports/zap-report.*', allowEmptyArchive: true }
            }
        }

        // ── Stage 8: Deploy Monitoring Stack ──────────────────────────────────
        // Idempotent — only installs kube-prometheus-stack once.
        // Applies PrometheusRules and Grafana dashboard on every run.
        stage('Deploy Monitoring Stack') {
            steps {
                echo '📊 Deploying Prometheus + Grafana (kube-prometheus-stack)...'
                sh '''
                    helm repo add prometheus-community \
                        https://prometheus-community.github.io/helm-charts 2>/dev/null || true
                    helm repo update --fail-on-repo-update-fail=false

                    sudo k3s kubectl get namespace monitoring \
                        || sudo k3s kubectl create namespace monitoring

                    KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
                    helm upgrade --install monitoring \
                        prometheus-community/kube-prometheus-stack \
                        --kubeconfig /etc/rancher/k3s/k3s.yaml \
                        -n monitoring \
                        -f monitoring/prometheus-values.yaml \
                        --timeout 5m --wait --atomic \
                        || echo "[WARN] Helm install timed out — stack may still be starting"

                    sudo k3s kubectl apply -f monitoring/alert-rules.yaml
                    sudo k3s kubectl apply -f monitoring/grafana-dashboard.yaml
                    sudo k3s kubectl apply -f monitoring/servicemonitor.yaml

                    echo ""
                    echo "Monitoring pods:"
                    sudo k3s kubectl get pods -n monitoring --no-headers 2>/dev/null \
                        | awk "{print \"   \" \$1 \" \" \$3}" || true

                    PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_EC2_IP")
                    echo ""
                    echo "   Grafana → http://${PUBLIC_IP}:30030  (admin / gridsync-admin)"
                '''
            }
        }

        // ── Stage 9: Run Carbon Scheduler (docker compose) ───────────────────
        stage('Run Carbon Scheduler') {
            steps {
                echo '🌍 Running GridSync multi-container carbon scheduler...'
                sh '''
                    docker compose down --remove-orphans 2>/dev/null || true
                    docker compose up -d carbon-exporter

                    echo "Waiting for carbon-exporter health..."
                    for i in $(seq 1 12); do
                        STATUS=$(docker inspect --format="{{.State.Health.Status}}" gridsync-exporter 2>/dev/null || echo "missing")
                        [ "$STATUS" = "healthy" ] && echo "Exporter healthy." && break
                        echo "  ($i/12) $STATUS" && sleep 5
                    done

                    docker compose run --rm scheduler

                    echo ""
                    echo "Post-migration state:"
                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        PODS=$(sudo k3s kubectl get deployment ${APP_NAME} -n $NS -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                        ACTIVE=""; [ "$PODS" -gt 0 ] 2>/dev/null && ACTIVE=" ← ACTIVE"
                        echo "   $NS → $PODS pod(s)${ACTIVE}"
                    done

                    echo ""
                    echo "Live metrics:"
                    curl -sf http://localhost:8000/metrics | grep "^gridsync" || echo "(exporter warming up)"
                '''
            }
        }
    }

    post {
        success {
            script {
                def activeRegion = sh(
                    script: '''for NS in sweden-green ireland-mixed virginia-dirty; do
                        PODS=$(sudo k3s kubectl get deployment gridsync-payload \
                            -n $NS -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                        if [ "$PODS" -gt 0 ] 2>/dev/null; then echo "$NS"; break; fi
                    done''',
                    returnStdout: true
                ).trim()

                slackSend(
                    channel: env.SLACK_CHANNEL,
                    color: 'good',
                    message: """:leaf: *GridSync Pipeline — SUCCESS* (Build #${env.BUILD_NUMBER})

:white_check_mark: SAST (Bandit)        passed
:white_check_mark: Pytest (3-region)    passed
:white_check_mark: Docker images built
:white_check_mark: Trivy + SBOM         generated
:white_check_mark: Helm (3 namespaces)  deployed
:white_check_mark: DAST (ZAP)           complete
:white_check_mark: Prometheus + Grafana live
:white_check_mark: Carbon scheduler     migrated

:round_pushpin: Active region: *${activeRegion ?: 'unknown'}*
:link: <${env.BUILD_URL}|View build>"""
                )
            }
        }

        failure {
            sh 'docker compose down --remove-orphans 2>/dev/null || true'
            slackSend(
                channel: env.SLACK_CHANNEL,
                color: 'danger',
                message: """:x: *GridSync Pipeline — FAILED* (Build #${env.BUILD_NUMBER})

Failed stage: *${env.STAGE_NAME}*
:link: <${env.BUILD_URL}|View build logs>"""
            )
        }

        always {
            sh 'docker rm -f gridsync-scheduler 2>/dev/null || true'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            echo '📡 carbon-exporter remains running for Prometheus scraping.'
        }
    }
}
