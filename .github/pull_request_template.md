## Linked issue
Refs #

## Summary
<!-- What changed and why? -->

## Automated validation
- [ ] Latest PR HEAD SHA recorded; **all applicable GitHub Actions jobs completed successfully for that exact SHA** (including full matrix)
- [ ] No pending, failed, timed-out, cancelled, missing or unverifiable required checks
- [ ] HEAD and CI rechecked immediately before merge (repeat if new commits appear)
- [ ] Agent/code review completed; findings resolved

## Local acceptance (integration/E2E + preview)
- [ ] Applicable local integration/E2E test matrix selected and documented (or N/A with reason)
- [ ] All **required** local tests passed for the recorded PR HEAD SHA (or N/A with reason); environment/logs/results recorded
- [ ] Preview/user journeys checked via `bash scripts/preview.sh <PR-number>` (or N/A with reason); shared-data risks understood
- [ ] No required local test is failed, missing or unverified; affected checks repeated after new commits
- [ ] Known gaps and test evidence recorded
<!-- Future: one-command `bash scripts/accept.sh <PR-number>` is planned but NOT yet implemented. -->

## Merge gate
- [ ] Human owner explicitly authorized **this PR's** merge
- [ ] Default merge method: **Create a merge commit** (unless owner explicitly approves otherwise)
- [ ] Post-merge `main` CI checked and reported; linked Issue closed only if fully resolved

<!-- Never merge if CI is not fully successful for the current PR HEAD, even with owner permission. Do not merge without explicit owner permission. If this PR fully resolves the issue, change Refs to Fixes before merging. -->
