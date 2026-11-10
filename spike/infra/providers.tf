provider "aws" {
  alias               = "west"
  region              = "us-west-2"
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = var.deployment_name, Owner = var.owner, Purpose = "latency-spike", ExpiresAt = var.expires_at }
  }
}
provider "aws" {
  alias               = "east1"
  region              = "us-east-1"
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = var.deployment_name, Owner = var.owner, Purpose = "latency-spike", ExpiresAt = var.expires_at }
  }
}
provider "aws" {
  alias               = "east2"
  region              = "us-east-2"
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = var.deployment_name, Owner = var.owner, Purpose = "latency-spike", ExpiresAt = var.expires_at }
  }
}
provider "aws" {
  alias               = "euwest"
  region              = "eu-west-1"
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = var.deployment_name, Owner = var.owner, Purpose = "latency-spike", ExpiresAt = var.expires_at }
  }
}
provider "aws" {
  alias               = "eucentral"
  region              = "eu-central-1"
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = var.deployment_name, Owner = var.owner, Purpose = "latency-spike", ExpiresAt = var.expires_at }
  }
}
