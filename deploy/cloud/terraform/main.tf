provider "alicloud" {
  region = var.region
}

# ── VPC + vSwitch ──
resource "alicloud_vpc" "clawshell" {
  vpc_name   = "clawshell-vpc"
  cidr_block = "10.0.0.0/16"
}

resource "alicloud_vswitch" "clawshell" {
  vpc_id       = alicloud_vpc.clawshell.id
  cidr_block   = "10.0.1.0/24"
  zone_id      = var.zone_id
  vswitch_name = "clawshell-vswitch"
}

# ── Security Group ──
resource "alicloud_security_group" "clawshell" {
  name        = "clawshell-sg"
  description = "ClawShell Cloud Hub security group"
  vpc_id      = alicloud_vpc.clawshell.id
}

resource "alicloud_security_group_rule" "ssh" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "22/22"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "http" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "80/80"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "https" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "443/443"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "api" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "8000/8000"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "n8n" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "5678/5678"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "egress" {
  type              = "egress"
  ip_protocol       = "all"
  port_range        = "-1/-1"
  security_group_id = alicloud_security_group.clawshell.id
  cidr_ip           = "0.0.0.0/0"
}

# ── ECS Instance ──
resource "alicloud_instance" "clawshell" {
  instance_name   = "clawshell-cloud-hub"
  host_name       = "clawshell"
  instance_type   = var.instance_type
  image_id        = "ubuntu_22_04_x64_20G_alibase_20230208.vhd"
  system_disk_category = "cloud_essd"
  system_disk_size     = var.disk_size

  vswitch_id      = alicloud_vswitch.clawshell.id
  security_groups = [alicloud_security_group.clawshell.id]

  internet_max_bandwidth_out = var.bandwidth
  internet_charge_type       = "PayByTraffic"

  password = var.ecs_password

  user_data = file("${path.module}/user_data.sh")
}

# ── Elastic IP ──
resource "alicloud_eip" "clawshell" {
  bandwidth            = var.bandwidth
  internet_charge_type = "PayByTraffic"
}

resource "alicloud_eip_association" "clawshell" {
  allocation_id = alicloud_eip.clawshell.id
  instance_id   = alicloud_instance.clawshell.id
}

# ── OSS Bucket ──
resource "alicloud_oss_bucket" "vault" {
  bucket = "clawshell-vault-${var.oss_bucket_suffix}"
  acl    = "private"
}
