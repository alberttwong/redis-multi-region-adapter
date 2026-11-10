module "peer_west_east1" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.west, aws.accepter = aws.east1 }
  name      = var.deployment_name
  requester = module.west.network
  accepter  = module.east1.network
}
module "peer_west_east2" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.west, aws.accepter = aws.east2 }
  name      = var.deployment_name
  requester = module.west.network
  accepter  = module.east2.network
}
module "peer_west_euwest" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.west, aws.accepter = aws.euwest }
  name      = var.deployment_name
  requester = module.west.network
  accepter  = module.euwest.network
}
module "peer_west_eucentral" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.west, aws.accepter = aws.eucentral }
  name      = var.deployment_name
  requester = module.west.network
  accepter  = module.eucentral.network
}
module "peer_east1_east2" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.east1, aws.accepter = aws.east2 }
  name      = var.deployment_name
  requester = module.east1.network
  accepter  = module.east2.network
}
module "peer_east1_euwest" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.east1, aws.accepter = aws.euwest }
  name      = var.deployment_name
  requester = module.east1.network
  accepter  = module.euwest.network
}
module "peer_east1_eucentral" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.east1, aws.accepter = aws.eucentral }
  name      = var.deployment_name
  requester = module.east1.network
  accepter  = module.eucentral.network
}
module "peer_east2_euwest" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.east2, aws.accepter = aws.euwest }
  name      = var.deployment_name
  requester = module.east2.network
  accepter  = module.euwest.network
}
module "peer_east2_eucentral" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.east2, aws.accepter = aws.eucentral }
  name      = var.deployment_name
  requester = module.east2.network
  accepter  = module.eucentral.network
}
module "peer_euwest_eucentral" {
  source    = "./modules/peering"
  providers = { aws.requester = aws.euwest, aws.accepter = aws.eucentral }
  name      = var.deployment_name
  requester = module.euwest.network
  accepter  = module.eucentral.network
}
