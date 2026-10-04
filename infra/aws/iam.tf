# ECS Task Execution Role (used by ECS agent to pull images, stream logs, and inject secrets)
resource "aws_iam_role" "ecs_execution" {
  name = "edipro-${var.environment}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "edipro-${var.environment}-ecs-execution-role"
  }
}

# Attach standard AWS managed execution policy
resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Grant least-privilege access to Secrets Manager and KMS decryption for secret injection
resource "aws_iam_policy" "ecs_secrets_kms" {
  name        = "edipro-${var.environment}-ecs-secrets-kms-policy"
  description = "Allows ECS execution agent to fetch task secrets and decrypt them with KMS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetAppSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.app_secrets.arn
        ]
      },
      {
        Sid    = "DecryptKMSSecret"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [
          aws_kms_key.main.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_secrets_kms.arn
}

# ECS Task Role (used by application containers at runtime - least privilege)
resource "aws_iam_role" "ecs_task" {
  name = "edipro-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "edipro-${var.environment}-ecs-task-role"
  }
}
