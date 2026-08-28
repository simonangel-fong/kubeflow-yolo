# cloudflare.tf

resource "cloudflare_dns_record" "web" {
  zone_id = var.cloudflare_zone_id
  name    = local.web_domain
  type    = "CNAME"
  content = aws_cloudfront_distribution.web.domain_name
  ttl     = 300
  proxied = false
  comment = "${local.project_prefix} website -> CloudFront"
}
