# cloudfront.tf

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.project_prefix}-web"
  description                       = "OAC for the ${local.web_domain} static site"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${local.project_prefix} website"
  default_root_object = local.web_index
  price_class         = "PriceClass_100" # NA + EU; cheapest tier
  aliases             = [local.web_domain]

  origin {
    domain_name              = aws_s3_bucket.project.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.project.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id

    origin_path = "/${local.web_s3_prefix}"
  }

  default_cache_behavior {
    target_origin_id       = "s3-${aws_s3_bucket.project.id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS managed policies: CachingOptimized + no origin request forwarding.
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.web.id
  }

  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/${local.web_index}"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/${local.web_index}"
    error_caching_min_ttl = 60
  }

  viewer_certificate {
    acm_certificate_arn      = data.aws_acm_certificate.web.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = merge(local.project_tags, { Name = "${local.project_prefix}-web" })
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_response_headers_policy" "web" {
  name = "${local.project_prefix}-web-security-headers"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = false
      override                   = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
  }
}
