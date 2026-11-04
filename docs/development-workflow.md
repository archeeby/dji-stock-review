# Specification-driven development workflow

## Artifacts
- **GitHub Issue**: why and what — user scenarios, acceptance criteria, scope, priority, status, constraints and links.
- **Design document**: how — inspected current code, alternatives and trade-offs, architecture, affected modules and contracts, implementation steps, testing and risks. For substantial work, store in `docs/design/` and link from the Issue; for trivial work, a short Issue plan is enough.
- **Pull Request**: actual implementation, links to Issue and approved design, deviations, test evidence, review and remaining risks.

## Lifecycle
1. Discover the problem through voice or text discussion; agree on actual user journeys and expected behavior.
2. Create an Issue with scope and acceptance criteria, initially pending design.
3. Inspect relevant code and tests before proposing changes.
4. Draft a design and implementation plan with options, module impacts, validation and risks.
5. Discuss and revise the plan; complex or risky tasks require explicit human approval before implementation.
6. Delegate the bounded approved work to an agent on a feature branch with a PR.
7. Run tests and CI, investigate failures, and obtain independent code review. Material design deviations return to discussion.
8. Human owner reviews evidence and authorizes merge.

## Design document template
Status (Draft / Approved / Superseded); linked Issue; problem and use cases; acceptance criteria; observed current behavior; assumptions and non-goals; alternatives and decision; affected modules and interfaces; ordered implementation plan; unit/integration/E2E test matrix; security and data safety; rollback; open questions.

An Issue tracks work; the design records technical decisions; the PR demonstrates implementation. Do not silently modify approved decisions or treat a draft as permission to code.
