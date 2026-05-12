output "ecs_public_ip" {
  value       = alicloud_eip.clawshell.ip_address
  description = "ECS public IP address"
}

output "cloud_api_url" {
  value       = "http://${alicloud_eip.clawshell.ip_address}:8000"
  description = "Cloud Hub API URL"
}

output "n8n_url" {
  value       = "http://${alicloud_eip.clawshell.ip_address}:5678"
  description = "N8N workflow engine URL"
}

output "ssh_command" {
  value       = "ssh root@${alicloud_eip.clawshell.ip_address}"
  description = "SSH connection command"
}

output "oss_bucket" {
  value       = alicloud_oss_bucket.vault.bucket
  description = "OSS vault bucket name"
}
