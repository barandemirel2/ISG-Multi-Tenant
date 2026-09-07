# AGENTS.md — Repository Operating Rules (ABCD Tech Solutions İSG Risk Analiz)

This file is the mandatory operational constitution for ANY coding agent working in this repository.
Read it before touching the working tree. When in doubt, STOP and report rather than improvising.

---

## 1. START-OF-WORK GIT PREFLIGHT

Before modifying ANY source file, run:

```bash
git status --short
git fetch origin --prune
git switch main
git merge --ff-only origin/main
git rev-list --left-right --count main...origin/main
```

Expected: `0 0` (local main and origin/main fully aligned).

New feature branches MUST be created from a clean, current local main.
Never start new feature work from an old feature branch.

## 2. EXISTING BRANCH CHECK

Before modifying an existing branch, determine:

* merge-base with current main
* ahead/behind count vs main
* working tree status
* whether the latest main is represented in the branch

If the branch is stale or diverged in a risky way: STOP and report before implementation.

## 3. FETCH IS NOT SYNC

`git fetch` updates remote references only. It does NOT merge, rebase, or synchronize the current branch.
Do not claim "fetch fixed divergence." Verify with `git rev-list --left-right --count main...origin/main`.

## 4. SHARED BRANCH HISTORY

Do NOT:

* rebase shared/pushed branches
* force push
* reset --hard
* rewrite history

unless the user explicitly authorizes that exact operation.
Secret exposure is NOT permission to autonomously rewrite shared history.

## 5. SECRET HANDLING

Never hardcode in tracked files:

* passwords
* API keys
* tokens
* database credentials

Use environment variables / ignored local secret files (`*.env`, already ignored).
Never commit `.env`.

If a secret is found in tracked/pushed content:

1. stop propagation
2. sanitize current code
3. report the compromise
4. rotate the secret
5. do not silently rewrite history

## 6. TEST REPORTING

A targeted test PASS must NEVER be presented as a full-suite PASS.
Report these scopes separately, with exact pass/fail/error/skip counts:

* targeted tests
* full backend suite
* frontend suite
* production build
* integration tests
* E2E

## 7. DOCKER VALIDATION

A running container is NOT proof of the current branch.
Before E2E or any container-based claim:

* verify the image/code corresponds to the current HEAD
* rebuild when required
* never claim an old-container PASS as a current-branch PASS

Do not delete persistent volumes without explicit authorization.

## 8. DOMAIN INVARIANTS

Canonical domain rules live in `ARRODES.md`. Critical invariants include:

* FINAL audit is backend-immutable
* soft-deleted audit is unavailable to normal flows
* historical DÖF evidence is retained (no physical deletion)
* invalidated DÖF is not active
* Excel/PDF share the S6 column contract
* audit compliance mutations require durable logging
* ibraz SHA-256 verification is NOT an electronic signature

## 9. GIT WRITES

Commit / push / PR / merge only when explicitly requested by the user or task.
No autonomous force push or history rewrite.

## 10. REPORT HONESTY

Never turn:

* subset PASS
* skipped integration
* stale Docker result
* frontend-only guard

into stronger claims than the evidence supports. Manual UAT PASS must never be claimed without a manual UAT.

---

## Tooling

* `scripts/agent_preflight.sh` — diagnostic-only readiness check (no git state changes).
  Run before starting new work:
  ```bash
  ./scripts/agent_preflight.sh
  ```
  See `ARRODES.md` → Tests for canonical suite commands.
