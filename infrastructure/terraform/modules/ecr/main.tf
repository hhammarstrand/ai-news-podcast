variable "prefix" {
  type = string
}

variable "repository" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "aws_ecr_repository" "main" {
  name = "${var.prefix}/${var.repository}"

  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.prefix}-${var.repository}"
  })
}

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only last 10 images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["v"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

output "repository_url" {
  value = aws_ecr_repository.main.repository_url
}

output "repository_name" {
  value = aws_ecr_repository.main.name
}