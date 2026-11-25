#!/usr/bin/env python3
"""Finantsabi uuendaja: hinnad, valuutakursid ja uudised -> data.json.

Ainult Pythoni standardteek. Käivitab GitHub Actions igal hommikul (vt .github/workflows/uuenda.yml).
Kaust FIN_HOME: sisend portfolio.json, väljund data.json (eelmine data.json annab ajaloo).
Allikad (kõik avalikud, ilma võtmeta):
  - Nasdaq quote API (USA aktsiad ja ETF-id, ajalugu)
  - Nasdaq Nordic API (Stockholmi aktsiad)
  - Euroopa Keskpank (EUR kursid)
  - Google News RSS ja ERR majandus RSS (uudised)
Euroopa ETF-id ja LHV fond, millele avalikku hinda ei saa, arvutatakse
"varjuhinnana": viimane teadaolev hind x sama indeksi USA ETF-i muutus x kursimuutus.
"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HOME = os.environ.get("FIN_HOME") or os.path.expanduser("~/Library/Application Support/Finantsabi")
PORTFOLIO = os.path.join(HOME, "portfolio.json")
OUT_JSON = os.path.join(HOME, "data.json")
LOG = os.path.join(HOME, "update.log")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Finantsabi/1.0"
HIST_DAYS = 200

MARKETS = [
    {"id": "COMP", "name": "Nasdaq Composite", "src": "nasdaq", "sym": "COMP", "ac": "index"},
    {"id": "VOO", "name": "S&P 500", "sub": "VOO", "src": "nasdaq", "sym": "VOO", "ac": "etf"},
    {"id": "URTH", "name": "Maailma aktsiad", "sub": "URTH", "src": "nasdaq", "sym": "URTH", "ac": "etf"},
    {"id": "SMH", "name": "Pooljuhid", "sub": "SMH", "src": "nasdaq", "sym": "SMH", "ac": "etf"},
    {"id": "GLD", "name": "Kuld", "sub": "GLD", "src": "nasdaq", "sym": "GLD", "ac": "etf"},
]

MARKET_NEWS = [
    {"id": "world", "title": "Maailma turud", "url": "https://news.google.com/rss/search?q=stock+market+today+when:2d&hl=en-US&gl=US&ceid=US:en", "n": 10},
    {"id": "ee", "title": "Eesti majandus", "url": "https://www.err.ee/rss/majandus", "n": 10,
     "fallback": "https://news.google.com/rss/search?q=site:err.ee+majandus+when:3d&hl=et&gl=EE&ceid=EE:et"},
    {"id": "eeb", "title": "Börs eesti keeles", "url": "https://news.google.com/rss/search?q=b%C3%B6rs+OR+aktsiad+OR+aktsiaturg+when:3d&hl=et&gl=EE&ceid=EE:et", "n": 8},
]

ERRORS = []


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def get(url, accept="application/json, text/plain, */*", tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "et,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def get_json(url):
    return json.loads(get(url))


def num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = re.sub(r"[^0-9.\-]", "", str(s).replace(",", ""))
    try:
        return float(s)
    except ValueError:
        return None


def iso_from_us(d):  # 11/24/2026 -> 2026-11-24
    m, d_, y = d.split("/")
    return f"{y}-{int(m):02d}-{int(d_):02d}"


# ---------------------------------------------------------------- FX (EKP)
def ecb_rates():
    """Tagastab {kuupäev: {USD:x, SEK:y, ...}} viimase 90 päeva kohta (1 EUR = x valuutat)."""
    xml = get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml", accept="application/xml")
    root = ET.fromstring(xml)
    out = {}
    for cube in root.iter():
        t = cube.attrib.get("time")
        if t:
            out[t] = {c.attrib["currency"]: float(c.attrib["rate"]) for c in cube}
    return out


def fx_on(fxhist, day):
    """Kurss antud päeval (või viimane varasem)."""
    keys = sorted(k for k in fxhist if k <= day)
    if not keys:
        keys = sorted(fxhist)
    return fxhist[keys[-1]]


# ---------------------------------------------------------------- Nasdaq
def nasdaq_quote(sym, ac):
    d = get_json(f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(sym)}/info?assetclass={ac}")["data"]
    status = d.get("marketStatus") or ""
    prim = d.get("primaryData") or {}
    sec = d.get("secondaryData") or {}
    regular = prim
    ext = None
    if sec and num(sec.get("lastSalePrice")) and status in ("Pre-Market", "After-Hours", "Closed"):
        regular = sec
        if status != "Closed":
            ext = {"label": "eelturul" if status == "Pre-Market" else "järelturul",
                   "price": num(prim.get("lastSalePrice")), "pct": num(prim.get("percentageChange")),
                   "ts": prim.get("lastTradeTimestamp")}
    price = num(regular.get("lastSalePrice"))
    chg = num(regular.get("netChange"))
    return {
        "price": price,
        "chg": chg,
        "pct": num(regular.get("percentageChange")),
        "prev": (price - chg) if (price is not None and chg is not None) else None,
        "last": num(prim.get("lastSalePrice")) or price,  # kõige värskem (ka eelturg) – varjuhinna ankurdamiseks
        "ts": regular.get("lastTradeTimestamp"),
        "status": status,
        "ext": ext,
        "range52": ((d.get("keyStats") or {}).get("fiftyTwoWeekHighLow") or {}).get("value"),
    }


def nasdaq_hist(sym, ac, days=HIST_DAYS):
    to = dt.date.today()
    fr = to - dt.timedelta(days=days)
    d = get_json(f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(sym)}/historical?assetclass={ac}"
                 f"&fromdate={fr}&todate={to}&limit=400")
    rows = (((d.get("data") or {}).get("tradesTable") or {}).get("rows")) or []
    out = [(iso_from_us(r["date"]), num(r["close"])) for r in rows if num(r.get("close"))]
    return sorted(out)


def nordic(orderbook, days=HIST_DAYS):
    to = dt.date.today()
    fr = to - dt.timedelta(days=days)
    d = get_json(f"https://api.nasdaq.com/api/nordic/instruments/{orderbook}/chart?assetClass=SHARES&fromDate={fr}&toDate={to}")
    cd = d["data"]
    hist = sorted((p["z"]["dateTime"][:10], float(p["y"])) for p in cd.get("CP", []) if p.get("y") is not None)
    live = get_json(f"https://api.nasdaq.com/api/nordic/instruments/{orderbook}/chart?assetClass=SHARES")["data"]["chartData"]
    price = num(live.get("lastSalePrice"))
    prev = num(live.get("previousClose"))
    if price is None and hist:
        price = hist[-1][1]
    today = dt.date.today().isoformat()
    # tänane päev ajalukku (päeva sees uuendades)
    if price is not None:
        hist = [h for h in hist if h[0] != today] + ([(today, price)] if live.get("timeAsOf", "").startswith(today) else [])
    return {
        "price": price,
        "prev": prev,
        "chg": (price - prev) if (price is not None and prev) else None,
        "pct": num(live.get("percentageChange")),
        "last": price,
        "ts": live.get("timeAsOf"),
        "status": "",
        "ext": None,
    }, hist


# ---------------------------------------------------------------- Uudised
def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def parse_rss(xml_bytes, limit=8, max_age_days=10):
    root = ET.fromstring(xml_bytes)
    items = []
    now = dt.datetime.now(dt.timezone.utc)
    for it in root.iter("item"):
        title = strip_tags(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = src_el.text.strip() if src_el is not None and src_el.text else ""
        if source and " - " in source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
            source = source.split(" - ")[0].strip()
        elif source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        elif not source and " - " in title and "news.google" in link:
            title, source = title.rsplit(" - ", 1)
        pub = it.findtext("pubDate")
        ts = None
        if pub:
            try:
                ts = email.utils.parsedate_to_datetime(pub)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
            except (TypeError, ValueError):
                ts = None
        if ts and (now - ts).days > max_age_days:
            continue
        if not source:
            m = re.match(r"https?://(?:www\.)?([^/]+)", link)
            source = m.group(1) if m else ""
        items.append({"title": title, "link": link, "source": source,
                      "ts": ts.isoformat() if ts else None, "t": ts.timestamp() if ts else 0})
    # dedup pealkirja järgi
    seen, out = set(), []
    for x in sorted(items, key=lambda x: -x["t"]):
        k = re.sub(r"\W+", "", x["title"].lower())[:60]
        if k in seen or not x["title"]:
            continue
        seen.add(k)
        out.append(x)
    return out[:limit]


def google_news(query, lang):
    if lang == "et":
        params = "hl=et&gl=EE&ceid=EE:et"
    else:
        params = "hl=en-US&gl=US&ceid=US:en"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query + ' when:7d')}&{params}"
    return parse_rss(get(url, accept="application/rss+xml, application/xml"), limit=6)


# ---------------------------------------------------------------- Abi
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def to_eur(x, cur, rates):
    if x is None:
        return None
    if cur == "EUR":
        return x
    r = rates.get(cur)
    return x / r if r else None


def fmt_eur(x):
    s = f"{abs(round(x)):,.0f}".replace(",", " ")
    return ("−" if x < 0 else "") + s + " €"


def fmt_pct(x, sign=True):
    s = f"{abs(x):.1f}".replace(".", ",") + "%"
    if not sign:
        return s
    return ("+" if x >= 0 else "−") + s


# ---------------------------------------------------------------- Põhitöö
def main():
    notify = "--notify" in sys.argv
    os.makedirs(HOME, exist_ok=True)
    run(notify)


def run(notify):
    started = time.time()
    port = load_json(PORTFOLIO, None)
    if not port:
        log("portfolio.json puudub")
        return
    prev_data = load_json(OUT_JSON, {})
    prev_by_id = {h["id"]: h for h in prev_data.get("holdings", [])}

    # --- kursid
    try:
        fxhist = ecb_rates()
    except Exception as e:  # noqa: BLE001
        ERRORS.append(f"EKP kursid: {e}")
        fxhist = prev_data.get("fxhist") or {"1970-01-01": {"USD": 1.16, "SEK": 11.0}}
    fx_day = sorted(fxhist)[-1]
    rates = fxhist[fx_day]

    # --- turud (proxyd tulevad siit samast vahemälust)
    qcache, hcache = {}, {}

    def nq(sym, ac):
        key = (sym, ac)
        if key not in qcache:
            q = nasdaq_quote(sym, ac)
            # väljaspool kauplemisaega on "secondaryData" järelturu hind; ametlik sulgemine on ajaloo viimasel real
            if q.get("status") != "Market Open":
                try:
                    h = nh(sym, ac)
                except Exception:  # noqa: BLE001
                    h = []
                if len(h) >= 2:
                    price, prev = h[-1][1], h[-2][1]
                    q.update(price=price, prev=prev, chg=price - prev, pct=(price / prev - 1) * 100, closeDate=h[-1][0])
            qcache[key] = q
        return qcache[key]

    def nh(sym, ac):
        key = (sym, ac)
        if key not in hcache:
            hcache[key] = nasdaq_hist(sym, ac)
        return hcache[key]

    markets = []
    for m in MARKETS:
        try:
            q = nq(m["sym"], m["ac"])
            h = nh(m["sym"], m["ac"])
            markets.append({**m, **q, "hist": h[-66:]})
        except Exception as e:  # noqa: BLE001
            ERRORS.append(f"{m['name']}: {e}")
    for cur in ("USD", "SEK"):
        days = sorted(fxhist)
        series = [(d, fxhist[d][cur]) for d in days if cur in fxhist[d]]
        if len(series) >= 2:
            p, c = series[-2][1], series[-1][1]
            markets.append({"id": "EUR" + cur, "name": f"EUR/{cur}", "sub": "EKP", "price": c, "prev": p,
                            "chg": c - p, "pct": (c / p - 1) * 100, "hist": series[-66:], "ts": series[-1][0], "fx": True})

    # --- positsioonid
    changed_port = False
    holdings = []
    for h in port["holdings"]:
        row = dict(h)
        row["estimated"] = False
        try:
            if h["src"] == "nasdaq":
                ac = "etf" if h.get("kind") == "ETF" else "stocks"
                q = nq(h["sym"], ac)
                hist = nh(h["sym"], ac)
            elif h["src"] == "nordic":
                q, hist = nordic(h["sym"])
            elif h["src"] == "proxy":
                a = h["anchor"]
                pq = nq(h["proxy"], "etf")
                ph = nh(h["proxy"], "etf")
                if not a.get("proxy"):
                    a["proxy"] = pq["last"]
                    changed_port = True
                if not a.get("fx"):
                    a["fx"] = rates["USD"]
                    changed_port = True

                def shadow(pp, usd):
                    return a["price"] * (pp / a["proxy"]) * (a["fx"] / usd)

                # ankur võeti kõige värskemast hinnast (ka eelturg), seega hinnang samuti
                if pq.get("status") == "Pre-Market" and pq.get("ext") and pq["ext"].get("price"):
                    cur_p, prev_p = pq["ext"]["price"], pq["price"]
                else:
                    cur_p, prev_p = pq["price"], pq.get("prev")
                price = shadow(cur_p, rates["USD"])
                prev = shadow(prev_p, rates["USD"]) if prev_p else None
                hist = [(d, shadow(c, fx_on(fxhist, d)["USD"])) for d, c in ph]
                q = {"price": price, "prev": prev, "chg": (price - prev) if prev else None,
                     "pct": (price / prev - 1) * 100 if prev else None, "ts": pq["ts"], "ext": None,
                     "status": pq["status"]}
                row["estimated"] = True
                row["anchorInfo"] = f"{h['anchor']['price']} € ({h['anchor']['date']}) + {h['proxy']} muutus"
            else:
                raise ValueError("tundmatu allikas " + h["src"])
            row.update({k: q.get(k) for k in ("price", "prev", "chg", "pct", "ts", "ext", "status", "range52")})
            row["hist"] = hist
            row["stale"] = False
        except Exception as e:  # noqa: BLE001
            ERRORS.append(f"{h['name']}: {e}")
            old = prev_by_id.get(h["id"], {})
            for k in ("price", "prev", "chg", "pct", "ts", "ext"):
                row[k] = old.get(k)
            row["hist"] = old.get("histNat") or []
            row["stale"] = True
            if row.get("hist") is None:
                row["hist"] = []
        holdings.append(row)

    if changed_port:
        save_json(PORTFOLIO, port)

    # --- väärtused eurodes
    for r in holdings:
        cur = r["cur"]
        r["valueEur"] = (to_eur(r["price"], cur, rates) or 0) * r["qty"] if r.get("price") else 0
        r["dayEur"] = to_eur(r["chg"], cur, rates) * r["qty"] if r.get("chg") is not None else 0
        # soetus eurodes: portfellis antud costEur (ostuaegse kursiga, nagu Yahoo) või avg x kogus tänase kursiga
        if r.get("costEur") or r.get("avg"):
            r["costEur"] = r.get("costEur") or to_eur(r["avg"] * r["qty"], cur, rates)
            r["gainEur"] = r["valueEur"] - r["costEur"] if r["valueEur"] else None
            r["gainPct"] = r["gainEur"] / r["costEur"] * 100 if r["gainEur"] is not None and r["costEur"] else None
        else:
            r["costEur"] = r["gainEur"] = r["gainPct"] = None
    total = sum(r["valueEur"] for r in holdings)
    day = sum(r["dayEur"] for r in holdings)
    for r in holdings:
        r["share"] = r["valueEur"] / total * 100 if total else 0
        # ajalugu eurodes (kuupäev, eur-hind) graafiku jaoks
        r["histEur"] = [(d, to_eur(c, r["cur"], fx_on(fxhist, d))) for d, c in (r.get("hist") or [])]
        r["histNat"] = [(d, round(c, 4)) for d, c in (r.get("hist") or [])][-130:]
        r.pop("hist", None)
    holdings.sort(key=lambda r: -r["valueEur"])

    # --- portfelli ajalugu praeguste kogustega
    all_days = sorted({d for r in holdings for d, _ in r["histEur"]})
    series = []
    last_px = {}
    first_day_ok = None
    for d in all_days:
        for r in holdings:
            for dd, px in r["histEur"]:
                if dd == d:
                    last_px[r["id"]] = px
        if len(last_px) == len(holdings):
            first_day_ok = first_day_ok or d
            series.append((d, round(sum(last_px[r["id"]] * r["qty"] for r in holdings), 2)))
    today = dt.date.today().isoformat()
    if series and series[-1][0] != today:
        series.append((today, round(total, 2)))
    elif series:
        series[-1] = (today, round(total, 2))
    for r in holdings:  # sparkline: viimased ~30 kauplemispäeva
        r["spark"] = [round(px, 4) for _, px in r["histEur"][-30:]]
        r["histEur"] = [(d, round(px, 4)) for d, px in r["histEur"][-130:]]

    # --- päevased hetktõmmised (pikaajaline päris ajalugu)
    snaps = dict(prev_data.get("snapshots") or [])
    snaps[today] = round(total, 2)

    # --- uudised
    news_by_id = {}
    for r in holdings:
        q = r.get("news")
        if not q:
            continue
        try:
            news_by_id[r["id"]] = google_news(q, r.get("lang", "en"))
        except Exception as e:  # noqa: BLE001
            ERRORS.append(f"Uudised {r['name']}: {e}")
            news_by_id[r["id"]] = (prev_data.get("news", {}).get("holdings", {}) or {}).get(r["id"], [])
    market_news = []
    for f in MARKET_NEWS:
        try:
            try:
                items = parse_rss(get(f["url"], accept="application/rss+xml, application/xml"), limit=f["n"], max_age_days=4)
            except Exception:  # noqa: BLE001
                if not f.get("fallback"):
                    raise
                items = parse_rss(get(f["fallback"], accept="application/rss+xml, application/xml"), limit=f["n"], max_age_days=4)
        except Exception as e:  # noqa: BLE001
            ERRORS.append(f"Uudised {f['title']}: {e}")
            items = next((x["items"] for x in prev_data.get("news", {}).get("market", []) if x["id"] == f["id"]), [])
        market_news.append({"id": f["id"], "title": f["title"], "items": items})

    # --- kokkuvõte
    movers = sorted([r for r in holdings if r.get("pct") is not None], key=lambda r: r["pct"])
    prev_total = total - day
    day_pct = (day / prev_total * 100) if prev_total else 0
    known = [r for r in holdings if r.get("gainEur") is not None]
    divs = sum(r.get("divEur") or 0 for r in holdings)
    summary = {
        "total": total,
        "day": day,
        "dayPct": day_pct,
        "best": {"id": movers[-1]["id"], "name": movers[-1]["name"], "pct": movers[-1]["pct"]} if movers else None,
        "worst": {"id": movers[0]["id"], "name": movers[0]["name"], "pct": movers[0]["pct"]} if movers else None,
        "gainKnown": sum(r["gainEur"] for r in known) if known else None,
        "costKnown": sum(r["costEur"] for r in known) if known else None,
        "knownCount": len(known),
        "divEur": divs or None,
        "usdShare": sum(r["share"] for r in holdings if r["cur"] == "USD" or r.get("proxy")),
        "top": {"name": holdings[0]["name"], "share": holdings[0]["share"]} if holdings else None,
    }

    data = {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fxDay": fx_day,
        "rates": {"USD": rates.get("USD"), "SEK": rates.get("SEK")},
        "summary": summary,
        "holdings": holdings,
        "series": series,
        "snapshots": sorted(snaps.items()),
        "markets": markets,
        "plan": port.get("plan"),
        "news": {"holdings": news_by_id, "market": market_news},
        "errors": ERRORS,
        "seconds": round(time.time() - started, 1),
    }
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT_JSON)
    log(f"OK {fmt_eur(total)} päev {fmt_eur(day)} ({fmt_pct(day_pct)}) | {len(ERRORS)} viga | {data['seconds']} s")
    for e in ERRORS:
        log("  ! " + e)

    if notify and total:
        best = summary["best"]
        msg = f"{fmt_eur(total)}, päev {fmt_pct(day_pct)}"
        if best:
            msg += f" · parim {best['name']} {fmt_pct(best['pct'])}"
        subprocess.run(["/usr/bin/osascript", "-e",
                        f'display notification "{msg}" with title "Finantsabi" subtitle "Hommikune ülevaade on valmis"'],
                       check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log("KRIITILINE: " + traceback.format_exc())
        sys.exit(1)
