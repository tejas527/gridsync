sudo k3s kubectl create namespace virginia-dirty
sudo k3s kubectl create namespace sweden-green
nano dummy-app.yaml
sudo k3s kubectl apply -f dummy-app.yaml -n virginia-dirty
sudo k3s kubectl get pods -n virginia-dirty
sudo k3s kubectl get pods -n sweden-green
nano scheduler.py
python3 scheduler.py
sudo k3s kubectl get pods -n virginia-dirty
sudo systemctl stop jenkins
sudo k3s kubectl apply -f dummy-app.yaml -n sweden-green
sudo apt update
sudo apt install -y ansible
nano setup-server.yml
ansible-playbook setup-server.yml
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/ | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt-get update
sudo apt-get install jenkins -y
sudo wget -O /usr/share/keyrings/jenkins-keyring.asc https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt-get update
sudo apt-get install jenkins -y
sudo k3s kubectl get nodes
sudo docker ps
sudo systemctl status jenkins
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
sudo systemctl restart jenkins
l
ls
python3 scheduler.py
sudo sysctl -w vm.drop_caches=3
sudo systemctl restart k3s
sudo k3s kubectl get nodes
sudo systemctl disable jenkins
sudo reboot
sudo k3s kubectl get nodes
ls
cat dummy-app.yaml
cat scheduler.py
cat setup-server.yml
ssh -i "tejas-key.pem" ubuntu@3.26.205.222
sudo rm -f /usr/share/keyrings/jenkins-keyring.asc
sudo rm -f /etc/apt/sources.list.d/jenkins.list
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt update && sudo apt install jenkins -y
sudo k3s kubectl get deployments -n sweden-green
ls
nano setup-server.yml
nano dummy-app.yaml
nano setup-server.yml
nano dummy-app.yaml
sudo k3s kubectl apply -f dummy-app.yaml -n virginia-dirty
sudo k3s kubectl apply -f dummy-app.yaml -n sweden-green
nano dummy-app.yaml
nano scheduler.py
nano dummy-app.yaml
nano scheduler.py
sudo k3s kubectl apply -f dummy-app.yaml -n virginia-dirty
sudo k3s kubectl apply -f dummy-app.yaml -n sweden-green
nano test_scheduler.py
pytest test_scheduler.py -v
pip install pytest
pip3 install pytest
sudo apt update
sudo apt install python3-pytest
pytest test_scheduler.py -v
sudo apt update && sudo apt install python3-pytest -y
pytest test_scheduler.py -v
ls
exit
nano scheduler.py
cat scheduler.py
ls
sudo apt update && sudo apt install ansible -y
ansible-playbook setup-server.yml
sudo apt update
sudo systemctl status jenkins
sudo rm -f /usr/share/keyrings/jenkins-keyring.asc
sudo rm -f /etc/apt/sources.list.d/jenkins.list
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt update && sudo apt install jenkins -y
sudo systemctl status jenkins
sudo systemctl start jenkins
sudo systemctl status jenkins
sudo systemctl status k3s
sudo systemctl status docker
sudo k3s kubectl create namespace virginia-dirty
sudo k3s kubectl create namespace sweden-green
sudo k3s kubectl apply -f dummy-app.yaml -n virginia-dirty
sudo k3s kubectl apply -f dummy-app.yaml -n sweden-green
sudo k3s kubectl scale deployment gridsync-payload --replicas=3 -n virginia-dirty
sudo k3s kubectl scale deployment gridsync-payload --replicas=0 -n sweden-green
sudo k3s kubectl get deployments -n virginia-dirty
sudo k3s kubectl get deployments -n sweden-green
python3 scheduler.py
sudo k3s kubectl get deployments -n sweden-green
sudo k3s kubectl get deployments -n virginia-dirty
sudo k3s kubectl get deployments -n sweden-green
ls
cat dumm-app.yaml
cat dummy-app.yaml
sudo k3s kubectl get svc -n sweden-green
nano scheduler.py
nano setup-server.yml
ls
test_scheduler.py
cat test_scheduler.py
ls
nano Dockerfile
nano Jenkinsfile
cd /home/ubuntu/gridsync && git add . && git commit -m "add Jenkinsfile"
git init
git add .
git commit -m "added all initial files"
git branch -M main
git remote add origin https://github.com/tejas527/gridsync.git
git push -u origin main
ls
sudo systemctl start jenkins
sudi systemctl enable jenkins
sudo systemctl enable jenkins
sudo nano /var/lib/jenkins/config.xml
sudo systemctl restart jenkins
nano Jenkinsfile
nano alert-rules.yaml
git add alert-rules.yaml Jenkinsfile
git commit -m "add Trivy scan stage and GridSync alert rules"
git push
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
sudo apt-get clean
sudo apt-get autoremove -y
sudo docker system prune -af
sudo journalctl --vacuum-size=50M
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
sudo k3s kubectl create namespace monitoring
helm install monitoring prometheus-community/kube-prometheus-stack   --namespace monitoring   --set grafana.adminPassword=gridsync123   --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false   --kubeconfig /etc/rancher/k3s/k3s.yaml
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown ubuntu:ubuntu ~/.kube/config
helm install monitoring prometheus-community/kube-prometheus-stack   --namespace monitoring   --set grafana.adminPassword=gridsync123   --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
