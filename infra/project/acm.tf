# acm.tf

data "aws_acm_certificate" "web" {
  provider = aws.us_east_1

  domain      = local.web_cert_domain
  statuses    = ["ISSUED"]
  most_recent = true
}
