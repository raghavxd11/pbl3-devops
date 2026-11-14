#!/usr/bin/env bash
# Usage: bash scripts/smoke_test.sh <base-url> <expected-version>
# Passes when /health is OK and /version reports the expected build number.
set -u
URL="$1"
EXPECTED="$2"

for i in $(seq 1 20); do
  BODY=$(curl -fs "$URL/version" 2>/dev/null || true)
  if [ -n "$BODY" ]; then
    echo "attempt $i: $BODY"
    GOT=$(echo "$BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])' 2>/dev/null)
    if [ "$GOT" = "$EXPECTED" ] && curl -fs "$URL/health" >/dev/null; then
      echo "SMOKE TEST PASSED: $URL is serving version $EXPECTED"
      exit 0
    fi
  else
    echo "attempt $i: no response yet from $URL"
  fi
  sleep 3
done

echo "SMOKE TEST FAILED: expected version $EXPECTED at $URL"
exit 1
