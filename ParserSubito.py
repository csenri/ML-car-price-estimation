import requests
from bs4 import BeautifulSoup
import re
import time

# 1) Leggi e parsifica il file copy.html salvato in precedenza
with open("copy.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 2) Estrai tutti i link relativi alle pagine di dettaglio degli annunci
#    In Subito.it gli URL delle schede auto sono del tipo:
#    "/annunci-italia/vendita/auto/<marca>/<modello>_<id>.htm"
#    quindi filtriamo tutti gli <a href="..."> che contengono "/vendita/auto/" ma non puntano alla listing page stessa.

base_url = "https://www.subito.it"

listing_links = set()
for a in soup.find_all("a", href=True):
    href = a["href"]
    # Condizione: link relativo che contiene "/annunci-italia/vendita/auto/"
    # Esclude la pagina listing principale ("/annunci-italia/vendita/auto/") e cattura solo i dettagli veri e propri
    if href.startswith("/annunci-italia/vendita/auto/") and href != "/annunci-italia/vendita/auto/":
        # Escludiamo eventuali link a sottosezioni (per sicurezza) controllando che finisca in ".htm"
        if href.endswith(".htm"):
            listing_links.add(base_url + href)

print(f"Trovati {len(listing_links)} link di dettaglio:")
for link in list(listing_links)[:10]:
    print("  ", link)
print()

# Se il tuo copy.html contiene già molte pagine di risultati, otterrai X link in listing_links.
# A questo punto, per ciascun link andremo a scaricare la scheda di dettaglio e a parsare i campi.

# 3) Definiamo una funzione per scaricare e parsare i campi di dettaglio da ciascuna pagina
def parse_dettaglio_auto(url):
    """
    Scarica il dettaglio dell'annuncio da `url` e restituisce un dizionario con:
    - brand_model
    - year
    - mileage
    - fuel_type
    - engine_power
    - transmission
    - num_previous_owners
    - condition
    - color
    - emission_standard
    - first_registration_date
    - body_type
    Se un campo non è trovato, rimane a None.
    """
    # (1) Scarica l'HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/113.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    dettaglio_soup = BeautifulSoup(resp.text, "html.parser")

    # (2) In molte schede Subito, le informazioni tecniche sono elencate come <li><span class="...">Label:</span> Valore</li>
    #     Cerchiamo il contenitore generale che raggruppa la lista di specifiche.
    #     Può variare: ad esempio "div.AdInfoList", "div.adDescriptionSection__infoList ul", ecc.
    #     Di solito nel codice attuale si trova sotto un div con classe simile a "adInfoList" o "adDescriptionSection__infoList".

    # Proviamo alcune delle classi più frequenti:
    possibili_selettori = [
        "div.adDescriptionSection__infoList ul",
        "div.AdInfoList ul",
        "div[class*=infoList] ul",   # generic: qualsiasi classe che contenga 'infoList'
    ]
    info_list = None
    for sel in possibili_selettori:
        info_list = dettaglio_soup.select_one(sel)
        if info_list:
            break

    # Prepariamo la struttura di output
    data = {
        "url": url,
        "brand_model": None,
        "year": None,
        "mileage": None,
        "fuel_type": None,
        "engine_power": None,
        "transmission": None,
        "num_previous_owners": None,
        "condition": None,
        "color": None,
        "emission_standard": None,
        "first_registration_date": None,
        "body_type": None,
    }

    # Salviamo URL canonico (se presente)
    canon = dettaglio_soup.find("link", {"rel": "canonical"})
    if canon and canon.get("href"):
        data["url"] = canon["href"]

    # Se non troviamo la lista, restituiamo il dizionario parziale
    if not info_list:
        return data

    # (3) Iteriamo su ogni <li> e ricaviamo label + valore
    for li in info_list.select("li"):
        span_label = li.select_one("span")
        if not span_label:
            continue
        label = span_label.get_text(strip=True).rstrip(":")
        # Il testo successivo al <span> è tipicamente valore
        # Può trovarsi in span_label.next_sibling oppure in un tag fratello
        val = None
        # Proviamo a prendere tutto il testo rimanente del <li> togliendo la parte del label
        testo_intero = li.get_text(separator=" ", strip=True)
        # Rimuoviamo la parte del label + ":" dal testo intero per isolare il valore
        # (a volte può ripetere il label nel testo, ma di solito funziona)
        val = testo_intero.replace(label + ":", "").strip()

        key = label.lower()

        if key.startswith("marca") or "modello" in key:
            data["brand_model"] = val
        elif key.startswith("anno"):
            data["year"] = val
        elif "chil" in key:
            data["mileage"] = val
        elif "carburante" in key:
            data["fuel_type"] = val
        elif "potenza" in key:
            data["engine_power"] = val
        elif "cambio" in key:
            data["transmission"] = val
        elif "proprietari" in key:
            data["num_previous_owners"] = val
        elif "condizion" in key:
            data["condition"] = val
        elif "colore" in key:
            data["color"] = val
        elif "emission" in key:
            data["emission_standard"] = val
        elif "prima immatricolazione" in key or "data prima" in key:
            data["first_registration_date"] = val
        elif "carrozzeria" in key:
            data["body_type"] = val

    return data

# 4) Cicliamo su tutti i link trovati e creiamo una lista di dizionari
tutti_dati = []
for idx, link in enumerate(list(listing_links)):
    try:
        record = parse_dettaglio_auto(link)
        print(f"[{idx+1}/{len(listing_links)}] Parsed: {link}")
        tutti_dati.append(record)
        # Pausa breve per non sovraccaricare il server
        time.sleep(0.5)
    except Exception as e:
        print(f"Errore nel parsing di {link}: {e}")

# 5) (Facoltativo) Mostriamo i primi 5 record estratti
print("\nEsempio dei primi 5 record:\n")
for rec in tutti_dati[:5]:
    for k, v in rec.items():
        print(f"{k:25s}: {v}")
    print("-" * 60)