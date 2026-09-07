#!/usr/bin/env bash
#
# agent_preflight.sh — diagnostic-only repository readiness check.
#
# Reports: current branch, working tree state, local main vs origin/main,
# branch divergence, merge-base, and any unresolved merge/rebase state.
#
# It NEVER modifies git state: no fetch, no merge, no checkout, no reset,
# no branch deletion. Read-only diagnostic.
#
# Usage:
#   ./scripts/agent_preflight.sh            # default: continuing work
#   ./scripts/agent_preflight.sh --new-work # stricter: new feature work
#
# Exit codes:
#   0 = READY
#   1 = STOP (condition requires attention)
#   2 = environment problem (not a git repo, origin missing, etc.)
set -u

MODE="continue"
if [ "${1:-}" = "--new-work" ]; then
  MODE="new-work"
elif [ "${1:-}" != "" ]; then
  echo "usage: $0 [--new-work]" >&2
  exit 2
fi

say()  { printf '%s\n' "$*"; }
fail() { printf 'STATUS: STOP\nreason: %s\n' "$*"; exit 1; }

say "AGENT PREFLIGHT"
say ""

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "not inside a git repository"
fi

# --- branch ---------------------------------------------------------------
BRANCH="$(git branch --show-current 2>/dev/null)"
[ -z "$BRANCH" ] && fail "detached HEAD; switch to a branch first"
say "current branch: $BRANCH"

# --- working tree ---------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  say "working tree: DIRTY"
  [ "$MODE" = "new-work" ] && fail "dirty working tree (new work must start clean)"
else
  say "working tree: CLEAN"
fi

# --- unresolved merge/rebase state ----------------------------------------
if [ -d "$(git rev-parse --git-path rebase-merge 2>/dev/null)" ] || \
   [ -d "$(git rev-parse --git-path rebase-apply 2>/dev/null)" ]; then
  fail "unresolved rebase/merge in progress"
fi
if [ -f "$(git rev-parse --git-path MERGE_HEAD 2>/dev/null)" ]; then
  fail "unresolved merge in progress"
fi

# --- main vs origin/main --------------------------------------------------
if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
  fail "origin/main not available locally; run 'git fetch origin --prune'"
fi

LOCAL_MAIN="$(git rev-parse main 2>/dev/null || echo MISSING)"
ORIGIN_MAIN="$(git rev-parse origin/main)"
say "local main:    ${LOCAL_MAIN}"
say "origin/main:   ${ORIGIN_MAIN}"

MAIN_DIV="$(git rev-list --left-right --count main...origin/main 2>/dev/null || echo '? ?')"
say "main <-> origin/main: $MAIN_DIV"

if [ "$LOCAL_MAIN" != "MISSING" ] && [ "$LOCAL_MAIN" != "$ORIGIN_MAIN" ]; then
  fail "local main is not aligned with origin/main (run: git switch main && git merge --ff-only origin/main)"
fi

# --- current branch vs main -----------------------------------------------
if [ "$BRANCH" != "main" ]; then
  if git merge-base --is-ancestor main "$BRANCH" 2>/dev/null; then
    MERGE_BASE="$(git merge-base main "$BRANCH")"
    say "merge-base with main: $MERGE_BASE (main is ancestor of $BRANCH)"
    AB="$(git rev-list --left-right --count main...$BRANCH)"
    MAIN_ONLY="${AB%%	*}"
    BR_ONLY="${AB##*	}"
    say "branch divergence: main-only=$MAIN_ONLY branch-only=$BR_ONLY"
    if [ "$MODE" = "new-work" ]; then
      if [ "$MAIN_ONLY" != "0" ]; then
        fail "branch is behind main (new feature work must start from current main)"
      fi
      if [ "$BRANCH" = "main" ]; then :; fi
    fi
  else
    MERGE_BASE="$(git merge-base main "$BRANCH" 2>/dev/null || echo NONE)"
    say "merge-base with main: ${MERGE_BASE:-NONE}"
    if [ "$MODE" = "new-work" ]; then
      fail "branch has diverged from main (merge-base is not an ancestor relation)"
    fi
  fi
else
  say "current branch: main (no branch divergence check)"
fi

# --- mode-specific summary ------------------------------------------------
if [ "$MODE" = "new-work" ]; then
  say ""
  say "STATUS: READY (new work may start from a clean, current main)"
else
  say ""
  say "STATUS: READY (continuing existing branch is fine; verify ahead-only feature branch is intentional)"
fi
exit 0
