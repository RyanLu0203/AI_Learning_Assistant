#!/usr/bin/env bash
# Execute on the ECS instance; this is the Task 2 public-IP evidence check.
set -uo pipefail
umask 077
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ECS_PUBLIC_IP="${1:-}"
if [[ ! "$ECS_PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Usage: bash scripts/check-ecs-public-ui.sh ECS_PUBLIC_IPV4" >&2
    exit 2
fi
check() {
    printf 'AI Learning Assistant ECS Web Interface Check\n'
    date '+Time (local): %Y-%m-%dT%H:%M:%S%z'
    date -u '+Time (UTC): %Y-%m-%dT%H:%M:%SZ'
    printf 'Machine: %s\n' "$(hostname)"
    printf 'Operating system: %s\n' "$(uname -sr)"
    printf 'CPU architecture: %s\n' "$(uname -m)"
    printf 'ECS login user: %s\n' "$(whoami)"
    printf 'Website URL: http://%s:14242/ui/\n' "$ECS_PUBLIC_IP"
    docker --version || return 1
    printf '\nDocker application container:\n'
    docker ps -a --filter publish=14242 --format \
        'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || return 1
    local status curl_exit
    status=$(curl --noproxy '*' -sS --connect-timeout 5 --max-time 15 \
        -o /dev/null -w '%{http_code}' "http://${ECS_PUBLIC_IP}:14242/ui/")
    curl_exit=$?
    printf '\nHTTP status: %s\n' "$status"
    if [ "$curl_exit" -eq 0 ] && [ "$status" = 200 ]; then
        printf 'Website URL check: PASS\n'
    else
        printf 'Website URL check: FAIL (curl exit code: %s)\n' "$curl_exit"
        return 1
    fi
    printf 'Browser screenshot with address bar: capture separately from your own computer.\n'
}
check 2>&1 | tee "${ROOT_DIR}/ecs-docker-check.txt"
