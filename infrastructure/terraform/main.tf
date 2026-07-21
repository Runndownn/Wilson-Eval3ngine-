# Wilson Eval3ngine - Production Infrastructure as Code
# T8.1.6 - Declarative infrastructure for all environments

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    postgresql = {
      source  = "cyrilgandon/postgresql"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket         = "we3-terraform-state"
    key            = "we3/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "we3-terraform-locks"
  }
}

locals {
  environment     = var.environment
  region          = var.region
  cluster_name    = "we3-${var.environment}"
  common_tags = {
    Project         = "wilson-eval3ngine"
    Environment     = var.environment
    ManagedBy       = "terraform"
    SecurityContext = "production-data-plane"
  }
}

# ============================================================================
# VPC and Networking
# ============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment == "staging"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.common_tags
}

# ============================================================================
# KMS Keys for Encryption
# ============================================================================

resource "aws_kms_key" "database_encryption" {
  description             = "WE3 database encryption key - ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "Enable IAM User Permissions"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "Allow Backup Role"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.backup.arn }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "database_encryption" {
  name          = "alias/we3-db-${var.environment}"
  target_key_id = aws_kms_key.database_encryption.key_id
}

resource "aws_kms_key" "object_encryption" {
  description             = "WE3 object store encryption key - ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "Allow WE3 Services"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.we3_service.arn }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

# ============================================================================
# PostgreSQL RDS Instance
# ============================================================================

resource "aws_db_subnet_group" "we3" {
  name       = "${local.cluster_name}-db-subnet"
  subnet_ids = module.vpc.private_subnets
  tags       = local.common_tags
}

resource "aws_security_group" "database" {
  name        = "${local.cluster_name}-db-sg"
  description = "Database access for WE3 services"
  vpc_id      = module.vpc.vpc_id
  tags        = local.common_tags

  ingress {
    description     = "WE3 API access"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "we3_primary" {
  identifier        = "${local.cluster_name}-db"
  engine            = "postgres"
  engine_version    = "16.3"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_encrypted = true
  kms_key_id        = aws_kms_key.database_encryption.arn

  db_name  = "we3"
  username = "we3_admin"

  # Use secrets manager for password
  password = random_password.db_password.result

  db_subnet_group_name = aws_db_subnet_group.we3.name
  vpc_security_group_ids = [aws_security_group.database.id]

  # Backup configuration
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"

  # PITR enabled via default WAL archiving
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.cluster_name}-final-snapshot"

  deletion_protection = var.environment == "production"

  tags = local.common_tags
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${local.cluster_name}/database-password"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = jsonencode({
    username = aws_db_instance.we3_primary.username
    password = random_password.db_password.result
    host     = aws_db_instance.we3_primary.endpoint
    port     = aws_db_instance.we3_primary.port
    dbname   = aws_db_instance.we3_primary.db_name
  })
}

# ============================================================================
# S3 Object Store
# ============================================================================

resource "aws_s3_bucket" "artifacts" {
  bucket = "we3-artifacts-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.object_encryption.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire_old_backups"
    status = "Enabled"

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ============================================================================
# IAM Roles
# ============================================================================

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "we3_service" {
  name = "${local.cluster_name}-service-role"
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
  tags = local.common_tags
}

resource "aws_iam_role" "backup" {
  name = "${local.cluster_name}-backup-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.common_tags
}

# ============================================================================
# ECS Cluster and Services
# ============================================================================

resource "aws_ecs_cluster" "we3" {
  name = local.cluster_name
  tags = local.common_tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.cluster_name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.we3_service.arn
  task_role_arn            = aws_iam_role.we3_service.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.api_image_digest
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "WE3_ENVIRONMENT", value = var.environment },
      { name = "WE3_DATABASE_URL", value = "postgresql+psycopg://${aws_db_instance.we3_primary.username}:${random_password.db_password.result}@${aws_db_instance.we3_primary.endpoint}/${aws_db_instance.we3_primary.db_name}" },
      { name = "WE3_ARTIFACT_ROOT", value = "s3://${aws_s3_bucket.artifacts.id}" },
    ]

    secrets = [
      {
        name      = "WE3_SIGNING_KEY"
        valueFrom = aws_secretsmanager_secret.api_signing_key.arn
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/we3/${var.environment}/api"
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${local.cluster_name}-api"
  cluster         = aws_ecs_cluster.we3.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.api.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_controller {
    type = "CODE_DEPLOY"
  }

  tags = local.common_tags
}

# ============================================================================
# Application Load Balancer
# ============================================================================

resource "aws_lb" "api" {
  name               = "${local.cluster_name}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.api.id]
  subnets            = module.vpc.public_subnets
  tags               = local.common_tags
}

resource "aws_lb_target_group" "api" {
  name        = "${local.cluster_name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"
  tags        = local.common_tags
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "api_https" {
  load_balancer_arn = aws_lb.api.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.api.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ============================================================================
# CloudWatch Monitoring
# ============================================================================

resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${local.cluster_name}-database-high-cpu"
  alarm_description   = "Database CPU utilization is high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.we3_primary.id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.common_tags
}

resource "aws_sns_topic" "alerts" {
  name = "${local.cluster_name}-alerts"
  tags = local.common_tags
}

# ============================================================================
# Variables
# ============================================================================

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Must be production, staging, or development."
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 100
}

variable "api_image_digest" {
  description = "Container image digest for API service (immutable reference)"
  type        = string
}

variable "api_desired_count" {
  description = "Desired count for API service"
  type        = number
  default     = 2
}

# ============================================================================
# Outputs
# ============================================================================

output "database_endpoint" {
  value = aws_db_instance.we3_primary.endpoint
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "api_url" {
  value = aws_lb_listener.api_https.endpoint
}