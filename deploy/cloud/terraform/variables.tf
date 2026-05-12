variable "region" {
  description = "Alibaba Cloud region"
  default     = "cn-hongkong"
}

variable "zone_id" {
  description = "Availability zone"
  default     = "cn-hongkong-b"
}

variable "instance_type" {
  description = "ECS instance type"
  default     = "ecs.c6.large"
}

variable "disk_size" {
  description = "System disk size in GB"
  default     = 40
}

variable "bandwidth" {
  description = "Internet bandwidth in Mbps"
  default     = 5
}

variable "ecs_password" {
  description = "ECS root password"
  type        = string
  sensitive   = true
}

variable "oss_bucket_suffix" {
  description = "Unique suffix for OSS bucket name"
  default     = "prod"
}
