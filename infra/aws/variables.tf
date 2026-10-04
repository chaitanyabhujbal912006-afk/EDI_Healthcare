variable "aws_region" {
  description = "AWS deployment region."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Target deployment environment (e.g. prod, staging)."
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated HIPAA VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB and optional NAT)."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for isolated private subnets (ECS tasks & VPC endpoints)."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "domain_name" {
  description = "Fully-qualified domain name for the Application Load Balancer and ACM TLS certificate."
  type        = string
  default     = "edipro.internal.example.com"
}

variable "enable_external_llm" {
  description = "Whether to provision NAT Gateways for outbound Internet egress to third-party LLM APIs (e.g. Groq/HuggingFace). When false, tasks remain strictly air-gapped without public egress."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Retention period in days for CloudWatch log groups. Configured by default to 2192 days (6 years) to satisfy HIPAA § 164.316(b)(2)(i)."
  type        = number
  default     = 2192
}

variable "backend_image" {
  description = "Container image URI for the FastAPI backend service."
  type        = string
  default     = "ghcr.io/chaitanyabhujbal912006-afk/edi_healthcare/backend:latest"
}

variable "frontend_image" {
  description = "Container image URI for the Nginx frontend service."
  type        = string
  default     = "ghcr.io/chaitanyabhujbal912006-afk/edi_healthcare/frontend:latest"
}

variable "backend_cpu" {
  description = "CPU units allocated to backend Fargate task (256, 512, 1024, etc.)."
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory (in MiB) allocated to backend Fargate task (512, 1024, 2048, etc.)."
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Desired number of running backend container instances."
  type        = number
  default     = 2
}

variable "frontend_cpu" {
  description = "CPU units allocated to frontend Fargate task."
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Memory (in MiB) allocated to frontend Fargate task."
  type        = number
  default     = 512
}

variable "frontend_desired_count" {
  description = "Desired number of running frontend container instances."
  type        = number
  default     = 2
}

variable "waf_rate_limit" {
  description = "Maximum requests allowed per IP address within a 5-minute rolling window by AWS WAF."
  type        = number
  default     = 2000
}
