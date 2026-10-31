#!/usr/bin/env bash
set -euo pipefail
root="$PWD"
export HOMEBREW_NO_AUTO_UPDATE=1
if [[ "$MODE" == stable ]]; then
    (cd source && bun run package:homebrew --wld-tag v0.14.3 --output "$root/tap-check")
elif [[ "$MODE" == candidate ]]; then
    python3 -m http.server 8765 --bind 127.0.0.1 --directory candidate-assets > evidence/candidate-http.log 2>&1 &
    server_pid=$!
    trap 'kill "$server_pid"' EXIT
    ready=false
    for attempt in {1..30}; do
        if curl --fail --silent http://127.0.0.1:8765/SHA256SUMS > /dev/null; then ready=true; break; fi
        sleep 1
    done
    [[ "$ready" == true ]]
    (cd source && bun run package:homebrew --wld-tag v0.14.4-rc.1 --output "$root/tap-check" --test-only --wld-base-url http://127.0.0.1:8765)
elif [[ "$MODE" != repair ]]; then
    echo "Invalid qualification mode: $MODE" >&2
    exit 1
fi
(cd source && bun run package:homebrew:check --tap "$root/tap-check") 2>&1 | tee evidence/package-check.log
