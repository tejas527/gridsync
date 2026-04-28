terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # State file stored locally for portfolio project.
  # In production: use S3 backend + DynamoDB locking.
  # backend "s3" {
  #   bucket = "gridsync-tfstate"
  #   key    = "prod/terraform.tfstate"
  #   region = "ap-southeast-2"
  # }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region to deploy GridSync into"
  default     = "ap-southeast-2"
}

variable "instance_type" {
  description = "EC2 instance type — t3.small gives 2 vCPU / 2 GB RAM for K3s + Jenkins"
  default     = "c7i-flex.large"
}

variable "key_name" {
  description = "EC2 Key Pair name for SSH access"
  default     = "tejas-key"
}

variable "project_name" {
  description = "Tag applied to all resources"
  default     = "GridSync"
}

# ── 1. Fetch latest Ubuntu 22.04 AMI dynamically ─────────────────────────────
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]   # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── 2. Security Group ──────────────────────────────────────────────────────────
resource "aws_security_group" "gridsync_sg" {
  name        = "gridsync_security_group"
  description = "GridSync: SSH, Jenkins, K3s NodePorts, demo app"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Jenkins Web UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "GridSync Demo App (NodePort 30080)"
    from_port   = 30080
    to_port     = 30080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Grafana (NodePort 30030)"
    from_port   = 30030
    to_port     = 30030
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "K3s NodePort range"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Standard HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-SG"
    Project     = var.project_name
    Environment = "DevOps-Portfolio"
  }
}

# ── 3. EC2 Instance ───────────────────────────────────────────────────────────
resource "aws_instance" "gridsync_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.gridsync_sg.id]

  # Increase root volume for Docker images + K3s
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name        = "${var.project_name}-Master-Node"
    Project     = var.project_name
    Environment = "DevOps-Portfolio"
    ManagedBy   = "Terraform"
  }
}

# ── 4. Outputs ────────────────────────────────────────────────────────────────
output "server_public_ip" {
  value       = aws_instance.gridsync_server.public_ip
  description = "EC2 public IP — use this for SSH and all browser URLs"
}

output "jenkins_url" {
  value       = "http://${aws_instance.gridsync_server.public_ip}:8080"
  description = "Jenkins CI/CD dashboard"
}

output "demo_app_url" {
  value       = "http://${aws_instance.gridsync_server.public_ip}:30080"
  description = "GridSync live demo dashboard"
}

output "grafana_url" {
  value       = "http://${aws_instance.gridsync_server.public_ip}:30030"
  description = "Grafana monitoring dashboard"
}

output "ssh_command" {
  value       = "ssh -i tejas-key.pem ubuntu@${aws_instance.gridsync_server.public_ip}"
  description = "SSH command to connect to the server"
}
