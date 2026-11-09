#!/usr/bin/env bash
# The CI commands, one function per job: .github/workflows/ci.yml calls `ci.sh <job>`, and the
# maintainers run the same file on the composed tree before every release, so a release whose
# CI would fail is not published.
#
#   .github/ci.sh brain|engine|fleet|admin [...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

with_pytest() { python3 -c 'import pytest' 2>/dev/null || python3 -m pip install -q pytest; }

job_brain() {
  (cd "$ROOT" && python3 -m unittest discover -s reference/manifest -q)
}

job_engine() {
  with_pytest
  (cd "$ROOT/engine" && python3 -m pytest -q -p no:cacheprovider)
  # The quickstart, as in engine/README.md, in an empty agent folder.
  local agent; agent="$(mktemp -d)"
  (
    cd "$agent"
    git init -q
    "$ROOT/engine/sync-to.sh" . --pack cases
    python3 -m anytime_engine.selftest
    ANYTIME_PLUGINS=anytime_cases python3 -m anytime_engine.tick hourly --dry-run > plan.json
    python3 -c "import json; print(len(json.load(open('plan.json'))['actions']), 'actions')"
    test -z "$(git status --short | grep -v -e anytime_engine/ -e anytime_cases/ -e plan.json)"
  )
  rm -rf "$agent"
}

job_fleet() {
  with_pytest
  cd "$ROOT/fleet"
  PYTHONPATH=src python3 -m unittest discover -s tests -q
  PYTHONPATH=src python3 -m unittest discover -s src/fleet -p 'test_*.py' -q
  node --test bridge/test/*.test.mjs
  FLEET_REGISTRY=examples/registry PYTHONPATH=src python3 -m fleet.cli validate
}

job_admin() {
  cd "$ROOT/admin"
  npm ci --prefix worker && npm ci --prefix admin
  npm --prefix worker run typecheck
  npm --prefix worker run test
  npm --prefix admin run typecheck
  npm --prefix admin run test
  npm --prefix admin run build
  python3 -m unittest discover -s agent/cases/tests
}

[ $# -gt 0 ] || { echo "usage: $0 brain|engine|fleet|admin [...]" >&2; exit 2; }
for job in "$@"; do
  case "$job" in
    brain|engine|fleet|admin) echo "== ci $job"; ( "job_$job" ) ;;
    *) echo "unknown job: $job" >&2; exit 2 ;;
  esac
done
