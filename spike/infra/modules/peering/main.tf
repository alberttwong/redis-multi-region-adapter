terraform {
  required_providers {
    aws = { source = "hashicorp/aws", configuration_aliases = [aws.requester, aws.accepter] }
  }
}
variable "name" { type = string }
variable "requester" { type = object({ vpc_id = string, cidr = string, route_table_id = string, region = string }) }
variable "accepter" { type = object({ vpc_id = string, cidr = string, route_table_id = string, region = string }) }
resource "aws_vpc_peering_connection" "link" {
  provider    = aws.requester
  vpc_id      = var.requester.vpc_id
  peer_vpc_id = var.accepter.vpc_id
  peer_region = var.accepter.region
  auto_accept = false
  tags        = { Name = "${var.name}-${var.requester.region}-${var.accepter.region}" }
}
resource "aws_vpc_peering_connection_accepter" "link" {
  provider                  = aws.accepter
  vpc_peering_connection_id = aws_vpc_peering_connection.link.id
  auto_accept               = true
}
resource "aws_route" "requester" {
  provider                  = aws.requester
  route_table_id            = var.requester.route_table_id
  destination_cidr_block    = var.accepter.cidr
  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.link.id
}
resource "aws_route" "accepter" {
  provider                  = aws.accepter
  route_table_id            = var.accepter.route_table_id
  destination_cidr_block    = var.requester.cidr
  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.link.id
}
