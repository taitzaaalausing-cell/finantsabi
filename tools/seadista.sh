#!/bin/bash
# Finantsabi esmane seadistus: GitHubi repo + igahommikune uuendus + veebileht.
# Käivita oma Terminalis:  bash ~/Documents/Finantsabi/tools/seadista.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
REPO="${1:-finantsabi}"

echo "== 1/6 GitHubi tööriist (gh)"
command -v gh >/dev/null || brew install gh

echo "== 2/6 GitHubi sisselogimine (avaneb brauser, kinnita seal)"
gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
USER_GH=$(gh api user -q .login)
echo "Sisse logitud: $USER_GH"

echo "== 3/6 Parool"
echo "Parooliga krüpteeritakse portfell ja andmed. Sama parool läheb telefoni ja Maci."
echo "Vali pikk parool (vähemalt 12 märki, nt neli juhuslikku sõna)."
while true; do
  read -r -s -p "Parool: " P1; echo
  read -r -s -p "Korda:  " P2; echo
  if [ "$P1" != "$P2" ]; then echo "Ei kattu, proovi uuesti."; continue; fi
  if [ ${#P1} -lt 12 ]; then echo "Liiga lühike."; continue; fi
  break
done
export FIN_PASSWORD="$P1"

echo "== 4/6 Krüpteerin"
test -f work/portfolio.json || { echo "work/portfolio.json puudub"; exit 1; }
mkdir -p data
sh tools/crypt.sh enc work/portfolio.json data/portfolio.enc
if [ -f work/data.json ]; then sh tools/crypt.sh enc work/data.json site/data.enc; fi

echo "== 5/6 Repo ja saladus"
if [ ! -d .git ]; then git init -q -b main; fi
git config user.name >/dev/null || git config user.name "$USER_GH"
git config user.email >/dev/null || git config user.email "$USER_GH@users.noreply.github.com"
git add -A
git commit -q -m "Finantsabi" || true
if ! gh repo view "$USER_GH/$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --description "Isiklik portfelli ja börsiuudiste ülevaade (andmed krüpteeritud)"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$USER_GH/$REPO.git"
printf '%s' "$FIN_PASSWORD" | gh secret set FIN_PASSWORD --repo "$USER_GH/$REPO"

echo "== 6/6 Veebileht (GitHub Pages), push ja esimene pilveuuendus"
gh api -X POST "repos/$USER_GH/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || \
  gh api -X PUT "repos/$USER_GH/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || true
git push -u origin main
sleep 5
gh workflow run uuenda.yml --repo "$USER_GH/$REPO" || true
unset FIN_PASSWORD P1 P2

URL="https://$USER_GH.github.io/$REPO/"
echo
echo "Valmis. Leht: $URL"
echo "Esimene uuendus jookseb ~1–2 min: gh run watch --repo $USER_GH/$REPO"
echo "$URL" > work/url.txt
