import time
import csv
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------
# PARTE 1: Selenium + webdriver-manager per estrarre fino a 100 URL
# ---------------------------------------------------------------------
def estrai_link_con_selenium(base_listing_url, max_annunci=100, max_pagine=10):
    """
    Visita le prime pagine di Subito.it/annunci-italia/vendita/auto/ finché
    non raccoglie max_annunci link o supera max_pagine.
    Restituisce un set di URL delle singole schede (fino a max_annunci).
    """
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1080")
    # Facoltativo: disabilita caricamento immagini e CSS per velocizzare
    chrome_opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    })

    # webdriver-manager scarica e usa il ChromeDriver corretto
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_opts)
    all_links = set()

    try:
        for page_num in range(1, max_pagine + 1):
            if len(all_links) >= max_annunci:
                break

            if page_num == 1:
                url = base_listing_url
            else:
                url = base_listing_url + f"?o={page_num}"
            print(f"Aprendo pagina {page_num}: {url}")
            driver.get(url)
            time.sleep(5)  # attendi il caricamento JavaScript

            soup = BeautifulSoup(driver.page_source, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/annunci-italia/vendita/auto/") and href.endswith(".htm"):
                    full_link = "https://www.subito.it" + href
                    if full_link not in all_links:
                        all_links.add(full_link)
                        if len(all_links) >= max_annunci:
                            break

            print(f"  → Trovati {len(all_links)} link di dettaglio (finora).")
            if len(all_links) >= max_annunci:
                break

    finally:
        driver.quit()

    # Ritorna al massimo i primi max_annunci link
    return set(list(all_links)[:max_annunci])


# ---------------------------------------------------------------------
# PARTE 2: Funzione per parsare i dettagli di ciascuna scheda
# ---------------------------------------------------------------------
def parse_dettaglio_auto(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/113.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    dettaglio_soup = BeautifulSoup(resp.text, "html.parser")

    # Proviamo a individuare il contenitore delle specifiche
    possibili_selettori = [
        "div.adDescriptionSection__infoList ul",
        "div.AdInfoList ul",
        "div[class*=infoList] ul",
    ]
    info_list = None
    for sel in possibili_selettori:
        info_list = dettaglio_soup.select_one(sel)
        if info_list:
            break

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
    canon = dettaglio_soup.find("link", {"rel": "canonical"})
    if canon and canon.get("href"):
        data["url"] = canon["href"]

    if not info_list:
        return data

    for li in info_list.select("li"):
        span_label = li.select_one("span")
        if not span_label:
            continue
        label = span_label.get_text(strip=True).rstrip(":")
        testo_intero = li.get_text(separator=" ", strip=True)
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


# ---------------------------------------------------------------------
# PARTE 3: Main – estrazione link + parsing dettagli + salvataggio CSV
# ---------------------------------------------------------------------
if __name__ == "__main__":
    BASE_LISTING_URL = "https://www.subito.it/annunci-italia/vendita/auto/"
    MAX_ANNUNCI = 100       # Ci fermiamo a 100 annunci
    MAX_PAGINE = 10         # Numero massimo di pagine da esplorare

    # 1) Recupera fino a 100 link di dettaglio con Selenium
    listing_urls = estrai_link_con_selenium(
        BASE_LISTING_URL,
        max_annunci=MAX_ANNUNCI,
        max_pagine=MAX_PAGINE
    )

    print(f"\nTotale link recuperati: {len(listing_urls)} (max {MAX_ANNUNCI})\n")

    # 2) Per ogni link, chiama parse_dettaglio_auto(...) e accumula i dati
    tutti_dati = []
    for idx, link in enumerate(list(listing_urls)):
        try:
            record = parse_dettaglio_auto(link)
            print(f"[{idx+1}/{len(listing_urls)}] Parsed: {link}")
            tutti_dati.append(record)
            time.sleep(0.5)  # piccola pausa per non sovraccaricare il server
        except Exception as e:
            print(f"Errore nel parsing di {link}: {e}")

    # 3) Salva esattamente i primi 100 record in CSV
    fieldnames = [
        "url", "brand_model", "year", "mileage", "fuel_type", "engine_power",
        "transmission", "num_previous_owners", "condition", "color",
        "emission_standard", "first_registration_date", "body_type"
    ]
    with open("subito_cars_100.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in tutti_dati:
            writer.writerow(row)

    print(f"\nSalvataggio completato: {len(tutti_dati)} annunci esportati in subito_cars_100.csv")