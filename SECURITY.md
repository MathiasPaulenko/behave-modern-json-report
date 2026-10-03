# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.5.x   | :white_check_mark: |
| 1.2.x   | :white_check_mark: |
| < 1.2   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue
in `behave-modern-json-report`, please report it responsibly.

### How to Report

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email **security@mathiaspaulenko.com** with:

1. A description of the vulnerability
2. Steps to reproduce or a proof of concept
3. The affected version(s)
4. The potential impact

You will receive an acknowledgment within **48 hours**. We will work with you
to assess the issue and coordinate a fix and disclosure timeline.

### Disclosure Policy

- We follow **coordinated disclosure**.
- A fix will be developed and released as soon as possible.
- A GitHub Security Advisory will be published after the fix is released.
- Credit will be given to the reporter (unless they prefer to remain anonymous).

## Security Measures

This project follows these security practices:

- **No hardcoded secrets** — API keys, tokens, and credentials must never be
  committed. The repository includes secret scanning via GitHub.
- **Dependency scanning** — We monitor dependencies for known vulnerabilities.
- **Input validation** — All external inputs (Behave events, config values)
  are validated before use.
- **Safe deserialization** — JSON parsing uses safe defaults; no `eval` or
  arbitrary code execution.
- **Minimal permissions** — The formatter only writes to the configured output
  stream; no network calls, no filesystem access beyond the output file.

## Scope

This security policy covers the `behave-modern-json-report` Python package and
its formatters (`ModernJSONFormatter`, `CucumberJSONFormatter`).

Out of scope:

- Vulnerabilities in Behave itself (report to the
  [Behave project](https://github.com/behave/behave))
- Vulnerabilities in third-party tools that consume the JSON output
- Issues that require physical access to the machine running the tests
