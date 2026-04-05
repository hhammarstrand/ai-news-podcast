variable "prefix" {
  type = string
}

variable "ecs_cluster" {
  type = string
}

variable "ecs_task_def" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_groups" {
  type = list(string)
}

variable "tags" {
  type = map(string)
}

resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.prefix}-pipeline-api"
  description = "API Gateway for triggering AI News Podcast pipeline"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name = "${var.prefix}-pipeline-api"
  })
}

resource "aws_api_gateway_resource" "pipeline" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "trigger"
}

resource "aws_api_gateway_method" "pipeline_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.pipeline.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "pipeline_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.pipeline.id
  http_method             = aws_api_gateway_method.pipeline_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.pipeline_trigger.invoke_arn
}

resource "aws_api_gateway_integration" "pipeline_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pipeline.id
  http_method = "OPTIONS"

  type                    = "MOCK"
  passthrough_behavior    = "WHEN_NO_MATCH"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "pipeline_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pipeline.id
  http_method = "OPTIONS"
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "pipeline_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pipeline.id
  http_method = aws_api_gateway_integration.pipeline_options.http_method
  status_code = aws_api_gateway_method_response.pipeline_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.pipeline_options]
}

resource "aws_lambda_function" "pipeline_trigger" {
  function_name = "${var.prefix}-pipeline-trigger"
  description   = "Triggers the AI News Podcast pipeline ECS task"
  role         = aws_iam_role.lambda_exec.arn
  runtime      = "python3.12"
  handler      = "index.handler"

  filename         = "${path.module}/lambda_function.py.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_function.py.zip")

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_groups
  }

  environment {
    variables = {
      ECS_CLUSTER      = var.ecs_cluster
      ECS_TASK_DEF     = var.ecs_task_def
      SUBNET_IDS       = join(",", var.subnet_ids)
      SECURITY_GROUP_ID = var.security_groups[0]
    }
  }

  timeout     = 60
  memory_size = 256

  tags = merge(var.tags, {
    Name = "${var.prefix}-pipeline-trigger"
  })
}

resource "aws_iam_role" "lambda_exec" {
  name = "${var.prefix}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.prefix}-lambda-exec-role"
  })
}

resource "aws_iam_role_policy" "lambda_ecs" {
  name = "${var.prefix}-lambda-ecs"

  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline_trigger.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.prefix}-pipeline-trigger"
  retention_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.prefix}-lambda-logs"
  })
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/lambda_function.py.zip"
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.pipeline.id,
      aws_api_gateway_method.pipeline_post.id,
      aws_api_gateway_integration.pipeline_lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.pipeline_lambda,
    aws_api_gateway_integration.pipeline_options
  ]
}

resource "aws_api_gateway_stage" "production" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "production"

  tags = merge(var.tags, {
    Name = "${var.prefix}-api-stage"
  })
}

output "invoke_url" {
  value = "${aws_api_gateway_stage.production.invoke_url}/${aws_api_gateway_resource.pipeline.path_part}"
}