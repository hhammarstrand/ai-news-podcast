terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "ai-news-podcast-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "eu-north-1"
  }
}

provider "aws" {
  region = "eu-north-1"
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = "eu-north-1"
  prefix     = "ai-news-podcast"

  tags = {
    Project     = "AI News Podcast"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

module "vpc" {
  source = "./modules/vpc"

  prefix = local.prefix
  tags   = local.tags
}

module "ecr" {
  source = "./modules/ecr"

  prefix     = local.prefix
  repository = "ai-news-podcast"
  tags       = local.tags
}

module "ecs" {
  source = "./modules/ecs"

  prefix           = local.prefix
  vpc_id           = module.vpc.vpc_id
  subnet_ids       = module.vpc.private_subnet_ids
  ecr_repository   = module.ecr.repository_url
  tags             = local.tags

  pipeline_environment = {
    ANTHROPIC_API_KEY    = var.anthropic_api_key
    ELEVENLABS_API_KEY   = var.elevenlabs_api_key
    AWS_S3_BUCKET        = module.s3.bucket_name
    DATABASE_URL         = var.database_url
    NEWS_API_KEY         = var.news_api_key
    PIPELINE_OUTPUT_DIR  = "/tmp/podcast_output"
  }
}

module "s3" {
  source = "./modules/s3"

  prefix = local.prefix
  tags   = local.tags
}

module "api_gateway" {
  source = "./modules/api-gateway"

  prefix       = local.prefix
  ecs_cluster  = module.ecs.cluster_name
  ecs_task_def = module.ecs.task_definition_family
  subnet_ids   = module.vpc.private_subnet_ids
  security_groups = [module.ecs.security_group_id]
  tags         = local.tags
}

variable "anthropic_api_key" {
  description = "Anthropic Claude API key"
  sensitive   = true
}

variable "elevenlabs_api_key" {
  description = "ElevenLabs API key"
  sensitive   = true
}

variable "database_url" {
  description = "PostgreSQL database connection string"
  sensitive   = true
}

variable "news_api_key" {
  description = "NewsAPI.org API key"
  sensitive   = true
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "api_gateway_endpoint" {
  value = module.api_gateway.invoke_url
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}