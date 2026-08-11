---
name: threat-modeling
description: Use before or while making any identity, ACL, data-classification, new storage/model/network path, logging/audit, Product Tool/MCP, external-transfer, deployment-zone, or security-control change in AgentForge. Produces a threat/control matrix, blocker/critical findings, required contract/architecture changes, a security test/eval plan, and a residual-risk recommendation.
---

Authoritative source: `harness/skills/threat-modeling/SKILL.md`. That file is the full procedure — required inputs, the 8-step method, output shape, checks, escalation, and stop conditions. Read it in full before starting; do not restate or copy its content here, and do not let this file drift from it. If the two ever disagree, `harness/skills/threat-modeling/SKILL.md` wins.

This wrapper exists only so Claude Code actually loads the skill (the `harness/skills/*/SKILL.md` files have no frontmatter, so Claude Code never discovers them on its own). `security-reviewer` should load this skill whenever its task matches the trigger above.
