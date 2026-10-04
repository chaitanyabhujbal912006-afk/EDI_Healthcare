# Security Policy

ValidEDI and EdiPro Gateway take security and the protection of Protected Health Information (PHI) seriously. We appreciate the efforts of security researchers and engineers who discover and report vulnerabilities responsibly.

---

## Supported Versions

Only the latest active minor release receives security updates and patches:

| Version | Supported          | Security Fixes |
| ------- | ------------------ | -------------- |
| 1.0.x (Gateway) / 0.4.x (Core) | :white_check_mark: | Full active support |
| < 0.4.0 | :x:                | Unsupported (End-of-life) |

---

## Reporting a Vulnerability

**Please do NOT disclose vulnerabilities publicly in GitHub Issues or Discussions.**

### Preferred Method: GitHub Private Vulnerability Reporting
1. Navigate to the repository's **Security** tab.
2. Select **Advisories** and click **Report a vulnerability**.
3. Fill out the report details and submit.

### Alternative Method: Direct Security Contact
If GitHub Private Reporting is unavailable, email vulnerability details directly to:
- **Email:** security@example.com
- **Subject:** `[SECURITY VULNERABILITY] <Brief Description>`

### What to Include in Your Report
To help us triage and resolve the issue quickly, please provide:
1. **Type of Vulnerability:** (e.g., PHI leakage, authentication bypass, denial of service, memory exhaustion, arbitrary code execution, supply chain risk).
2. **Affected Component & Version:** (e.g., `src/validedi/engine`, `src/backend/app/main.py`, `v0.4.0`).
3. **Step-by-step Reproduction:** Clear instructions, minimal reproducible synthetic EDI sample (do NOT include real PHI/PII), or proof-of-concept script.
4. **Impact Assessment:** Real-world impact on HIPAA compliance, service availability, or data integrity.
5. **Proposed Mitigation:** Any suggested fixes or workarounds.

---

## Response & Disclosure Process

- **Acknowledgement:** Within 48 hours of initial report submission.
- **Triage & Assessment:** Within 5 business days, confirming severity and validity.
- **Remediation & Patching:** High and critical severity issues receive priority patching within 14 calendar days.
- **Coordinated Disclosure:** We adhere to responsible, coordinated disclosure. Fixes will be published alongside a GitHub Security Advisory (GHSA) and CVE if applicable.

---

## Safe Harbor

We consider security research conducted under this policy to be authorized. If you:
- Make a good faith effort to avoid privacy violations (specifically HIPAA/PHI exposure), data destruction, and service interruption;
- Give us reasonable time to resolve the issue before sharing details publicly;
- Do not exploit identified vulnerabilities beyond proof of concept;

We will not pursue legal action against you regarding your research.
