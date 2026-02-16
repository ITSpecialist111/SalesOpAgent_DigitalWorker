# Public Anonymization Guide

This repository keeps **real testing values locally** and publishes **anonymized values publicly**.

## Scope

Apply anonymization to any public-facing content, especially:
- `README.md`, `HANDOVER.md`, `SETUP.md`
- `docs/*`
- `deployment.yaml`, `a365.config.json`
- sample defaults in code (emails, endpoints, tenant IDs)

## Placeholder Conventions

Use these placeholders consistently:
- Tenant IDs: `<m365-tenant-id>`, `<azure-tenant-id>`
- Subscription: `<subscription-id>`
- Resource group: `<resource-group>`
- Container app: `<container-app-name>`, `<container-app-fqdn>`, `<container-app-revision>`
- OpenAI resource: `<azure-openai-resource>`
- Key Vault: `<key-vault-name>`
- Generic identity examples: `agent.user@example.com`, `manager@example.com`, `synthetic.worker@example.com`

## Keep vs Publish Workflow

- Keep real values on local testing branches (for example: `local-testing-real`).
- Publish only anonymized content from `public-main` to `origin/master`.
- Never publish real secrets, tenant-specific account emails, subscription IDs, or resource names.

## Pre-push Checks

Before any public push:
1. Run a targeted `git grep` for known real identifiers.
2. Ensure no hardcoded secrets are present.
3. Confirm examples use placeholders or `example.com` addresses.
4. Push from the anonymized branch only.

## Notes

- `.env` and generated diagnostics should stay ignored.
- If a doc needs real values for local operations, keep that in local-only notes/branches, not in public history.
