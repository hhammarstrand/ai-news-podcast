# Deployment Runbook — AI News Podcast Pipeline

## Overview

This runbook guides the Backend Engineer through deploying the AI News Podcast infrastructure on AWS using Terraform.

## Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.5.0 installed
- Access to the AWS account (eu-north-1 region)
- GitHub Personal Access Token with repo access

## Step 1: Clone the Repository

```bash
git clone https://github.com/hhammarstrand/ai-news-podcast.git
cd ai-news-podcast/infrastructure/terraform
```

## Step 2: Configure Terraform Variables

Create a `terraform.tfvars` file with your credentials:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with actual values:

```hcl
anthropic_api_key    = "sk-ant-..."
elevenlabs_api_key   = "..."
database_url         = "postgresql://user:pass@host:5432/podcast"
news_api_key         = "..."
minimax_api_key      = "..."
minimax_group_id     = "..."
```

## Step 3: Initialize Terraform

```bash
terraform init
```

## Step 4: Plan and Apply

```bash
# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

Type `yes` when prompted.

## Step 5: Verify Infrastructure

After apply completes, verify the resources:

```bash
# Check S3 bucket
aws s3 ls | grep ai-news-podcast

# Check ECS cluster
aws ecs list-clusters | grep ai-news-podcast

# Check ECR repository
aws ecr describe-repositories --repository-names ai-news-podcast
```

## Step 6: Build and Push Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-north-1.amazonaws.com

# Build image
cd ../../pipeline
docker build -t ai-news-podcast:latest .

# Tag and push
docker tag ai-news-podcast:latest <account-id>.dkr.ecr.eu-north-1.amazonaws.com/ai-news-podcast:latest
docker push <account-id>.dkr.ecr.eu-north-1.amazonaws.com/ai-news-podcast:latest
```

## Step 7: Configure GitHub Secrets (Optional for CI/CD)

If setting up GitHub Actions:

1. Go to GitHub repo → Settings → Secrets
2. Add these secrets:
   - `ANTHROPIC_API_KEY`
   - `MINIMAX_API_KEY`
   - `MINIMAX_GROUP_ID`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `ECS_CLUSTER` (from terraform output)
   - `ECS_TASK_DEF` (from terraform output)
   - `ECS_SUBNET` (subnet IDs)
   - `ECS_SG` (security group ID)

## Step 8: Test the Pipeline

```bash
# Run locally first to verify credentials work
cd ../../pipeline
cp .env.example .env
# Edit .env with real credentials
python -m src.main
```

## Step 9: Set Up Scheduled Execution

### Option A: AWS EventBridge (Recommended)
Create a scheduled rule to trigger the pipeline daily:

```bash
aws events put-rule \
  --name ai-news-podcast-daily \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED

aws events put-targets \
  --rule ai-news-podcast-daily \
  --targets "Id"="1","Arn"="<api-gateway-arn>","RoleArn"="<execution-role-arn>"
```

### Option B: Paperclip Routine
The Paperclip routine is already set up to fire daily at 06:00 SE. Once API Gateway is deployed, add a webhook trigger.

## Infrastructure Outputs

After `terraform apply`, note these outputs:
- `ecr_repository_url` — ECR image repository
- `ecs_cluster_name` — ECS cluster name
- `api_gateway_endpoint` — API Gateway invoke URL
- `s3_bucket_name` — S3 bucket for audio storage
- `vpc_id` — VPC ID
- `private_subnet_ids` — Private subnet IDs

## Troubleshooting

### ECS Task Won't Start
Check CloudWatch logs:
```bash
aws logs tail /ecs/ai-news-podcast-pipeline --follow
```

### Lambda Not Triggering
Check API Gateway metrics in CloudWatch.

### S3 Bucket Access Denied
Verify bucket policy allows public read on `feed.xml` and `episodes/*`.

## Architecture

```
Paperclip Routine (daily 06:00 SE)
  → Webhook trigger (when configured)
    → API Gateway
      → Lambda
        → ECS Fargate (pipeline)
          → News Ingestion (RSS feeds)
          → Editorial AI (Claude)
          → TTS (MiniMax)
          → Audio Assembly (ffmpeg)
            → S3 (audio files + RSS feed)
              → Distribution (Spotify, Apple Podcasts)
```

## Contact

For questions, @mention the CTO agent in Paperclip.