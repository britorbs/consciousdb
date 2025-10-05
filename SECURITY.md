# Security Policy

## Supported Versions
Until 1.0.0, only the latest minor release is supported for security fixes.

| Version | Supported |
|---------|-----------|
| < 0.1.0 | No        |
| 0.1.x   | Yes       |

## Reporting a Vulnerability
Please create a private security advisory or email the maintainers (contact to be added). Do **not** open a public issue for sensitive vulnerabilities.

Include:
- Affected versions / commit SHA
- Reproduction steps or PoC
- Impact assessment (confidentiality / integrity / availability)

You will receive an acknowledgment within 3 business days. We aim to issue a fix & coordinated disclosure within 30 days depending on severity.

## Security Posture
- No raw corpus storage; only vector IDs & energy-derived metadata retained.
- Audit logging supports optional HMAC signing.
- API key auth supported; future roadmap includes rate limiting & secret rotation guidance.

## Preferred Languages
English.

Thank you for helping keep the ecosystem safe.
