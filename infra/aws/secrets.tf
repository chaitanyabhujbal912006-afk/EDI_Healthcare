resource "aws_secretsmanager_secret" "app_secrets" {
  name_prefix             = "edipro-${var.environment}-app-"
  description             = "Application secrets (JWT key, credentials) encrypted with HIPAA KMS CMK"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = 30

  tags = {
    Name = "edipro-${var.environment}-app-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets_initial" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    JWT_SECRET_KEY        = "CHANGE_ME_IN_AWS_CONSOLE_OR_CLI_BEFORE_USE"
    GROQ_API_KEY          = ""
    HUGGINGFACE_API_TOKEN = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
