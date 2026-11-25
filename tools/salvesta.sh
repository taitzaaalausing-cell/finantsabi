#!/bin/bash
# Salvesta kohalik work/portfolio.json (krüpteeritult) GitHubi ja uuenda leht.
# Käivita:  bash ~/Documents/Finantsabi/tools/salvesta.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
python3 -c "import json;json.load(open('work/portfolio.json'))" || { echo "work/portfolio.json on katki"; exit 1; }
read -r -s -p "Finantsabi parool: " FIN_PASSWORD; echo; export FIN_PASSWORD
# parooli kontroll: praegune pilvefail peab avanema
sh tools/crypt.sh dec data/portfolio.enc /dev/null 2>/dev/null || { echo "Vale parool."; exit 1; }
git pull -q --rebase
sh tools/crypt.sh enc work/portfolio.json data/portfolio.enc
git add data/portfolio.enc && git commit -q -m "Portfell/plaan uuendatud" && git push -q
gh workflow run uuenda.yml >/dev/null && echo "Salvestatud. Uued andmed on lehel ~2 min pärast."
