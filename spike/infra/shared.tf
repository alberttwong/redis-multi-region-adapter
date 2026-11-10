resource "aws_s3_bucket" "artifacts" {
  provider      = aws.west
  bucket        = "${var.deployment_name}-${var.expected_account_id}"
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "artifacts" {
  provider                = aws.west
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  provider = aws.west
  bucket   = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  provider = aws.west
  bucket   = aws_s3_bucket.artifacts.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_iam_role" "instance" {
  provider = aws.west
  for_each = toset(["redis", "runner"])
  name     = "${var.deployment_name}-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  provider   = aws.west
  for_each   = aws_iam_role.instance
  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "spike" {
  provider = aws.west
  for_each = aws_iam_role.instance
  role     = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = each.key == "redis" ? [var.license_secret_arn, var.admin_secret_arn, var.database_secret_arn] : [var.database_secret_arn] },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.artifacts.arn}/code/*", "${aws_s3_bucket.artifacts.arn}/config/*"] },
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = ["${aws_s3_bucket.artifacts.arn}/results/*"] }
  ] })
}
resource "aws_iam_instance_profile" "spike" {
  provider = aws.west
  for_each = aws_iam_role.instance
  name     = "${var.deployment_name}-${each.key}"
  role     = each.value.name
}
