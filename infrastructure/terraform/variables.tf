# Wilson Eval3ngine - Terraform Variables
# T8.1.6 - Infrastructure variables for all environments

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

# KMS key variables
variable "database_kms_key_alias" {
  description = "Alias for database KMS key"
  type        = string
  default     = "alias/we3-db"
}

variable "object_kms_key_alias" {
  description = "Alias for object store KMS key"
  type        = string
  default     = "alias/we3-object"
}