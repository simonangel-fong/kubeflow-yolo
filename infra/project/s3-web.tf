# s3-web.tf

data "aws_iam_policy_document" "project_bucket" {
  statement {
    sid    = "AllowCloudFrontReadWebPrefix"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.project.arn}/${local.web_s3_prefix}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.web.arn]
    }
  }

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.project.arn,
      "${aws_s3_bucket.project.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "project" {
  bucket = aws_s3_bucket.project.id
  policy = data.aws_iam_policy_document.project_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.project]
}
