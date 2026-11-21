#!/usr/bin/env bash
# Crea il repository GitHub pubblico, carica il progetto, attiva Pages e avvia il primo controllo.
# Requisiti: git e GitHub CLI autenticata (gh auth login).
set -euo pipefail
NAME="${1:-iphone-price-monitor}"
cd "$(dirname "$0")"

command -v gh >/dev/null || { echo "Installa GitHub CLI: https://cli.github.com/"; exit 1; }
gh auth status >/dev/null || gh auth login

if [ ! -d .git ]; then
  git init -q -b main
  git add -A
  git commit -qm "Monitor prezzi iPhone ricondizionati"
fi

OWNER="$(gh api user --jq .login)"
gh repo create "$NAME" --public --source . --remote origin --push \
  --description "Monitor orario prezzi iPhone ricondizionati (Amazon.it, Back Market, TrenDevice)"

# GitHub Pages servito dal workflow
gh api -X POST "repos/$OWNER/$NAME/pages" -f build_type=workflow >/dev/null 2>&1 || \
  gh api -X PUT "repos/$OWNER/$NAME/pages" -f build_type=workflow >/dev/null 2>&1 || true

gh workflow run pages.yml -R "$OWNER/$NAME" || true
gh workflow run monitor.yml -R "$OWNER/$NAME" || true

echo
echo "Repository:  https://github.com/$OWNER/$NAME"
echo "Dashboard:   https://$OWNER.github.io/$NAME/   (attiva dopo il primo deploy, 1-2 minuti)"
echo "Telegram:    aggiungi i secret TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID (vedi README)"
