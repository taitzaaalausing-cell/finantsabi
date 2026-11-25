# Finantsabi

Isiklik portfelli ja börsiuudiste ülevaade. Töötab Macis ja telefonis (veebirakendus / PWA).

- **Igal hommikul kell 8** (Eesti talveaeg) jooksutab GitHub Actions `src/update.py`:
  hinnad (Nasdaq US / Nasdaq Nordic), kursid (EKP), uudised (Google News, ERR).
- Portfell (`data/portfolio.enc`) ja tulemus (`site/data.enc`) on **AES-256 krüpteeritud**.
  Parool on ainult repo saladuses `FIN_PASSWORD` ja sinu seadmetes.
- Leht: `https://<kasutaja>.github.io/finantsabi/`

## Paigaldamine
- **iPhone:** ava leht Safaris → Jaga → *Lisa avakuvale*.
- **Mac:** ava leht Safaris → *Fail → Lisa Dokki*. Rakendus tekib Dokki ja kausta ~/Applications.

## Muutmine
- Portfell: `bash tools/muuda.sh` (küsib parooli, avab TextEditi, saadab GitHubi).
- Uuenda kohe: GitHub → Actions → *Uuenda ja avalda* → Run workflow.

`work/` kaust (krüpteerimata) ei lähe kunagi GitHubi.
