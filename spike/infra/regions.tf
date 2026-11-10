module "west" {
  source                  = "./modules/region"
  providers               = { aws = aws.west }
  name                    = var.deployment_name
  region                  = "us-west-2"
  group                   = "US"
  cidr                    = "10.60.0.0/16"
  peer_cidrs              = ["10.60.0.0/16", "10.61.0.0/16", "10.62.0.0/16", "10.63.0.0/16", "10.64.0.0/16"]
  instance_profile        = aws_iam_instance_profile.spike["redis"].name
  runner_instance_profile = aws_iam_instance_profile.spike["runner"].name
  redis_instance_type     = var.redis_instance_type
  runner_instance_type    = var.runner_instance_type
  installer_url           = var.installer_url
  installer_sha256        = var.installer_sha256
}
module "east1" {
  source                  = "./modules/region"
  providers               = { aws = aws.east1 }
  name                    = var.deployment_name
  region                  = "us-east-1"
  group                   = "US"
  cidr                    = "10.61.0.0/16"
  peer_cidrs              = ["10.60.0.0/16", "10.61.0.0/16", "10.62.0.0/16", "10.63.0.0/16", "10.64.0.0/16"]
  instance_profile        = aws_iam_instance_profile.spike["redis"].name
  runner_instance_profile = aws_iam_instance_profile.spike["runner"].name
  redis_instance_type     = var.redis_instance_type
  runner_instance_type    = var.runner_instance_type
  installer_url           = var.installer_url
  installer_sha256        = var.installer_sha256
}
module "east2" {
  source                  = "./modules/region"
  providers               = { aws = aws.east2 }
  name                    = var.deployment_name
  region                  = "us-east-2"
  group                   = "US"
  cidr                    = "10.62.0.0/16"
  peer_cidrs              = ["10.60.0.0/16", "10.61.0.0/16", "10.62.0.0/16", "10.63.0.0/16", "10.64.0.0/16"]
  instance_profile        = aws_iam_instance_profile.spike["redis"].name
  runner_instance_profile = aws_iam_instance_profile.spike["runner"].name
  redis_instance_type     = var.redis_instance_type
  runner_instance_type    = var.runner_instance_type
  installer_url           = var.installer_url
  installer_sha256        = var.installer_sha256
}
module "euwest" {
  source                  = "./modules/region"
  providers               = { aws = aws.euwest }
  name                    = var.deployment_name
  region                  = "eu-west-1"
  group                   = "EU"
  cidr                    = "10.63.0.0/16"
  peer_cidrs              = ["10.60.0.0/16", "10.61.0.0/16", "10.62.0.0/16", "10.63.0.0/16", "10.64.0.0/16"]
  instance_profile        = aws_iam_instance_profile.spike["redis"].name
  runner_instance_profile = aws_iam_instance_profile.spike["runner"].name
  redis_instance_type     = var.redis_instance_type
  runner_instance_type    = var.runner_instance_type
  installer_url           = var.installer_url
  installer_sha256        = var.installer_sha256
}
module "eucentral" {
  source                  = "./modules/region"
  providers               = { aws = aws.eucentral }
  name                    = var.deployment_name
  region                  = "eu-central-1"
  group                   = "EU"
  cidr                    = "10.64.0.0/16"
  peer_cidrs              = ["10.60.0.0/16", "10.61.0.0/16", "10.62.0.0/16", "10.63.0.0/16", "10.64.0.0/16"]
  instance_profile        = aws_iam_instance_profile.spike["redis"].name
  runner_instance_profile = aws_iam_instance_profile.spike["runner"].name
  redis_instance_type     = var.redis_instance_type
  runner_instance_type    = var.runner_instance_type
  installer_url           = var.installer_url
  installer_sha256        = var.installer_sha256
}
