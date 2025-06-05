#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import csv
import requests
from bs4 import BeautifulSoup

# ---------- CONFIGURAZIONI ----------
BASE_LISTING_URL = "https://www.subito.it/annunci-piemonte/vendita/auto/"
MAX_LINKS = 10000                        # Numero massimo di annunci da estrarre
MAX_PAGES = 300                         # Numero massimo di pagine di ricerca da scandire
OUTPUT_CSV = "subito_cars_details.csv"  # Nome del CSV di output
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

def estrai_link_da_listings(max_links: int = MAX_LINKS, max_pages: int = MAX_PAGES) -> list:
    """
    Scorre fino a max_pages pagine di elenco (a partire dalla base),
    estrae i link di dettaglio finché non raggiunge max_links.
    Ritorna una lista di URL (al più max_links).
    """
    tutti_links = []
    pagina = 1

    while len(tutti_links) < max_links and pagina <= max_pages:
        if pagina == 1:
            url = BASE_LISTING_URL
        else:
            url = f"{BASE_LISTING_URL}?o={pagina}"
        print(f"Aprendo pagina {pagina}: {url}")
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Errore HTTP sulla pagina {pagina}: {e}")
            break

        nuovi = estrai_link_da_pagina(resp.text)
        prima_len = len(tutti_links)
        for link in nuovi:
            if len(tutti_links) >= max_links:
                break
            if link not in tutti_links:
                tutti_links.append(link)
        print(f"  → Trovati {len(tutti_links) - prima_len} nuovi link (totale: {len(tutti_links)})")
        pagina += 1
        time.sleep(0.5)

    print(f"Totale link recuperati: {len(tutti_links)} (max {max_links})\n")
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

    # 1) Cerca l'intestazione <h6> con testo "Dati principali"
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

    # 2) Scende nel div successivo che contiene tutte le feature
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

    # 3) Per ciascun <div class="main-data_main-feature__…"> estraiamo <img> e <p>
    for feature_div in container.find_all("div", class_=re.compile(r"main-data_main-feature__")):
        img = feature_div.find("img")
        testo = feature_div.find("p")
        if not img or not testo:
            continue

        src = img.get("src", "")
        filename = src.rsplit("/", 1)[-1]      # es. "mileage_scalar.svg"
        base = filename.split(".")[0]          # es. "mileage_scalar"
        valore = testo.get_text(strip=True)    # es. "42429 Km", "Benzina", ecc.

        if base == "register_date":
            # "07/2019" → year
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

    # a) URL canonico
    canon = soup.find("link", {"rel": "canonical"})
    if canon and canon.get("href"):
        record["url"] = canon["href"]

    # b) Marca+modello dal <h1 class="AdInfo_title__…">
    h1 = soup.find("h1", class_=re.compile(r".*AdInfo_title__.*"))
    if h1:
        record["brand_model"] = h1.get_text(strip=True)

    # c) Prezzo dal <p class="AdInfo_price__…">
    p_price = soup.find("p", class_=re.compile(r"AdInfo_price__"))
    if p_price:
        record["price"] = p_price.get_text(strip=True)

    # d) Descrizione dal <p class="AdDescription_description__…">
    p_desc = soup.find("p", class_=re.compile(r"AdDescription_description__"))
    if p_desc:
        record["description"] = p_desc.get_text(separator=" ", strip=True)

    # e) Estrazione 'Dati principali'
    dati_principali = parse_dettaglio_auto_html(html)
    record.update(dati_principali)

    return record

if __name__ == "__main__":
    # 1) Estrai fino a MAX_LINKS URL di dettaglio
    link_annunci = estrai_link_da_listings(MAX_LINKS, MAX_PAGES)
    print(f">> Totale link da processare: {len(link_annunci)}\n")

    # 2) Per ciascun URL, facciamo il parsing dei dati di dettaglio
    tutti_dati = []
    for idx, url in enumerate(link_annunci, start=1):
        print(f"[{idx}/{len(link_annunci)}] Parsando: {url}")
        record = parse_dettaglio_auto(url)
        tutti_dati.append(record)
        time.sleep(0.5)  # breve pausa tra le richieste

    # 3) Salva in CSV
    fieldnames = [
        "url", "brand_model", "price", "year", "mileage",
        "fuel_type", "transmission", "emission_standard",
        "body_type", "description"
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in tutti_dati:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\n>> Esportazione completata: {len(tutti_dati)} annunci salvati in '{OUTPUT_CSV}'")