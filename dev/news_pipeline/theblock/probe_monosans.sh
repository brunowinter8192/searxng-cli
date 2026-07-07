#!/usr/bin/env bash
# Proxy pool evidence for theblock.co — monosans/proxy-scraper-checker runs
#
# Deliverables: pool yield under neutral check_url vs theblock.co check_url
#
# Acquisition: nightly.link arm64 binary (TUI, requires TTY) → falls back to Docker.
# Docker image: ghcr.io/monosans/proxy-scraper-checker:<sha> (from compose.yaml in docker artifact)
# Two Docker artifacts consumed: proxy-scraper-checker-binary-aarch64-apple-darwin.zip (binary, TUI)
#                                proxy-scraper-checker-docker-arm64-v8.zip (Docker build context + config)
#
# The binary (arm64 native, TUI) was extracted from the binary artifact but REQUIRES a real TTY.
# Docker image (no TUI, stdout logging) is the working acquisition path on this machine.
#
# Usage (from worktree root):
#   bash dev/news_pipeline/theblock/probe_monosans.sh neutral
#   bash dev/news_pipeline/theblock/probe_monosans.sh theblock

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
IMAGE="ghcr.io/monosans/proxy-scraper-checker:f44fdb22c56e544eedf5784b2c5501fe9b3e466b"

NEUTRAL_CFG="$ROOT/dev/news_pipeline/theblock/monosans_cfg_neutral.toml"
THEBLOCK_CFG="$ROOT/dev/news_pipeline/theblock/monosans_cfg_theblock.toml"
NEUTRAL_OUT="$ROOT/dev/news_pipeline/theblock/monosans_out_neutral"
THEBLOCK_OUT="$ROOT/dev/news_pipeline/theblock/monosans_out_theblock"

MODE="${1:-neutral}"

case "$MODE" in
  neutral)
    CFG="$NEUTRAL_CFG"
    OUT="$NEUTRAL_OUT"
    echo "=== Run: neutral check_url (https://ipv4.icanhazip.com), concurrency 512 ==="
    ;;
  theblock)
    CFG="$THEBLOCK_CFG"
    OUT="$THEBLOCK_OUT"
    echo "=== Run: theblock check_url (https://www.theblock.co/sitemap_tbco_news.xml), concurrency 50 ==="
    ;;
  *)
    echo "Usage: $0 [neutral|theblock]" >&2
    exit 1
    ;;
esac

mkdir -p "$OUT"

# Docker needs /app/out as output path — sed-patch the config path inline
DOCKER_CFG="$(mktemp /tmp/monosans_docker_cfg.XXXXXX.toml)"
sed 's|^path = ".*"|path = "/app/out"|' "$CFG" > "$DOCKER_CFG"

echo "Start: $(date)"
START="$(date +%s)"

docker run --rm \
  -v "${DOCKER_CFG}:/app/config.toml:ro" \
  -v "${OUT}:/app/out" \
  -v "proxy_scraper_checker_cache:/home/app/.cache/proxy_scraper_checker" \
  "$IMAGE"

END="$(date +%s)"
echo "End: $(date) — elapsed: $((END-START))s"
rm -f "$DOCKER_CFG"

# Summarise results
echo ""
echo "=== Results ==="
if [ -f "$OUT/proxies.json" ]; then
  python3 -c "
import json
data = json.loads(open('$OUT/proxies.json').read())
print(f'Total passing proxies: {len(data)}')
from collections import Counter
protos = Counter(p['protocol'] for p in data)
for proto, count in sorted(protos.items()):
    print(f'  {proto}: {count}')
"
else
  echo "No proxies.json found in $OUT"
fi
