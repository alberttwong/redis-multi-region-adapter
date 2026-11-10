resource "aws_route53_zone" "spike" {
  provider = aws.west
  name     = "${var.deployment_name}.internal"
  vpc {
    vpc_id     = module.west.network.vpc_id
    vpc_region = "us-west-2"
  }
  lifecycle { ignore_changes = [vpc] }
}
resource "aws_route53_record" "west_cluster" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "us-west-2.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.west.inventory.nodes[0].private_ip]
}
resource "aws_route53_record" "west_wildcard" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "*.us-west-2.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.west.inventory.nodes[0].private_ip]
}
resource "aws_route53_zone_association" "east1" {
  provider   = aws.west
  zone_id    = aws_route53_zone.spike.zone_id
  vpc_id     = module.east1.network.vpc_id
  vpc_region = "us-east-1"
}
resource "aws_route53_record" "east1_cluster" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "us-east-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.east1.inventory.nodes[0].private_ip]
}
resource "aws_route53_record" "east1_wildcard" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "*.us-east-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.east1.inventory.nodes[0].private_ip]
}
resource "aws_route53_zone_association" "east2" {
  provider   = aws.west
  zone_id    = aws_route53_zone.spike.zone_id
  vpc_id     = module.east2.network.vpc_id
  vpc_region = "us-east-2"
}
resource "aws_route53_record" "east2_cluster" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "us-east-2.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.east2.inventory.nodes[0].private_ip]
}
resource "aws_route53_record" "east2_wildcard" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "*.us-east-2.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.east2.inventory.nodes[0].private_ip]
}
resource "aws_route53_zone_association" "euwest" {
  provider   = aws.west
  zone_id    = aws_route53_zone.spike.zone_id
  vpc_id     = module.euwest.network.vpc_id
  vpc_region = "eu-west-1"
}
resource "aws_route53_record" "euwest_cluster" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "eu-west-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.euwest.inventory.nodes[0].private_ip]
}
resource "aws_route53_record" "euwest_wildcard" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "*.eu-west-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.euwest.inventory.nodes[0].private_ip]
}
resource "aws_route53_zone_association" "eucentral" {
  provider   = aws.west
  zone_id    = aws_route53_zone.spike.zone_id
  vpc_id     = module.eucentral.network.vpc_id
  vpc_region = "eu-central-1"
}
resource "aws_route53_record" "eucentral_cluster" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "eu-central-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.eucentral.inventory.nodes[0].private_ip]
}
resource "aws_route53_record" "eucentral_wildcard" {
  provider = aws.west
  zone_id  = aws_route53_zone.spike.zone_id
  name     = "*.eu-central-1.${aws_route53_zone.spike.name}"
  type     = "A"
  ttl      = 30
  records  = [module.eucentral.inventory.nodes[0].private_ip]
}
