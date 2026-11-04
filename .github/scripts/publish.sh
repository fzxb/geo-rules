#!/usr/bin/env bash
# Publish a built tree to a data branch.
#
# The branch is rebuilt as a single commit on every run: consumers only ever
# need the current files, and dropping history keeps the repository small even
# though binary rule-sets are committed daily.
#
# usage: publish.sh <source-dir> [branch]
set -euo pipefail

src="${1:-dist}"
branch="${2:-rule-set}"
token="${GITHUB_TOKEN:?GITHUB_TOKEN is not set}"
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is not set}"

if [ ! -f "${src}/manifest.json" ]; then
  echo "refusing to publish: ${src}/manifest.json is missing" >&2
  exit 1
fi

cd "${src}"

# macOS 会在目录里留下 .DS_Store，别让它混进数据分支
find . -name ".DS_Store" -type f -delete

git init -q -b "${branch}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git config commit.gpgsign false

git add -A
git commit -q -m "rule-set: $(date -u +%Y-%m-%dT%H:%M:%SZ) [skip ci]"

# Force push on purpose: the branch is a generated artefact, not history.
git push -q --force \
  "https://x-access-token:${token}@github.com/${repo}.git" \
  "HEAD:${branch}"

echo "published $(git rev-parse --short HEAD) to ${repo}#${branch}"
