# Security Policy

TeamAI Runtime executes model-selected tools against a local workspace. Security
issues are treated as product bugs even before a stable release.

## Supported Versions

The project is pre-1.0. Security fixes target the latest `main` branch until a
versioned support policy is published.

## Reporting a Vulnerability

Do not report vulnerabilities through a public issue. Use GitHub private
security advisories when the repository is public, or contact the maintainers
privately.

Please include:

- affected version or commit
- Teamfile and command used to reproduce the issue
- expected and actual behavior
- whether the issue can read, write, execute, or exfiltrate outside the
  configured workspace

## Security Model

The runtime is local-first and does not require hosted telemetry or cloud
storage. Built-in filesystem tools must reject access outside the configured
workspace root, including path traversal and symlink escapes.

Side-effecting actions such as writes require an approval provider unless the
caller explicitly opts into auto-approval. Shell execution and network tools are
not built into the MVP.

Secrets, API keys, authorization headers, and raw environment variables must not
be persisted in event payloads.
