variable "aws_profile" { type = string }
variable "expected_account_id" { type = string }
variable "deployment_name" {
  type    = string
  default = "redis-session-spike-20261109"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{5,39}$", var.deployment_name))
    error_message = "Use 6-40 lowercase alphanumeric/hyphen characters."
  }
}
variable "redis_version" {
  type    = string
  default = "8.2.6-25"
}
variable "installer_url" {
  type    = string
  default = "https://redis-enterprise-software-downloads.s3.amazonaws.com/8.2.6/redislabs-8.2.6-25-jammy-amd64.tar"
  validation {
    condition     = startswith(var.installer_url, "https://redis-enterprise-software-downloads.s3.amazonaws.com/")
    error_message = "Use the official HTTPS Redis Software download origin."
  }
}
variable "installer_sha256" { type = string }
variable "license_secret_arn" { type = string }
variable "admin_secret_arn" { type = string }
variable "redis_instance_type" {
  type    = string
  default = "m6i.xlarge"
}
variable "runner_instance_type" {
  type    = string
  default = "c6i.large"
}
variable "owner" { type = string }
variable "expires_at" {
  type        = string
  description = "UTC expiry label; not an automatic deletion schedule."
}

variable "database_secret_arn" { type = string }
