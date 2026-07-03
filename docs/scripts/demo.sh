#!/usr/bin/env sh
# Regenerates docs/assets/demo.png from a real run of the README quickstart.
# Requires: uv (for uvx) and freeze (https://github.com/charmbracelet/freeze).
set -eu

root=$(cd "$(dirname "$0")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cp "$root/examples/minimal.py" "$work/minimal.py"
cd "$work"

uvx docker-dsl minimal --tag=v1.0.0 --out Dockerfile

{
  printf '$ uvx docker-dsl minimal --tag=v1.0.0 --out Dockerfile\n'
  printf '$ cat Dockerfile\n'
  cat Dockerfile
} > transcript.txt

freeze transcript.txt \
  --language console \
  --theme github-dark \
  --background "#0d1117" \
  --window \
  --padding 24 \
  --font.size 28 \
  --output "$root/docs/assets/demo.png"
