# Release Governance Skill

## Enforcement Status

Nothing loads or runs this procedure today. Files under `harness/skills/*/SKILL.md` carry no frontmatter, so Claude Code's Skill tool cannot discover this one on its own, and no agent contract points a dispatched subagent at it. Following the checklist below is currently up to an individual session choosing to open and read this file — there is no gate behind it. Compare `harness/skills/threat-modeling/`, the one skill in this directory that *is* reachable: it works because a matching `.claude/skills/threat-modeling/SKILL.md` wrapper exists and references (not copies) it. Making this skill real means the same thing here — a discoverable wrapper, plus something that actually invokes it at the trigger point below.

Do not take this note's word for what's wired — it will drift. Check yourself: `apps/api/.venv/Scripts/python.exe harness/tools/project_status.py`

## Trigger

Use before PR merge, Build activation, release, pilot entry/exit, incident closure, baseline acceptance, or any GO/HOLD/NO-GO claim.

## Required Inputs

- exact candidate commit/Build/release/environment;
- accepted Work Order and requirement IDs;
- applicable Release Gates;
- Evidence Package and raw references;
- required Review Results;
- unresolved dependencies, risks, and limitations;
- accountable decision roles.

## Steps

1. Verify candidate identity and that evidence is fresh for the same candidate/configuration/environment.
2. Verify approved scope and changed-file/component boundary.
3. Sample raw CI/test/eval/trace/audit/security/operations evidence rather than trusting summaries alone.
4. Check every mandatory gate and blocker case.
5. Confirm missing/incomplete evidence is not marked passed.
6. Confirm technical MVP, pilot, and production readiness are not conflated.
7. Confirm non-code dependencies remain owned and visible.
8. Check reviewer independence and conflicts of interest.
9. Check rollback/disable/containment and decision expiry conditions.
10. Record findings, recommendation, and accountable final decision.

## Outputs

- Review Result;
- gate-by-gate status;
- GO/HOLD/NO-GO recommendation;
- missing evidence and open findings;
- decision record and conditions;
- update/close guidance for issue, PR, release, or incident.

## Checks

- ACL leakage and other blockers are zero/open-none as required.
- Required CI and Eval Cases pass on exact candidate.
- Product model/tool/environment routes are approved, not placeholders.
- Evidence contains no secrets or unauthorized content.
- Implementer is not the sole release authority.
- Merge success is not called pilot or production success.
- Residual risk has accountable acceptance.
- Pilot owner/docs/SSO/models/staging/operations exist before pilot GO.

## Escalation

Escalate evidence conflict or possible misrepresentation to accountable human owner; security blockers to Security; missing product/pilot authority to PM/Sponsor; environment and operations gaps to Platform/Service Owner.

## Stop Conditions

- GO recommendation and accountable decision are recorded;
- HOLD conditions and owners are explicit;
- NO-GO is recorded for unacceptable risk/value/feasibility;
- candidate identity/evidence is invalid;
- required human authority is unavailable.