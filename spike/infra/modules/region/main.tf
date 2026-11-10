terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}
variable "name" { type = string }
variable "region" { type = string }
variable "group" { type = string }
variable "cidr" { type = string }
variable "peer_cidrs" { type = list(string) }
variable "runner_instance_profile" { type = string }
variable "instance_profile" { type = string }
variable "redis_instance_type" { type = string }
variable "runner_instance_type" { type = string }
variable "installer_url" { type = string }
variable "installer_sha256" {
  type = string
  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.installer_sha256))
    error_message = "Pin the exact downloaded installer SHA256."
  }
}
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
data "aws_ami" "runner" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
data "aws_availability_zones" "available" { state = "available" }
resource "aws_vpc" "spike" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name}-${var.region}" }
}
resource "aws_internet_gateway" "spike" { vpc_id = aws_vpc.spike.id }
resource "aws_subnet" "spike" {
  count                   = 3
  vpc_id                  = aws_vpc.spike.id
  cidr_block              = cidrsubnet(var.cidr, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
}
resource "aws_route_table" "spike" { vpc_id = aws_vpc.spike.id }
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.spike.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.spike.id
}
resource "aws_route_table_association" "spike" {
  count          = 3
  route_table_id = aws_route_table.spike.id
  subnet_id      = aws_subnet.spike[count.index].id
}
resource "aws_security_group" "redis" {
  name_prefix = "${var.name}-redis-"
  vpc_id      = aws_vpc.spike.id
  description = "Redis internode and private spike traffic only; no public ingress"
  ingress {
    protocol  = "-1"
    from_port = 0
    to_port   = 0
    self      = true
  }
  dynamic "ingress" {
    for_each = toset([9443, 12000, 12001])
    content {
      protocol    = "tcp"
      from_port   = ingress.value
      to_port     = ingress.value
      cidr_blocks = var.peer_cidrs
    }
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "runner" {
  name_prefix = "${var.name}-runner-"
  vpc_id      = aws_vpc.spike.id
  description = "SSM managed runner with no inbound access"
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_instance" "redis" {
  count                  = 3
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.redis_instance_type
  subnet_id              = aws_subnet.spike[count.index].id
  vpc_security_group_ids = [aws_security_group.redis.id]
  iam_instance_profile   = var.instance_profile
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_size = 100
    volume_type = "gp3"
    encrypted   = true
  }
  user_data = templatefile("${path.module}/redis-init.sh.tftpl", {
    installer_url    = var.installer_url
    installer_sha256 = var.installer_sha256
  })
  user_data_replace_on_change = true
  tags                        = { Name = "${var.name}-${var.region}-redis-${count.index}", Role = "redis", GeographicGroup = var.group }
}
resource "aws_instance" "runner" {
  ami                    = data.aws_ami.runner.id
  instance_type          = var.runner_instance_type
  subnet_id              = aws_subnet.spike[0].id
  vpc_security_group_ids = [aws_security_group.runner.id]
  iam_instance_profile   = var.runner_instance_profile
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }
  user_data                   = file("${path.module}/runner-init.sh")
  user_data_replace_on_change = true
  tags                        = { Name = "${var.name}-${var.region}-runner", Role = "runner", GeographicGroup = var.group }
}
output "network" { value = { vpc_id = aws_vpc.spike.id, cidr = var.cidr, route_table_id = aws_route_table.spike.id, region = var.region } }
output "inventory" {
  value = {
    group          = var.group
    nodes          = [for n in aws_instance.redis : { id = n.id, private_ip = n.private_ip }]
    runner         = { id = aws_instance.runner.id, private_ip = aws_instance.runner.private_ip }
    ami_id         = data.aws_ami.ubuntu.id
    runner_ami_id  = data.aws_ami.runner.id
    primary_shards = 3
  }
}
