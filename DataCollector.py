#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import csv
import os
import requests
import threading
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- CONFIGURAZIONI ----------
# Lista di tutte le regioni italiane nel formato utilizzato da Subito.it
REGIONI = [ "basilicata", "calabria", "campania", "emilia-romagna",
    "friuli-venezia-giulia", "lazio", "liguria", "lombardia", "marche",
    "molise", "piemonte", "puglia", "sardegna", "sicilia", "toscana",
    "trentino-alto-adige", "umbria", "valle-d-aosta", "veneto"
]

# abruzzo tolto perche gia fatto

MAX_LINKS = 100000   # Numero massimo di annunci da estrarre per regione
MAX_PAGES = 300      # Numero massimo di pagine di ricerca da scandire per regione
MAX_WORKERS = 20      # Numero di thread per il parsing dei dettagli
# --------------------------------------

# Header HTTP aggiornati secondo i nuovi dati forniti
REQUEST_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "referer": "https://www.subito.it/",
    "upgrade-insecure-requests": "1",
    "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "device-memory": "8",
    "ect": "4g",
    "accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-language": "it-IT,it;q=0.9,en;q=0.8,en-US;q=0.7",
    "accept-encoding": "gzip, deflate, br"
}

def estrai_link_da_pagina(html: str) -> set:
    """
    Estrae tutti i link di dettaglio annunci (es. https://www.subito.it/auto/… .htm)
    dal codice HTML di una pagina di elenco.
    Ritorna un set di URL unici.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    pattern = re.compile(r"^https://www\.subito\.it/auto/.*\.htm$")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if pattern.match(href):
            links.add(href)
    return links

def estrai_link_da_listings(base_url: str, max_links: int = MAX_LINKS, max_pages: int = MAX_PAGES) -> list:
    """
    Scorre fino a max_pages pagine di elenco (a partire da base_url),
    estrae i link di dettaglio finché non raggiunge max_links.
    Se una pagina restituisce zero link, interrompe l'iterazione per quella regione.
    Ritorna una lista di URL (al più max_links).
    """
    tutti_links = []
    pagina = 1

    while len(tutti_links) < max_links and pagina <= max_pages:
        if pagina == 1:
            url = base_url
        else:
            url = f"{base_url}?o={pagina}"
        print(f"  Aprendo pagina {pagina}: {url}")
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"    Errore HTTP sulla pagina {pagina}: {e}")
            break

        nuovi = estrai_link_da_pagina(resp.text)
        if not nuovi:
            print("    → Nessun annuncio trovato, interrompo per questa regione.")
            break

        prima_len = len(tutti_links)
        for link in nuovi:
            if len(tutti_links) >= max_links:
                break
            if link not in tutti_links:
                tutti_links.append(link)
        print(f"    → Trovati {len(tutti_links) - prima_len} nuovi link (totale: {len(tutti_links)})")
        pagina += 1
        time.sleep(0.5)

    print(f"  Totale link recuperati: {len(tutti_links)} (max {max_links})")
    return tutti_links[:max_links]

def parse_dettaglio_auto_html(html: str) -> dict:
    """
    Dato l'HTML di una pagina di dettaglio annuncio, estrae i campi 'Dati principali':
      - year (data di prima immatricolazione)
      - mileage (Km)
      - fuel_type (Benzina, Diesel, ecc.)
      - transmission (Manuale, Automatico, ecc.)
      - emission_standard (Euro 6, Euro 5, ecc.)
      - body_type (SUV/Fuoristrada, Berlina, ecc.)
    Ritorna un dizionario con queste chiavi (valori None se non trovati).
    """
    soup = BeautifulSoup(html, "html.parser")

    titolo_feat = soup.find("h6", string=re.compile(r"^\s*Dati principali\s*$", re.IGNORECASE))
    if not titolo_feat:
        return {
            "year": None,
            "mileage": None,
            "fuel_type": None,
            "transmission": None,
            "emission_standard": None,
            "body_type": None
        }

    container = titolo_feat.find_next_sibling(
        "div",
        class_=re.compile(r"main-data_main-features-container__")
    )
    if not container:
        return {
            "year": None,
            "mileage": None,
            "fuel_type": None,
            "transmission": None,
            "emission_standard": None,
            "body_type": None
        }

    campi = {
        "year": None,
        "mileage": None,
        "fuel_type": None,
        "transmission": None,
        "emission_standard": None,
        "body_type": None
    }

    for feature_div in container.find_all("div", class_=re.compile(r"main-data_main-feature__")):
        img = feature_div.find("img")
        testo = feature_div.find("p")
        if not img or not testo:
            continue

        src = img.get("src", "")
        filename = src.rsplit("/", 1)[-1]
        base = filename.split(".")[0]
        valore = testo.get_text(strip=True)

        if base == "register_date":
            campi["year"] = valore
        elif base == "mileage_scalar":
            campi["mileage"] = valore
        elif base == "fuel":
            campi["fuel_type"] = valore
        elif base == "gearbox":
            campi["transmission"] = valore
        elif base == "pollution":
            campi["emission_standard"] = valore
        elif base == "car_type":
            campi["body_type"] = valore

    return campi

def parse_dettaglio_auto(url: str) -> dict:
    """
    Effettua una richiesta GET all'URL di dettaglio annuncio, quindi:
      - Estrae il titolo (marca+modello) dal <h1>
      - Estrae il prezzo dal paragrafo con classe "AdInfo_price__…"
      - Estrae l'URL canonico dal <link rel="canonical">
      - Estrae la descrizione dal paragrafo con classe "AdDescription_description__…"
      - Chiama parse_dettaglio_auto_html() sui 'Dati principali'
    Ritorna un dizionario con tutti i campi raccolti.
    """
    record = {
        "url": url,
        "brand_model": None,
        "price": None,
        "year": None,
        "mileage": None,
        "fuel_type": None,
        "transmission": None,
        "emission_standard": None,
        "body_type": None,
        "description": None
    }

    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Errore HTTP dettaglio {url}: {e}")
        return record

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # URL canonico
    canon = soup.find("link", {"rel": "canonical"})
    if canon and canon.get("href"):
        record["url"] = canon["href"]

    # Marca+modello
    h1 = soup.find("h1", class_=re.compile(r".*AdInfo_title__.*"))
    if h1:
        record["brand_model"] = h1.get_text(strip=True)

    # Prezzo
    p_price = soup.find("p", class_=re.compile(r"AdInfo_price__"))
    if p_price:
        record["price"] = p_price.get_text(strip=True)

    # Descrizione
    p_desc = soup.find("p", class_=re.compile(r"AdDescription_description__"))
    if p_desc:
        record["description"] = p_desc.get_text(separator=" ", strip=True)

    # Dati principali
    dati_principali = parse_dettaglio_auto_html(html)
    record.update(dati_principali)

    return record

if __name__ == "__main__":
    # Creiamo un lock per sincronizzare l'accesso al CSV e al set di URL processati
    lock = threading.Lock()

    # Per ciascuna regione, estraiamo e salviamo in un CSV dedicato
    for regione in REGIONI:
        base_listing = f"https://www.subito.it/annunci-{regione}/vendita/auto/"
        print(f"\n=== Elaborazione regione: {regione} ===")
        print(f"> Base URL: {base_listing}")

        # Definisci il file di output per la regione
        output_csv = f"subito_cars_{regione}.csv"
        processed_urls = set()
        file_exists = os.path.isfile(output_csv)

        # Se esiste già il file, carichiamo gli URL già processati
        if file_exists:
            with open(output_csv, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("url"):
                        processed_urls.add(row["url"])

        # Apriamo il CSV in append o write, a seconda che esista o meno
        mode = "a" if file_exists else "w"
        csvfile = open(output_csv, mode, newline="", encoding="utf-8")
        fieldnames = [
            "url", "brand_model", "price", "year", "mileage",
            "fuel_type", "transmission", "emission_standard",
            "body_type", "description"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            csvfile.flush()

        # 1) Estrai fino a MAX_LINKS URL di dettaglio per questa regione
        link_annunci = estrai_link_da_listings(base_listing, MAX_LINKS, MAX_PAGES)
        print(f">> Totale link da processare per {regione}: {len(link_annunci)}\n")

        # 2) Filtriamo i link già processati
        da_processare = [url for url in link_annunci if url not in processed_urls]
        print(f">> {len(da_processare)} nuovi annunci da parsare.\n")

        # 3) Lanciamo un ThreadPoolExecutor per processare in parallelo
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(parse_dettaglio_auto, url): url
                for url in da_processare
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    record = future.result()
                except Exception as e:
                    print(f"    Errore nel thread per {url}: {e}")
                    continue

                # Scriviamo il risultato nel CSV sotto lock
                with lock:
                    if record["url"] not in processed_urls:
                        writer.writerow({k: record.get(k, "") for k in fieldnames})
                        csvfile.flush()
                        processed_urls.add(record["url"])
                        print(f"    Salvato: {record['url']}")

        csvfile.close()
        print(f">> Esportazione completata: {len(processed_urls)} annunci salvati in '{output_csv}'")