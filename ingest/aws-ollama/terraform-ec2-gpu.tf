# Terraform configuration for EC2 GPU instance running Ollama
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply
#   terraform output instance_ip
#

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type with GPU"
  default     = "g4dn.xlarge"  # T4 GPU, ~$0.50/hr on-demand
}

variable "use_spot" {
  description = "Use spot instance for lower cost"
  default     = true
}

variable "spot_price" {
  description = "Max spot price per hour"
  default     = "0.30"  # Usually ~$0.15-0.20
}

# Latest Ubuntu 22.04 Deep Learning AMI (has NVIDIA drivers pre-installed)
data "aws_ami" "ubuntu_gpu" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security group allowing Ollama access
resource "aws_security_group" "ollama" {
  name        = "ollama-inference-server"
  description = "Allow Ollama API access"

  ingress {
    description = "Ollama API"
    from_port   = 11434
    to_port     = 11434
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Restrict to your IP in production
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Restrict to your IP in production
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# User data script
data "template_file" "user_data" {
  template = file("${path.module}/ec2-ollama-setup.sh")
}

# EC2 instance (spot or on-demand)
resource "aws_instance" "ollama_gpu" {
  count = var.use_spot ? 0 : 1

  ami           = data.aws_ami.ubuntu_gpu.id
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.ollama.id]
  user_data              = data.template_file.user_data.rendered

  root_block_device {
    volume_size = 100  # GB
    volume_type = "gp3"
  }

  tags = {
    Name = "ollama-gpu-inference"
  }
}

# Spot instance alternative
resource "aws_spot_instance_request" "ollama_gpu_spot" {
  count = var.use_spot ? 1 : 0

  ami           = data.aws_ami.ubuntu_gpu.id
  instance_type = var.instance_type
  spot_price    = var.spot_price

  vpc_security_group_ids = [aws_security_group.ollama.id]
  user_data              = data.template_file.user_data.rendered

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  wait_for_fulfillment = true

  tags = {
    Name = "ollama-gpu-inference-spot"
  }
}

output "instance_ip" {
  description = "Public IP of Ollama server"
  value       = var.use_spot ? aws_spot_instance_request.ollama_gpu_spot[0].public_ip : aws_instance.ollama_gpu[0].public_ip
}

output "ollama_url" {
  description = "Ollama API URL"
  value       = var.use_spot ? "http://${aws_spot_instance_request.ollama_gpu_spot[0].public_ip}:11434" : "http://${aws_instance.ollama_gpu[0].public_ip}:11434"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = var.use_spot ? "ssh ubuntu@${aws_spot_instance_request.ollama_gpu_spot[0].public_ip}" : "ssh ubuntu@${aws_instance.ollama_gpu[0].public_ip}"
}
