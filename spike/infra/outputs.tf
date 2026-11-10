output "inventory" {
  value = {
    deployment_name     = var.deployment_name
    account_id          = var.expected_account_id
    redis_version       = var.redis_version
    license_secret_arn  = var.license_secret_arn
    admin_secret_arn    = var.admin_secret_arn
    database_secret_arn = var.database_secret_arn
    secret_region       = "us-west-2"
    dns_suffix          = aws_route53_zone.spike.name
    artifact_bucket     = aws_s3_bucket.artifacts.id
    regions = {
      "us-west-2"    = module.west.inventory
      "us-east-1"    = module.east1.inventory
      "us-east-2"    = module.east2.inventory
      "eu-west-1"    = module.euwest.inventory
      "eu-central-1" = module.eucentral.inventory
    }
  }
}
