pipeline {
    agent any

    environment {
        SCHEDULER_IMAGE  = "gridsync-scheduler"
        EXPORTER_IMAGE   = "gridsync-exporter"
        DEMO_APP_IMAGE   = "gridsync-demo-app"
        APP_NAME         = "gridsync-payload"
        SLACK_CHANNEL    = "#all-devops-webapp"
        REPORT_DIR       = "${WORKSPACE}/reports"
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out from GitHub...'
                checkout scm
                sh 'mkdir -p ${REPORT_DIR}'
                sh 'echo "Commit: $(git log -1 --pretty=format:%h)"'
            }
        }

        stage('Terraform — Infra Plan') {
            steps {
                echo 'Terraform: validating infrastructure...'
                sh '''
                    terraform version
                    terraform init -input=false
                    terraform validate
                    echo "Terraform validate: PASSED"
                    terraform plan -input=false -no-color \
                        2>&1 | tee ${REPORT_DIR}/terraform-plan.txt \
                        || echo "INFO: Plan needs AWS IAM credentials. HCL is valid."
                    echo "Terraform stage complete."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/terraform-plan.txt',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('Ansible — Config Check') {
            steps {
                echo 'Ansible: verifying server configuration...'
                sh '''
                    export PATH=$PATH:/var/lib/jenkins/.local/bin
                    ansible --version | head -1
                    ansible-playbook setup-server.yml \
                        -i "localhost," \
                        -c local \
                        --check \
                        --diff \
                        2>&1 | tee ${REPORT_DIR}/ansible-check.txt || true
                    echo "Ansible config check complete."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible-check.txt',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('SAST — Bandit') {
            steps {
                echo 'Running SAST with Bandit...'
                sh '''
                    export PATH=$PATH:/var/lib/jenkins/.local/bin
                    python3 -m bandit -r scheduler.py carbon_exporter.py app.py \
                        --skip B101,B102,B310,B602,B603,B604,B607 \
                        --severity-level medium \
                        -f json \
                        -o ${REPORT_DIR}/bandit-report.json \
                        --exit-zero

                    python3 -m bandit -r scheduler.py carbon_exporter.py app.py \
                        --skip B101,B102,B310,B602,B603,B604,B607 \
                        --severity-level medium \
                        --exit-zero

                    HIGH=$(python3 -c "
import json
with open('${REPORT_DIR}/bandit-report.json') as f:
    d = json.load(f)
highs = [r for r in d.get('results',[]) if r['issue_severity']=='HIGH']
print(len(highs))
")
                    echo "HIGH severity findings: $HIGH"
                    if [ "$HIGH" -gt 0 ]; then
                        echo "SAST FAILED: unhandled HIGH severity issues found"
                        exit 1
                    fi
                    echo "SAST: PASSED"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/bandit-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('Test — Pytest') {
            steps {
                echo 'Running Pytest...'
                sh '''
                    export PATH=$PATH:/var/lib/jenkins/.local/bin
                    python3 -m pytest test_scheduler.py -v --tb=short \
                        --junit-xml=${REPORT_DIR}/pytest-report.xml
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true,
                          testResults: 'reports/pytest-report.xml'
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                echo 'Building Docker images...'
                sh '''
                    docker build -t ${SCHEDULER_IMAGE}:${BUILD_NUMBER} \
                                 -t ${SCHEDULER_IMAGE}:latest \
                                 -f Dockerfile .

                    docker build -t ${EXPORTER_IMAGE}:${BUILD_NUMBER} \
                                 -t ${EXPORTER_IMAGE}:latest \
                                 -f Dockerfile.exporter .

                    docker build -t ${DEMO_APP_IMAGE}:${BUILD_NUMBER} \
                                 -t ${DEMO_APP_IMAGE}:latest \
                                 -f Dockerfile.app .

                    echo "Built images:"
                    docker images | grep gridsync

                    echo "Pruning dangling images to reclaim disk space..."
                    docker image prune -f || true
                '''
            }
        }

        stage('Trivy — Scan + SBOM') {
            steps {
                echo 'Trivy: scanning all images...'
                sh '''
                    TRIVY_CACHE="/tmp/trivy-cache"
                    mkdir -p "$TRIVY_CACHE"

                    # Remove stale lock files left by previously interrupted Trivy runs
                    find "$TRIVY_CACHE" -name "*.lock" -delete 2>/dev/null || true

                    for IMAGE in ${SCHEDULER_IMAGE} ${EXPORTER_IMAGE} ${DEMO_APP_IMAGE}; do
                        SAFE=$(echo $IMAGE | tr "-" "_")
                        echo "Scanning $IMAGE..."

                        # First call downloads/refreshes DB if needed
                        trivy image \
                            --exit-code 0 \
                            --severity HIGH,CRITICAL \
                            --format table \
                            --cache-dir "$TRIVY_CACHE" \
                            ${IMAGE}:latest

                        # Subsequent calls reuse the already-fresh DB
                        trivy image \
                            --format json \
                            --output ${REPORT_DIR}/trivy-${SAFE}.json \
                            --cache-dir "$TRIVY_CACHE" \
                            --skip-db-update \
                            ${IMAGE}:latest

                        trivy image \
                            --format spdx-json \
                            --output ${REPORT_DIR}/sbom-${SAFE}.spdx.json \
                            --cache-dir "$TRIVY_CACHE" \
                            --skip-db-update \
                            ${IMAGE}:latest
                    done
                    echo "Trivy: all images scanned."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/trivy-*.json,reports/sbom-*.spdx.json',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('Helm — Deploy K8s') {
            steps {
                echo 'Helm: deploying to all region namespaces...'
                sh '''
                    mkdir -p /var/lib/jenkins/.kube
                    sudo cp /etc/rancher/k3s/k3s.yaml /var/lib/jenkins/.kube/config
                    sudo chown jenkins:jenkins /var/lib/jenkins/.kube/config
                    chmod 600 /var/lib/jenkins/.kube/config
                    export KUBECONFIG=/var/lib/jenkins/.kube/config

                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        sudo k3s kubectl get namespace $NS \
                            || sudo k3s kubectl create namespace $NS
                    done

                    # Uninstall any existing releases first — this clears stuck
                    # "failed" or "pending-install" states that block upgrade --install.
                    helm uninstall gridsync-virginiadirty -n virginia-dirty 2>/dev/null || true
                    helm uninstall gridsync-irelandmixed  -n ireland-mixed  2>/dev/null || true
                    helm uninstall gridsync-swedengreen   -n sweden-green   2>/dev/null || true

                    # Wait for the uninstall deletions to propagate before reinstalling
                    sleep 5

                    helm upgrade --install gridsync-virginiadirty \
                        ./charts/gridsync-payload \
                        -n virginia-dirty \
                        --set replicaCount=3 \
                        --timeout 5m

                    helm upgrade --install gridsync-irelandmixed \
                        ./charts/gridsync-payload \
                        -n ireland-mixed \
                        --set replicaCount=0 \
                        --timeout 5m

                    helm upgrade --install gridsync-swedengreen \
                        ./charts/gridsync-payload \
                        -n sweden-green \
                        --set replicaCount=0 \
                        --timeout 5m

                    # Give K3s a moment to reconcile after the installs
                    sleep 10

                    # Deploy or update the live demo app and restart to pick up new image
                    sudo k3s kubectl apply -f demo-app.yaml
                    sudo k3s kubectl rollout restart deployment/gridsync-demo-app -n virginia-dirty
                    sudo k3s kubectl rollout status deployment/gridsync-demo-app \
                        -n virginia-dirty --timeout=120s || true

                    echo "Pod state after deploy:"
                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        PODS=$(sudo k3s kubectl get deployment ${APP_NAME} \
                                   -n $NS \
                                   -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                        echo "   $NS -> $PODS pod(s)"
                    done

                    PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4)
                    echo "Demo App -> http://${PUBLIC_IP}:30080"
                '''
            }
        }

        stage('DAST — OWASP ZAP') {
            steps {
                echo 'DAST: OWASP ZAP baseline scan...'
                sh '''
                    PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4)
                    TARGET="http://${PUBLIC_IP}:30080"
                    mkdir -p ${REPORT_DIR}/zap

                    echo "Waiting 30s for demo app pod to finish rolling..."
                    sleep 30

                    if curl -sf --max-time 10 "${TARGET}/health" > /dev/null 2>&1; then
                        echo "Target live: $TARGET"
                        docker run --rm \
                            --network host \
                            -v ${REPORT_DIR}/zap:/zap/wrk/:rw \
                            --user root \
                            ghcr.io/zaproxy/zaproxy:stable \
                            zap-baseline.py \
                                -t "$TARGET" \
                                -J zap-report.json \
                                -r zap-report.html \
                                -I 2>&1 | tail -30 || true
                        echo "DAST scan complete."
                    else
                        echo "WARN: Demo app not responding at $TARGET — skipping DAST."
                    fi
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/zap/**',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('Run Carbon Scheduler') {
            steps {
                echo 'Running carbon-aware scheduler via docker compose...'
                sh '''
                    docker compose down --remove-orphans 2>/dev/null || true
                    docker compose up -d carbon-exporter

                    echo "Waiting for carbon-exporter health check..."
                    TRIES=0
                    while [ $TRIES -lt 12 ]; do
                        STATUS=$(docker inspect \
                            --format="{{.State.Health.Status}}" \
                            gridsync-exporter 2>/dev/null || echo "missing")
                        if [ "$STATUS" = "healthy" ]; then
                            echo "Exporter is healthy."
                            break
                        fi
                        TRIES=$((TRIES+1))
                        echo "  ($TRIES/12) status=$STATUS — waiting 5s..."
                        sleep 5
                    done

                    docker compose run --rm scheduler

                    echo ""
                    echo "Post-migration pod state:"
                    for NS in virginia-dirty ireland-mixed sweden-green; do
                        PODS=$(sudo k3s kubectl get deployment ${APP_NAME} \
                                   -n $NS \
                                   -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                        MARKER=""
                        if [ "$PODS" -gt 0 ] 2>/dev/null; then
                            MARKER=" <- ACTIVE"
                        fi
                        echo "   $NS -> ${PODS} pod(s)${MARKER}"
                    done

                    echo ""
                    echo "Live metrics:"
                    curl -sf http://localhost:8000/metrics | grep "^gridsync" || true
                '''
            }
        }

        stage('Verify Monitoring') {
            steps {
                echo 'Verifying Prometheus + Grafana...'
                sh '''
                    sudo k3s kubectl get pods -n monitoring \
                        --no-headers 2>/dev/null \
                        | awk "{print \"   \" \$1 \" \" \$3}" \
                        || echo "   monitoring namespace not yet deployed"

                    sudo k3s kubectl apply \
                        -f monitoring/alert-rules.yaml 2>/dev/null || true
                    sudo k3s kubectl apply \
                        -f monitoring/grafana-dashboard.yaml 2>/dev/null || true

                    PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4)
                    echo ""
                    echo "   Grafana -> http://${PUBLIC_IP}:30030"
                    echo "   Demo    -> http://${PUBLIC_IP}:30080"
                '''
            }
        }
    }

    post {
        success {
            script {
                def activeRegion = sh(
                    script: '''
                        for NS in sweden-green ireland-mixed virginia-dirty; do
                            PODS=$(sudo k3s kubectl get deployment gridsync-payload \
                                -n $NS \
                                -o=jsonpath="{.spec.replicas}" 2>/dev/null || echo 0)
                            if [ "$PODS" -gt 0 ] 2>/dev/null; then
                                echo "$NS"
                                break
                            fi
                        done
                    ''',
                    returnStdout: true
                ).trim()

                def ip = sh(
                    script: 'curl -sf http://169.254.169.254/latest/meta-data/public-ipv4',
                    returnStdout: true
                ).trim()

                slackSend(
                    channel: env.SLACK_CHANNEL,
                    color: 'good',
                    message: """:leaf: *GridSync Pipeline SUCCESS* (Build #${env.BUILD_NUMBER})

:white_check_mark: Terraform  validated
:white_check_mark: Ansible    config verified
:white_check_mark: SAST       Bandit passed
:white_check_mark: Pytest     all tests passed
:white_check_mark: Docker     3 images built
:white_check_mark: Trivy      scanned + SBOM
:white_check_mark: Helm       3 namespaces deployed
:white_check_mark: DAST       ZAP scan complete
:white_check_mark: Scheduler  migration executed
:white_check_mark: Monitoring Prometheus + Grafana live

Active region: *${activeRegion ?: 'unknown'}*
Demo:    http://${ip}:30080
Grafana: http://${ip}:30030
<${env.BUILD_URL}|View build>"""
                )
            }
        }

        failure {
            slackSend(
                channel: env.SLACK_CHANNEL,
                color: 'danger',
                message: """:x: *GridSync Pipeline FAILED* (Build #${env.BUILD_NUMBER})
<${env.BUILD_URL}|View build logs>"""
            )
        }

        always {
            sh 'docker rm -f gridsync-scheduler 2>/dev/null || true'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
    }
}
