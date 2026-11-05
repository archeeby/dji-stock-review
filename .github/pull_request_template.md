## Linked issue
Refs #

## Summary
<!-- What changed and why? -->

## Automated validation
- [ ] Latest PR HEAD SHA recorded; **all applicable GitHub Actions jobs completed successfully for that exact SHA** (including full matrix)
- [ ] No pending, failed, timed-out, cancelled, missing or unverifiable required checks
- [ ] HEAD and CI rechecked immediately before merge (repeat if new commits appear)
- [ ] Agent/code review completed; findings resolved

## Local acceptance
- [ ] Preview opened with `bash scripts/preview.sh <PR-number>` (or N/A with reason)
- [ ] Acceptance criteria checked; shared-data changes understood
- [ ] Known gaps and test evidence recorded

## Merge gate
- [ ] Human owner explicitly authorized **this PR's** merge
- [ ] Default merge method: **Create a merge commit** (unless owner explicitly approves otherwise)
- [ ] Post-merge `main` CI checked and reported; linked Issue closed only if fully resolved

<!-- Never merge if CI is not fully successful for the current PR HEAD, even with owner permission. Do not merge without explicit owner permission. If this PR fully resolves the issue, change Refs to Fixes before merging. -->
