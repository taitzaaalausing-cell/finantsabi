#!/bin/sh
# Kasutus: FIN_PASSWORD=... tools/crypt.sh enc|dec SISEND VÄLJUND
# AES-256-CBC + PBKDF2-SHA256 250000 kordust – sama, mida index.html brauseris lahti teeb.
set -e
[ -n "$FIN_PASSWORD" ] || { echo "FIN_PASSWORD puudub" >&2; exit 2; }
case "$1" in
  enc) openssl enc -aes-256-cbc -pbkdf2 -iter 250000 -md sha256 -salt -in "$2" -out "$3" -pass env:FIN_PASSWORD ;;
  dec) openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -md sha256 -in "$2" -out "$3" -pass env:FIN_PASSWORD ;;
  *) echo "kasutus: crypt.sh enc|dec sisend väljund" >&2; exit 2 ;;
esac
