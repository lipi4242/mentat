# Connector Template (EN)

Configuration record for an external tool integration.

## When to create one

The USER asks for help with an external tool (Gmail, TickTick, Asana, Strava, etc.)
for the first time. Set up auth in `.env` (NEVER commit), document the interface here.

## Frontmatter

```yaml
---
type: connector
name: <tool-name>
status: configured   # configured | placeholder
auth_location: .env
tags: [...]
---
```

## Body structure

1. **What this connects to** — one line: tool name, purpose in this workspace.
2. **Auth + setup** — where credentials live, how to refresh. Reference `.env` key
   names only — **NEVER paste actual credentials in this file.**
3. **Available actions** — bullet list of capabilities this connector exposes.
4. **Quirks / known limits** — rate limits, pagination, known gotchas.
5. **Linked procedures** — paths to procedure files that use this connector.

## IMPORTANT — Security

**This file MUST NOT contain any credentials, tokens, API keys, or passwords.**
Reference `.env` key names (e.g. `GMAIL_CLIENT_ID`) but never their values.
Credentials live exclusively in `.env` (gitignored).

## Filename

`brain/connectors/<name>.md`

## Example

```yaml
---
type: connector
name: gmail
status: configured
auth_location: .env
tags: [email, google]
---
```

**What this connects to:** Gmail — read and send email for the USER's account.

**Auth + setup:** OAuth2 service account. Keys: `GMAIL_CLIENT_ID`,
`GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` in `.env`. Refresh with
`scripts/get-token.sh`.

**Available actions:**
- Search inbox by query string
- Read thread by ID
- Send email draft

**Quirks / known limits:** 250 quota units/second; batch if looping many threads.

**Linked procedures:** `brain/procedures/morning-email-triage.md`
