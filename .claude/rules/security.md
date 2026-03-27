# Rules: Security (letsbuild/hooks/**/* , letsbuild/publisher/**/*)

## Secret Detection

PrePublish hook MUST run `trufflehog` or `gitleaks` on all generated code before GitHub publishing. This is non-negotiable — the SecurityGate blocks publication if any secret is detected.

Scan targets:
- All files in the generated project workspace
- Environment variable references in code (must use placeholders, not real values)
- Docker files, CI configs, .env.example files

## Sandbox Security

- Docker containers run rootless with `--security-opt=no-new-privileges`
- Outbound network: allowed (package install). Inbound: blocked.
- Resource limits enforced: 4 CPU, 8GB RAM, 20GB disk, 30min lifetime
- Workspace is destroyed after each run — no persistent state in containers

## API Key Handling

- NEVER hardcode API keys anywhere in the codebase
- All keys via environment variables: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `SERPAPI_KEY`
- Generated projects use `.env.example` with placeholder values
- The SecurityGate scans for patterns: `sk-ant-`, `ghp_`, `Bearer`, API key regex patterns

## Hook Security

- Hooks execute in the main process, not in sandboxes
- Hook scripts MUST NOT make external network calls
- Hook scripts MUST complete within 5 seconds
- PreToolUse hooks can BLOCK tool execution — use with care
- PostToolUse hooks can MODIFY tool results — log all modifications

## GitHub Publisher Security

- Generated repos are created as private by default
- User must explicitly approve making repos public
- CI/CD secrets use GitHub Secrets, never hardcoded in workflows
- Generated `.gitignore` always includes: `.env`, `*.key`, `*.pem`, `__pycache__/`, `node_modules/`

## Input Sanitisation

- All JD text is sanitised before processing (HTML entities, script tags stripped)
- URLs are validated before fetching (no file://, no localhost, no private IP ranges)
- Company names are normalised and checked against a blocklist
