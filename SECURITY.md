# Security Policy

## Supported versions

Only the `main` branch receives security updates. Pinned releases are
not supported.

## Reporting a vulnerability

Please **do not** open a public issue for suspected security problems.

Report privately via GitHub Security Advisories:
https://github.com/ajvelo/forgestack/security/advisories/new

Include:
- A description of the issue and its impact
- Steps to reproduce
- The affected version or commit SHA

You'll receive an initial response within a few days. Once confirmed, a
fix is developed privately and a coordinated disclosure is published.

## Scope

ForgeStack is a CLI that calls the Anthropic API with user-provided
prompts. Secrets (API keys) are sourced from environment variables only;
do not commit them. Out-of-scope: issues arising from running ForgeStack
against a repository whose contents the user didn't intend to expose.
