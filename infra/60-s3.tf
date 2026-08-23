# s3.tf
#
# Bucket layout:
#
#   dvcstore/                              DVC content-addressed store
#     files/md5/<2>/<rest>                 every object, keyed by content hash
#
#   pipeline/                              written by kubeflow/pipelines
#     processed/                           train/val split + data.yaml
#     runs/<run-id>/                       one directory per pipeline run
#       train/best.pt                      trained weights
#       eval/metrics.json                  mAP50 and the run id
#       serve/                             registered storage_uri
#         model.onnx                       the served graph
#         metadata.json                    imgsz, class names, opset
#
# Objects under pipeline/ are reproducible: a run can be repeated from the
# dataset version in dvcstore/, so only dvcstore/ is irreplaceable.


# ##############################
# S3 bucket
# ##############################
resource "aws_s3_bucket" "project" {
  bucket = local.s3_bucket_name

  tags = local.project_tags
}

# prefixes keys
resource "aws_s3_object" "prefixes" {
  for_each = toset(local.s3_bucket_prefix)

  bucket = aws_s3_bucket.project.id
  key    = each.value
}

# Block all public access; 
resource "aws_s3_bucket_public_access_block" "project" {
  bucket = aws_s3_bucket.project.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "project" {
  bucket = aws_s3_bucket.project.id

  rule {
    object_ownership = "BucketOwnerEnforced" # disable ACLs
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "project" {
  bucket = aws_s3_bucket.project.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "project" {
  bucket = aws_s3_bucket.project.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "project" {
  bucket = aws_s3_bucket.project.id

  # Ordering: the lifecycle rule targets versions, so versioning must exist first.
  depends_on = [aws_s3_bucket_versioning.project]

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
