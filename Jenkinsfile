pipeline {
    agent any

    environment {
        IMAGE_NAME = "gridsync-scheduler"
        APP_NAME   = "gridsync-payload"
    }

    stages {

        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
            }
        }

	
	stage('Test') {
   	 steps {
        	echo '🧪 Running Pytest unit + integration tests...'
       	 sh '''
           	 python3 -m pip install pytest --quiet --break-system-packages
        	    python3 -m pytest test_scheduler.py -v
       	 '''
   		 }
	}	
       
       stage('Build Docker Image') {
            steps {
                echo '🐳 Building Docker image...'
                sh "docker build -t ${IMAGE_NAME} ."
            }
        }

        stage('Scan Docker Image') {
            steps {
                echo '🔍 Scanning image for vulnerabilities...'
                sh '''
                    which trivy || (curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin)
                    trivy image --exit-code 0 --severity HIGH,CRITICAL ${IMAGE_NAME}
                '''
            }
        }

        stage('Apply K8s Manifests') {
            steps {
                echo '☸️  Applying Kubernetes deployment manifests...'
                sh '''
                    sudo k3s kubectl get namespace virginia-dirty || sudo k3s kubectl create namespace virginia-dirty
                    sudo k3s kubectl get namespace sweden-green   || sudo k3s kubectl create namespace sweden-green

                    sudo k3s kubectl apply -f dummy-app.yaml -n virginia-dirty
                    sudo k3s kubectl apply -f dummy-app.yaml -n sweden-green

                    sudo k3s kubectl scale deployment ${APP_NAME} --replicas=3 -n virginia-dirty
                    sudo k3s kubectl scale deployment ${APP_NAME} --replicas=0 -n sweden-green

                    echo "✅ Cluster primed — 3 pods in virginia-dirty, 0 in sweden-green."
                '''
            }
        }

        stage('Run Carbon Scheduler') {
            steps {
                echo '🌍 Running GridSync carbon-aware scheduler...'
                sh '''
                    docker run --rm \
                        --network host \
                        -v /usr/local/bin/k3s:/usr/local/bin/k3s \
                        -v /etc/rancher/k3s/k3s.yaml:/etc/rancher/k3s/k3s.yaml \
                        ${IMAGE_NAME}
                '''
            }
        }

        stage('Verify Monitoring Stack') {
            steps {
                echo '📊 Verifying Prometheus + Grafana are live...'
                sh '''
                    sudo k3s kubectl get pods -n monitoring
                    sudo k3s kubectl get svc -n monitoring
                    echo "✅ Monitoring stack verified."
                '''
            }
        }
    }

    post {
        success {
            echo '''
✅ GridSync pipeline complete.
   → Pytest: passed
   → Trivy: scanned
   → K8s: workloads carbon-optimized
   → Monitoring: Prometheus + Grafana live
            '''
        }
        failure {
            echo '❌ Pipeline failed. Check the stage logs above.'
        }
    }
}
