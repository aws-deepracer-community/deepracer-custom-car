#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TARGET_HOST="${1:?Usage: $0 <target-host> [ssh-user]}"
SSH_USER="${2:-deepracer}"

SSH_CMD="ssh ${SSH_USER}@${TARGET_HOST}"

echo "==> Deploying to ${SSH_USER}@${TARGET_HOST}"

# Stop service
echo "Stopping deepracer-core..."
${SSH_CMD} "sudo systemctl stop deepracer-core"

# Sync install/ to the target (only changed files are transferred)
echo "Syncing install/ to ${TARGET_HOST}..."
rsync -a --rsync-path='sudo rsync' \
    "${REPO_DIR}/install/" \
    "${SSH_USER}@${TARGET_HOST}:/opt/aws/deepracer/lib/"

# Sync start_ros.sh
echo "Syncing start_ros.sh..."
rsync -a --rsync-path='sudo rsync' \
    "${REPO_DIR}/build_scripts/files/common/start_ros.sh" \
    "${SSH_USER}@${TARGET_HOST}:/opt/aws/deepracer/start_ros.sh"

# Disable CSRF protection for cross-origin dev access
echo "Disabling CSRF..."
${SSH_CMD} "sudo sed -i 's/REMEMBER_COOKIE_SECURE=True)/REMEMBER_COOKIE_SECURE=True,\n    WTF_CSRF_ENABLED=False)/' /opt/aws/deepracer/lib/webserver_pkg/lib/python3.*/site-packages/webserver_pkg/webserver.py"

# Restart deepracer
echo "Restarting deepracer-core..."
${SSH_CMD} "sudo systemctl restart deepracer-core"

echo "==> Done. Deployed to ${SSH_USER}@${TARGET_HOST}"
