output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.main.arn
}

output "vpc_id" {
  description = "ID of the provisioned HIPAA VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of private isolated subnet IDs."
  value       = aws_subnet.private[*].id
}

output "ecs_cluster_name" {
  description = "Name of the ECS Fargate Cluster."
  value       = aws_ecs_cluster.main.name
}

output "kms_key_arn" {
  description = "ARN of the Customer Managed Key (CMK) used for encryption at rest."
  value       = aws_kms_key.main.arn
}

output "secrets_manager_secret_arn" {
  description = "ARN of the application secret in AWS Secrets Manager."
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "cloudtrail_arn" {
  description = "ARN of the multi-region HIPAA CloudTrail."
  value       = aws_cloudtrail.main.arn
}

output "guardduty_detector_id" {
  description = "ID of the AWS GuardDuty detector."
  value       = aws_guardduty_detector.main.id
}
