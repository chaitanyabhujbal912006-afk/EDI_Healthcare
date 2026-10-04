# EdiPro HIPAA-Compliant AWS Reference Deployment

This directory contains the production-grade Terraform infrastructure for deploying the **EdiPro Healthcare EDI Gateway** on AWS in full alignment with the **HIPAA Security Rule (45 CFR Part 160 and Part 164, Subparts A and C)**.

---

## Architecture Overview

```
                      INTERNET / ON-PREMISES CLIENTS
                                    │
                                    ▼
                         [ AWS WAFv2 Web ACL ]
                  (OWASP Top 10, Bad Inputs, Rate Limit)
                                    │
                                    ▼
               [ Application Load Balancer (Public Subnets) ]
                 - Port 80: HTTP -> HTTPS (301 Permanent Redirect)
                 - Port 443: TLS 1.2+ (ELBSecurityPolicy-TLS13-1-2-2021-06)
                 - ACM Certificate & Invalid Header Drop
                                    │
                         Security Group: Port 80
                                    ▼
              [ Frontend ECS Fargate Service (Private Subnets) ]
                 - Nginx Alpine Reverse Proxy & Static UI
                 - Zero Public IP
                                    │
                       Security Group: Port 8000
                                    ▼
              [ Backend ECS Fargate Service (Private Subnets) ]
                 - FastAPI EDI Engine (Strictly Internal Microservice)
                 - Cloud Map Service Discovery (backend.internal:8000)
                 - Zero Public IP (Air-gapped when ENABLE_EXTERNAL_LLM=false)
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                       ▼
[ VPC Interface Endpoints (Port 443) ]            [ Security & Audit Controls ]
  - ecr.api & ecr.dkr (Image Pulls)                 - AWS KMS Customer Managed Key
  - secretsmanager (Secrets Injection)              - CloudWatch Logs (6-Year Retention)
  - logs (Encrypted Telemetry)                      - CloudTrail (Multi-Region, Validated)
  - s3 Gateway (Image Blobs)                        - GuardDuty Threat Detection
```

---

## HIPAA Technical Safeguards Matrix

| HIPAA Specification | Standard | AWS Implementation in this Module |
|---|---|---|
| **§ 164.312(a)(1) Access Control** | Required | Isolated private subnets; strictly internal backend service without public ingress; least-privilege security groups; IAM execution roles with scoped permissions. |
| **§ 164.312(b) Audit Controls** | Required | Multi-region AWS CloudTrail with log validation; CloudWatch Log Groups with KMS CMK encryption and configurable 6-year retention (2,192 days) fulfilling § 164.316(b)(2)(i); GuardDuty continuous threat monitoring. |
| **§ 164.312(c)(1) Integrity** | Required | S3 versioning and TLS-only bucket policy; CloudTrail digest files; WAF managed rules preventing request tampering, SQLi, and path traversal. |
| **§ 164.312(d) Authentication** | Required | Automated HTTPS redirection; ACM TLS certificates; JWT signing keys and credentials stored in AWS Secrets Manager encrypted with KMS CMK. |
| **§ 164.312(e)(1) Transmission Security** | Required | TLS 1.2+ minimum cipher suites (`ELBSecurityPolicy-TLS13-1-2-2021-06`); private VPC interface endpoints for AWS APIs so containers require zero public internet egress. |

---

## Variable Reference

| Variable Name | Type | Default | Description |
|---|---|---|---|
| `aws_region` | `string` | `"us-east-1"` | AWS deployment region. |
| `environment` | `string` | `"prod"` | Target deployment environment name. |
| `vpc_cidr` | `string` | `"10.0.0.0/16"` | CIDR block for the dedicated HIPAA VPC. |
| `public_subnet_cidrs` | `list(string)` | `["10.0.1.0/24", "10.0.2.0/24"]` | CIDR blocks for public subnets (ALB & NAT). |
| `private_subnet_cidrs` | `list(string)` | `["10.0.10.0/24", "10.0.20.0/24"]` | CIDR blocks for isolated private subnets (ECS & VPC Endpoints). |
| `domain_name` | `string` | `"edipro.internal.example.com"` | Fully-qualified domain name for ACM certificate and ALB. |
| `enable_external_llm` | `bool` | `false` | When `false`, tasks have zero outbound internet routes. When `true`, provisions NAT Gateway for outbound LLM API access. |
| `log_retention_days` | `number` | `2192` | CloudWatch log retention in days (2192 days = 6 years for HIPAA § 164.316). |
| `backend_image` | `string` | `ghcr.io/.../backend:latest` | Container image URI for backend service. |
| `frontend_image` | `string` | `ghcr.io/.../frontend:latest` | Container image URI for frontend service. |
| `backend_cpu` | `number` | `512` | Fargate CPU allocation for backend task (512 = 0.5 vCPU). |
| `backend_memory` | `number` | `1024` | Fargate Memory allocation for backend task in MiB. |
| `backend_desired_count` | `number` | `2` | Desired number of backend container tasks. |
| `frontend_cpu` | `number` | `256` | Fargate CPU allocation for frontend task (256 = 0.25 vCPU). |
| `frontend_memory` | `number` | `512` | Fargate Memory allocation for frontend task in MiB. |
| `frontend_desired_count` | `number` | `2` | Desired number of frontend container tasks. |
| `waf_rate_limit` | `number` | `2000` | Max requests per IP within 5 minutes before WAF rate-limiting blocks. |

---

## Step-by-Step Apply Order

Follow these steps strictly in sequence:

### Step 0: Prerequisites & Authentication
Ensure you have authenticated with AWS credentials with sufficient permissions (IAM, VPC, ECS, KMS, SecretsManager, CloudTrail, GuardDuty, WAFv2):
```bash
aws sts get-caller-identity
```

### Step 1: Initialize Terraform
Download provider plugins and setup local lockfiles:
```bash
cd infra/aws
terraform init
```

### Step 2: Validate & Generate Execution Plan
Run validation and generate an execution plan file:
```bash
terraform validate
terraform plan -out=tfplan
```

### Step 3: Domain Validation (ACM Certificate)
If you manage the domain outside AWS Route 53, the ACM certificate validation CNAME records must be created in your DNS provider before the ALB listener can finish binding.
1. Target apply the certificate:
   ```bash
   terraform apply -target=aws_acm_certificate.main
   ```
2. Retrieve the DNS validation records:
   ```bash
   aws acm describe-certificate --certificate-arn <CERT_ARN> --query "Certificate.DomainValidationOptions"
   ```
3. Add the CNAME records in your DNS provider.

### Step 4: Apply Full Infrastructure
Once the certificate is validated, apply the plan:
```bash
terraform apply tfplan
```

### Step 5: Populate Production Secrets in AWS Secrets Manager
Update the placeholder keys in AWS Secrets Manager before processing production EDI:
```bash
aws secretsmanager put-secret-value \
  --secret-id $(terraform output -raw secrets_manager_secret_arn) \
  --secret-string '{"JWT_SECRET_KEY":"<GENERATE_RANDOM_64_CHAR_KEY>","GROQ_API_KEY":"","HUGGINGFACE_API_TOKEN":""}'
```

---

## ⚠️ CRITICAL DESTROY WARNING

Executing `terraform destroy` in this directory will tear down all deployed HIPAA safeguards and will cause:

1. **IRREVERSIBLE AUDIT LOG PURGE:**
   - The CloudWatch log groups containing PHI access logs and EDI validation audit trails will be permanently deleted unless exported to long-term immutable archives.
   - Deletion of audit logs less than 6 years old violates **HIPAA § 164.316(b)(2)(i)**.
2. **KMS KEY RETIREMENT & PENDING DELETION:**
   - The Customer Managed Key enters a 30-day waiting period. Any backups or snapshots encrypted with this key will become **permanently unrecoverable** once the key deletion executes.
3. **IMMEDIATE SERVICE DISRUPTION:**
   - Dismantling the ALB, WAF, and private subnets will terminate active clearinghouse connections, HL7/X12 ingestion pipelines, and patient claims processing.

> **Production Safeguard:** Before applying this in a production AWS account, add `prevent_destroy = true` lifecycle blocks to `aws_kms_key.main`, `aws_cloudtrail.main`, and `aws_s3_bucket.cloudtrail`.
