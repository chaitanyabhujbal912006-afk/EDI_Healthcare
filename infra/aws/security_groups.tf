# -----------------------------------------------------------------------------
# Security Groups (Base definitions)
# -----------------------------------------------------------------------------
resource "aws_security_group" "alb" {
  name        = "edipro-${var.environment}-alb-sg"
  description = "Security group for external ALB - inbound HTTPS and HTTP redirect"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "edipro-${var.environment}-alb-sg"
  }
}

resource "aws_security_group" "frontend" {
  name        = "edipro-${var.environment}-frontend-sg"
  description = "Security group for frontend Nginx containers"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "edipro-${var.environment}-frontend-sg"
  }
}

resource "aws_security_group" "backend" {
  name        = "edipro-${var.environment}-backend-sg"
  description = "Security group for backend FastAPI containers - strictly internal"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "edipro-${var.environment}-backend-sg"
  }
}

resource "aws_security_group" "vpc_endpoints" {
  name        = "edipro-${var.environment}-vpce-sg"
  description = "Security group for VPC Interface Endpoints (ECR, Secrets, CloudWatch Logs)"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "edipro-${var.environment}-vpce-sg"
  }
}

# -----------------------------------------------------------------------------
# ALB Rules
# -----------------------------------------------------------------------------
resource "aws_security_group_rule" "alb_ingress_http" {
  type              = "ingress"
  description       = "Inbound HTTP for 301 redirect to HTTPS"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "alb_ingress_https" {
  type              = "ingress"
  description       = "Inbound HTTPS from Internet"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "alb_egress_frontend" {
  type                     = "egress"
  description              = "Forward traffic to Frontend ECS tasks on port 80"
  from_port                = 80
  to_port                  = 80
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.frontend.id
  security_group_id        = aws_security_group.alb.id
}

# -----------------------------------------------------------------------------
# Frontend Rules
# -----------------------------------------------------------------------------
resource "aws_security_group_rule" "frontend_ingress_alb" {
  type                     = "ingress"
  description              = "Allow HTTP from ALB only"
  from_port                = 80
  to_port                  = 80
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.frontend.id
}

resource "aws_security_group_rule" "frontend_egress_backend" {
  type                     = "egress"
  description              = "Allow traffic to Backend ECS tasks on port 8000"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.backend.id
  security_group_id        = aws_security_group.frontend.id
}

resource "aws_security_group_rule" "frontend_egress_vpce" {
  type                     = "egress"
  description              = "Allow HTTPS to VPC Interface Endpoints"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.vpc_endpoints.id
  security_group_id        = aws_security_group.frontend.id
}

# -----------------------------------------------------------------------------
# Backend Rules (Internal Only)
# -----------------------------------------------------------------------------
resource "aws_security_group_rule" "backend_ingress_frontend" {
  type                     = "ingress"
  description              = "Allow API calls from Frontend containers only"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.frontend.id
  security_group_id        = aws_security_group.backend.id
}

resource "aws_security_group_rule" "backend_egress_vpce" {
  type                     = "egress"
  description              = "Allow HTTPS to VPC Interface Endpoints"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.vpc_endpoints.id
  security_group_id        = aws_security_group.backend.id
}

resource "aws_security_group_rule" "backend_egress_external_llm" {
  count             = var.enable_external_llm ? 1 : 0
  type              = "egress"
  description       = "Outbound HTTPS to external LLM providers (when enabled)"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.backend.id
}

# -----------------------------------------------------------------------------
# VPC Interface Endpoints Rules
# -----------------------------------------------------------------------------
resource "aws_security_group_rule" "vpce_ingress_frontend" {
  type                     = "ingress"
  description              = "Allow HTTPS from Frontend containers"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.frontend.id
  security_group_id        = aws_security_group.vpc_endpoints.id
}

resource "aws_security_group_rule" "vpce_ingress_backend" {
  type                     = "ingress"
  description              = "Allow HTTPS from Backend containers"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.backend.id
  security_group_id        = aws_security_group.vpc_endpoints.id
}
