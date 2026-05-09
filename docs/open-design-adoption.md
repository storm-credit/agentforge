# Open Design Adoption Review

Open Design can be useful for Agent Forge, but it should enter as a design and workflow accelerator first, not as an MVP runtime dependency.

References checked on 2026-05-09:

- [Open Design repository](https://github.com/nexu-io/open-design)
- [Open Design site](https://opendesigner.io/)

## 1. Fit With Agent Forge

Open Design is relevant because it treats design work as an agent-driven artifact loop: select a skill, select a design system, ask clarifying questions, render an artifact, inspect it, and iterate.

That maps well to Agent Forge's operating model:

| Open Design idea | Agent Forge mapping |
|---|---|
| Skills | Specialist agent contracts |
| Design systems | Agent Studio UI and brand/system tokens |
| Artifact preview | Agent Studio prototype and review surface |
| Local-first/BYOK | Closed-network and approved-model direction |
| Coding-agent CLI support | Codex-driven repository workflow |
| Checklists and critique | D2/D3 specialist gate behavior |

## 2. Recommended Use

Use Open Design in three lanes.

| Lane | Use | Status |
|---|---|---|
| Reference | Study its skill, design system, artifact, and critique patterns | Approved |
| Sidecar prototype | Run it separately to prototype Agent Studio screens, dashboards, and decks using synthetic data only | Candidate |
| Product integration | Add Open Design-like skill/design-system behavior inside Agent Forge | Later |

The immediate recommendation is to use it as a sidecar design accelerator for Agent Studio and project presentation artifacts. Agent Forge remains the source of truth for product code, security rules, API contracts, and audit behavior.

## 3. What It Can Help With

- Agent Studio UI prototypes for Agents, Knowledge, Eval, Audit, and Settings.
- Dashboard screen exploration before implementation.
- Design system drafts for internal enterprise UI.
- Pitch decks, product one-pagers, and demo artifacts.
- Better frontend review gates through design critique checklists.

## 4. Guardrails

- Do not process real internal documents or sensitive company data through an unreviewed tool.
- Do not vendor Open Design code, skills, templates, or design systems without license and attribution review.
- Do not make it a required runtime dependency for the MVP.
- Use synthetic data for all prototype artifacts.
- Pin a commit before any serious trial.
- Run dependency and external-call review before closed-network use.
- Treat exported artifacts as drafts to be reviewed and ported, not as automatically accepted production UI.

## 5. Evaluation Checklist

Before adopting it beyond reference use:

- Confirm license obligations for any copied or adapted asset.
- Verify whether local mode can run without unintended external network calls.
- Test with Codex or an approved OpenAI-compatible endpoint.
- Create an Agent Forge-specific design system file with approved colors, layout density, component rules, and anti-patterns.
- Produce one Agent Studio prototype using only synthetic data.
- Review accessibility, enterprise density, security messaging, and maintainability.

## 6. Decision

Agent Forge can use Open Design as a reference and optional local sidecar for Agent Studio prototyping. It should not become a core MVP dependency until security, dependency, license, and closed-network reviews are complete.

