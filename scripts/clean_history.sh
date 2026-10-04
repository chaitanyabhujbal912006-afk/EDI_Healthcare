#!/usr/bin/env bash
set -euo pipefail

# scripts/clean_history.sh
# Purges dist/ binary artifacts and error.log from the entire Git repository history using git-filter-repo.
#
# IMPORTANT PREREQUISITES & WARNINGS:
# 1. This rewrites Git commit SHAs across the entire history of the repository.
# 2. Before executing, ensure all team members have committed and pushed work, or have backed up local changes.
# 3. Create a fresh bare or mirror backup clone:
#      git clone --mirror <remote-url> backup-repo.git
# 4. Install git-filter-repo:
#      pip install git-filter-repo
# 5. Run this script from the root of a freshly cloned repository.
# 6. Force-push rewritten branches and tags:
#      git push origin --force --all
#      git push origin --force --tags
# 7. Note: Force-pushing invalidates open Pull Requests, cached CI builds, and requires team members
#    to re-clone the repository or reset their local branches (`git fetch origin && git reset --hard origin/main`).

echo "=== ValidEDI / EdiPro History Cleaner ==="

if ! command -v git-filter-repo &> /dev/null; then
    echo "ERROR: 'git-filter-repo' is not found in PATH." >&2
    echo "Install it using: pip install git-filter-repo" >&2
    exit 1
fi

echo "Filtering repository history to remove 'dist/' and 'error.log'..."

git filter-repo \
    --path dist \
    --path error.log \
    --invert-paths \
    --force

echo "=== History rewrite completed successfully! ==="
echo "Inspect new log: git log --stat"
echo "When verified, push the rewritten history using:"
echo "  git push origin --force --all"
echo "  git push origin --force --tags"
