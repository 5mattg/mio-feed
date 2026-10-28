"""Legge i feed elencati in feeds.txt e genera la pagina index.html.

Formato di ogni riga di feeds.txt:
  Cartella | Nome | URL feed | parola1, parola2   (l'ultima parte e' facoltativa)
"""
import html
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser

MAX_PER_FONTE = 6        # articoli massimi per ogni fonte
MAX_PER_CARTELLA = 60    # articoli massimi per ogni cartella
MAX_GIORNI = 21          # ignora articoli piu' vecchi di tanti giorni
FUSO = ZoneInfo("Europe/Rome")
MESI = ["gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic"]


def leggi_elenco(percorso="feeds.txt"):
    feeds = []
    with open(percorso, encoding="utf-8") as f:
        for riga in f:
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            parti = [p.strip() for p in riga.split("|")]
            if len(parti) == 3:
                parti.append("")  # nessun filtro
            if len(parti) == 4:
                feeds.append(parti)
            else:
                print(f"Riga ignorata (formato errato): {riga}")
    return feeds


def pulisci(testo, limite=220):
    testo = re.sub(r"<[^>]+>", " ", testo or "")
    testo = html.unescape(re.sub(r"\s+", " ", testo)).strip()
    if len(testo) > limite:
        testo = testo[:limite].rsplit(" ", 1)[0] + "..."
    return testo


def crea_filtro(testo):
    """Trasforma 'DC, Batman' in un filtro che cerca quelle parole intere."""
    parole = [p.strip() for p in testo.split(",") if p.strip()]
    if not parole:
        return None
    modello = "|".join(r"\b" + re.escape(p) + r"\b" for p in parole)
    return re.compile(modello, re.IGNORECASE)


def data_voce(voce):
    t = voce.get("published_parsed") or voce.get("updated_parsed")
    if not t:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(timegm(t), tz=timezone.utc)


def raccogli():
    categorie, errori = {}, []
    limite = datetime.now(timezone.utc) - timedelta(days=MAX_GIORNI)
    for categoria, nome, url, parole in leggi_elenco():
        filtro = crea_filtro(parole)
        d = feedparser.parse(url, agent="Mozilla/5.0 (mio-feed)")
        if not d.entries:
            errori.append(f"{nome} -> {url}")
            continue
        voci = []
        for v in d.entries:
            quando = data_voce(v)
            if quando < limite or not v.get("link"):
                continue
            if filtro:
                tag = " ".join(t.get("term", "") for t in v.get("tags", []))
                cercato = f'{v.get("title", "")} {pulisci(v.get("summary", ""), 10**6)} {tag}'
                if not filtro.search(cercato):
                    continue
            voci.append({
                "titolo": pulisci(v.get("title", "(senza titolo)"), 160),
                "link": v["link"],
                "fonte": nome,
                "quando": quando,
                "testo": pulisci(v.get("summary", "")),
            })
        voci.sort(key=lambda x: x["quando"], reverse=True)
        categorie.setdefault(categoria, []).extend(voci[:MAX_PER_FONTE])
    for c in categorie:
        categorie[c].sort(key=lambda x: x["quando"], reverse=True)
        categorie[c] = categorie[c][:MAX_PER_CARTELLA]
    return categorie, errori


def formatta(dt):
    dt = dt.astimezone(FUSO)
    return f"{dt.day} {MESI[dt.month - 1]}, {dt:%H:%M}"


CSS = """
:root{--bg:#fafaf8;--fg:#1c1c1a;--muted:#6b6b66;--card:#fff;--line:#e4e4de;--accent:#b3261e}
@media (prefers-color-scheme:dark){
:root{--bg:#161615;--fg:#ecece8;--muted:#9a9a93;--card:#1f1f1d;--line:#333330;--accent:#ff7a70}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:8px 0 4px}
.sub{color:var(--muted);font-size:.85rem;margin-bottom:12px}
nav{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;
gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--line);z-index:2}
nav a{padding:4px 12px;border:1px solid var(--line);border-radius:999px;
text-decoration:none;color:var(--fg);font-size:.9rem}
h2{font-size:1.1rem;margin:28px 0 8px;color:var(--accent)}
article{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px 14px;margin-bottom:10px}
article a{color:var(--fg);font-weight:600;text-decoration:none}
article a:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:.8rem;margin:2px 0 4px}
p{margin:0;font-size:.92rem;color:var(--muted)}
"""


def costruisci(categorie):
    ora = formatta(datetime.now(timezone.utc))
    nav = "".join(
        f'<a href="#c{i}">{html.escape(c)}</a>' for i, c in enumerate(categorie))
    corpo = []
    for i, (cat, voci) in enumerate(categorie.items()):
        corpo.append(f'<h2 id="c{i}">{html.escape(cat)}</h2>')
        for v in voci:
            corpo.append(
                "<article>"
                f'<a href="{html.escape(v["link"], quote=True)}" target="_blank" '
                f'rel="noopener">{html.escape(v["titolo"])}</a>'
                f'<div class="meta">{html.escape(v["fonte"])} · {formatta(v["quando"])}</div>'
                f'<p>{html.escape(v["testo"])}</p>'
                "</article>")
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Il mio feed</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>Il mio feed</h1><div class="sub">Aggiornato il {ora}</div>
<nav>{nav}</nav>
{"".join(corpo)}
</div></body></html>"""


if __name__ == "__main__":
    categorie, errori = raccogli()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(costruisci(categorie))
    totale = sum(len(v) for v in categorie.values())
    print(f"Pagina creata: {totale} articoli in {len(categorie)} cartelle.")
    if errori:
        print("ATTENZIONE, feed non leggibili (controlla l'indirizzo):")
        for e in errori:
            print(" -", e)
