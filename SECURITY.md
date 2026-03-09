# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest on `main` | Yes |
| older releases | Best effort |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

### Preferred: GitHub Security Advisory

1. Navigate to the repository's **Security** tab.
2. Click **Report a vulnerability** under "Private vulnerability reporting".
3. Fill in the details including affected version, reproduction steps, and impact assessment.

### Alternative: Email

If private advisory reporting is unavailable, email the maintainer directly with:

- Affected version or commit SHA
- Reproduction steps or proof-of-concept
- Impact assessment (confidentiality, integrity, availability)
- Any suggested fix (optional)

## Response Timeline

- **Acknowledgement:** within 3 business days of receipt.
- **Triage and severity assessment:** within 7 business days.
- **Fix and coordinated disclosure:** target 30 days from acknowledgement, negotiable for complex issues.

## Security Measures

This project enforces the following security practices:

- **Dependency scanning:** Dependabot monitors pip and GitHub Actions dependencies weekly.
- **Static analysis:** Bandit (SAST) runs in CI and blocks merges on findings.
- **Dependency CVE checks:** Safety scans run in CI and block merges on known vulnerabilities.
- **Constant-time key comparison:** API key verification uses `hmac.compare_digest`.
- **No query-parameter credentials:** API keys are only accepted via the `X-API-Key` header.
- **No default passwords:** Docker Compose requires explicit `POSTGRES_PASSWORD` via environment.
- **Non-root containers:** Docker images run as a non-root user.

## Scope

The following are in scope for security reports:

- Any code in `src/toolkit_extensions/` and `dashboard/`
- Docker and deployment configurations
- CI/CD pipeline security (workflow injection, secret leakage)
- Dependency vulnerabilities in direct dependencies

The forked LiteLLM code in `src/` (outside `toolkit_extensions/`) should be reported upstream to the LiteLLM project.
