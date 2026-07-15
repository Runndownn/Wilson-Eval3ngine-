# Security Policy

## Foundation status

Version 0.1.0 is a development and internal-testing foundation. Do not connect
it to production model credentials, real harmful corpora, personal data, or
release-gating workflows.

## Security invariants

- Raw model content is untrusted.
- Reliability errors are not behavioral labels.
- Development header authentication is prohibited in production mode.
- The local artifact adapter is not a production immutability control.
- Graders must not receive provider credentials or live tools.
- Certification must not use target-response caching.
- A composite score may not override a raw safety gate.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner or the
organization's approved security intake. Include the affected version, a
minimal reproduction using synthetic data, impact, and suggested containment.
Do not include real secrets or harmful evidence in issue trackers.
