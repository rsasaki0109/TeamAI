# Governance

TeamAI Runtime is currently maintained as a small pre-1.0 project. The
governance model is intentionally simple until a stable contributor base forms.

## Maintainer Responsibilities

Maintainers are responsible for:

- reviewing changes that affect runtime safety, persistence, or public APIs
- keeping CI, release, and security workflows working
- triaging issues and pull requests
- deciding when a change belongs in the MVP, a later roadmap item, or a plugin

## Decision Principles

Project decisions should preserve the core product shape:

- deterministic control in Python
- model intelligence behind replaceable provider boundaries
- artifacts and reviews instead of unbounded group chat
- local-first operation
- bounded loops and explicit approval for side effects

When there is disagreement, maintainers should prefer the smaller change that
keeps the runtime auditable and testable.

## Release Process

Pre-1.0 releases are cut from `main` by tagging `v*`. The release workflow builds
distributions and uploads them as GitHub artifacts. PyPI publishing requires a
separate explicit decision.

## Security Decisions

Security-sensitive changes require maintainer review. Public discussion of
unfixed vulnerabilities should follow `SECURITY.md`.
