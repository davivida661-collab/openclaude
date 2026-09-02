# Security Policy

## Supported Versions

OpenClaude is currently maintained on the latest `main` branch and the latest
npm release only.

| Version | Supported |
| ------- | --------- |
| Latest release | :white_check_mark: |
| Older releases | :x: |
| Unreleased forks / modified builds | :x: |

Security fixes are generally released in the next patch version and may also be
landed directly on `main` before a package release is published.

## Reporting a Vulnerability

If you believe you have found a security vulnerability in OpenClaude, please
report it privately.

Preferred reporting channel:

- GitHub Security Advisories / private vulnerability reporting for this
  repository

Please include:

- a clear description of the issue
- affected version, commit, or environment
- reproduction steps or a proof of concept
- impact assessment
- any suggested remediation, if available

Please do **not** open a public issue for an unpatched vulnerability.

## Response Process

Our general goals are:

- initial triage acknowledgment within 7 days
- follow-up after validation when we can reproduce the issue
- coordinated disclosure after a fix is available

Severity, exploitability, and maintenance bandwidth may affect timelines.

## Disclosure and CVEs

Valid reports may be fixed privately first and disclosed after a patch is
available.

If a report is accepted and the issue is significant enough to warrant formal
tracking, we may publish a GitHub Security Advisory and request or assign a CVE
through the appropriate channel. CVE issuance is not guaranteed for every
report.

## Scope

This policy applies to:

- the OpenClaude source code in this repository
- official release artifacts published from this repository
- the `@gitlawb/openclaude` npm package

This policy does not cover:

- third-party model providers, endpoints, or hosted services
- local misconfiguration on the reporter's machine
- vulnerabilities in unofficial forks, mirrors, or downstream repackages

## Security Considerations for Android/Termux Users

Users running OpenClaude in a Termux + proot environment should be aware of
additional security considerations:

### API Key Storage

- Store API keys in a dedicated file with restricted permissions (`chmod 600`),
  not in shell profiles like `~/.bashrc` where other processes can read them.
- Never commit API keys to a Git repository, even in private repos.
- Rotate keys periodically, especially if you suspect they may have been
  exposed.

### proot Isolation Limitations

- proot provides **filesystem isolation only**, not full container isolation.
  Processes share the Android kernel with all other apps on the device.
- Do not treat the proot environment as a security boundary for protecting
  sensitive data or API keys beyond basic filesystem access control.
- Be aware that proot processes can see the Termux home directory
  (`/data/data/com.termux/files/home/`). Sensitive files outside the proot
  root may be accessible.

### Network Security

- All official OpenClaude providers use HTTPS. If you configure a custom
  endpoint, ensure it uses HTTPS to protect your API key in transit.
- Be cautious with proxy configurations that may downgrade HTTPS to HTTP.

### Keeping Updated

- Regularly update OpenClaude (`git pull && bun run build`) to receive
  security patches.
- Keep Termux and its packages updated (`pkg update && pkg upgrade`) to
  ensure you have the latest security fixes for the runtime environment.
- Update Bun regularly inside proot to benefit from upstream security
  improvements.
