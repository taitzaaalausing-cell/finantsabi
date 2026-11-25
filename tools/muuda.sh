#!/bin/bash
# Muuda portfelli (kogused, ostuhinnad, uued positsioonid) ja saada GitHubi.
# Käivita:  bash ~/Documents/Finantsabi/tools/muuda.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
read -r -s -p "Finantsabi parool: " FIN_PASSWORD; echo; export FIN_PASSWORD
git pull -q --rebase
mkdir -p work
sh tools/crypt.sh dec data/portfolio.enc work/portfolio.json || { echo "Vale parool?"; exit 1; }
cp work/portfolio.json work/portfolio.before.json
echo "Avan portfolio.json TextEditis. Salvesta, sulge aken ja vajuta siin Enter."
open -e work/portfolio.json
read -r -p ""
python3 -c "import json;json.load(open('work/portfolio.json'))" || { echo "JSON on katki, muudatust ei saadetud."; exit 1; }
if cmp -s work/portfolio.json work/portfolio.before.json; then echo "Muudatusi polnud."; exit 0; fi
sh tools/crypt.sh enc work/portfolio.json data/portfolio.enc
git add data/portfolio.enc && git commit -q -m "Portfell muudetud" && git push -q
gh workflow run uuenda.yml >/dev/null && echo "Saadetud. Uued andmed on lehel ~2 min pärast."
