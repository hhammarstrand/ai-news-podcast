variable "prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "aws_s3_bucket" "main" {
  bucket = "${var.prefix}-${data.aws_caller_identity.current.account_id}"

  tags = merge(var.tags, {
    Name = "${var.prefix}-audio-storage"
  })
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy    = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "audio-retention"
    status = "Enabled"

    filter {
      prefix = "episodes/"
    }

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = 7
      storage_class  = "GLACIER"
    }
  }
}

data "aws_caller_identity" "current" {}

output "bucket_name" {
  value = aws_s3_bucket.main.id
}