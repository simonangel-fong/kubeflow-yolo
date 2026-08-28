# web-upload.tf
# Uploads web/ into the bucket's web/ prefix. Terraform owns the objects so a
# removed source file is removed from the bucket too.

locals {
  web_files = fileset(local.web_source_dir, "**")

  # S3 has no content-type sniffing; a wrong type makes browsers refuse the file.
  web_content_types = {
    html  = "text/html; charset=utf-8"
    css   = "text/css; charset=utf-8"
    js    = "text/javascript; charset=utf-8"
    json  = "application/json"
    svg   = "image/svg+xml"
    png   = "image/png"
    jpg   = "image/jpeg"
    jpeg  = "image/jpeg"
    gif   = "image/gif"
    webp  = "image/webp"
    ico   = "image/x-icon"
    txt   = "text/plain; charset=utf-8"
    woff  = "font/woff"
    woff2 = "font/woff2"
  }
}

resource "aws_s3_object" "web" {
  for_each = local.web_files

  bucket = aws_s3_bucket.project.id
  key    = "${local.web_s3_prefix}/${each.value}"
  source = "${local.web_source_dir}/${each.value}"

  # Re-uploads only when the file content actually changes.
  etag = filemd5("${local.web_source_dir}/${each.value}")

  content_type = lookup(
    local.web_content_types,
    lower(reverse(split(".", each.value))[0]),
    "application/octet-stream",
  )

  # The CDN, not the browser, holds the cache; invalidation on deploy is what
  # makes a change visible, so keep the browser TTL short.
  cache_control = "public, max-age=300, must-revalidate"

  tags = local.project_tags
}
