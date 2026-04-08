variable "prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "ecr_repository" {
  type = string
}

variable "pipeline_environment" {
  type = map(string)
}

variable "tags" {
  type = map(string)
}

resource "aws_ecs_cluster" "main" {
  name = "${var.prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${var.prefix}-cluster"
  })
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.prefix}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.prefix}-ecs-tasks-sg"
  })
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.prefix}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.prefix}-ecs-task-execution-role"
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets_manager" {
  name = "${var.prefix}-ecs-secrets-manager"

  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "*"
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "s3_publishing" {
  name = "${var.prefix}-ecs-s3-publishing"

  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Publishing"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.pipeline_environment["AWS_S3_BUCKET"]}",
          "arn:aws:s3:::${var.pipeline_environment["AWS_S3_BUCKET"]}/*"
        ]
      }
    ]
  })
}

resource "aws_ecs_task_definition" "pipeline" {
  family                   = "${var.prefix}-pipeline"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([
    {
      name      = "pipeline"
      image     = "${var.ecr_repository}:latest"
      essential = true

      environment = [
        for key, value in var.pipeline_environment : {
          name  = key
          value = value
        }
      ]

      logConfiguration = {
        logDriver = "cloudwatchlogs"
        options = {
          "awslogs-group"         = "/ecs/${var.prefix}-pipeline"
          "awslogs-region"        = "eu-north-1"
          "awslogs-stream-prefix" = "ecs"
        }
      }

      mountPoints = []
      volumesFrom = []
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.prefix}-pipeline-task"
  })
}

resource "aws_ecs_service" "pipeline_runner" {
  name            = "${var.prefix}-pipeline-runner"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.pipeline.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  deployment_controller {
    type = "ECS"
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = merge(var.tags, {
    Name = "${var.prefix}-pipeline-runner"
  })
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/ecs/${var.prefix}-pipeline"
  retention_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.prefix}-pipeline-logs"
  })
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "task_definition_family" {
  value = aws_ecs_task_definition.pipeline.family
}

output "security_group_id" {
  value = aws_security_group.ecs_tasks.id
}