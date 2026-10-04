resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/edipro-${var.environment}-backend"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn

  tags = {
    Name = "edipro-${var.environment}-backend-logs"
  }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/edipro-${var.environment}-frontend"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn

  tags = {
    Name = "edipro-${var.environment}-frontend-logs"
  }
}

# AWS WAF logging group (AWS requires name to start with 'aws-waf-logs-')
resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-edipro-${var.environment}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn

  tags = {
    Name = "edipro-${var.environment}-waf-logs"
  }
}
