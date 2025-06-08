#!/usr/bin/env python3
"""
GermanyDataCollector.py
• Collects every listing link on AutoScout24.de (infinite-scroll + ?page=2…)
• Opens each detail page, reads the JSON blob, writes one CSV row per car
Requirements: undetected-chromedriver, selenium-stealth, beautifulsoup4, lxml
"""

import csv
import json
import random
import re
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup as Soup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# ────────────── CONFIG ──────────────
BASE_URL = (
    "https://www.autoscout24.de/lst?sort=standard&desc=0"
    "&ustate=N%2CU&atype=C&cy=D&ocs_listing=include"
    "&source=homepage_search-mask"            # add your filters here
)
CSV_NAME  = "ML-car-price-estimation/DataGermany.csv"
HEADLESS  = True
MAX_PAGES = 2                               # safety limit
# ─────────────────────────────────────

def human_delay(a=0.7, b=1.4):
    """Random sleep to look less like a bot."""
    time.sleep(random.uniform(a, b))

# ---------- launch stealth Chrome ----------
chrome_options = uc.ChromeOptions()
if HEADLESS:
    chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--lang=de-DE")

driver = uc.Chrome(options=chrome_options)
stealth(
    driver,
    languages=["de-DE"],
    vendor="Google Inc.",
    platform="Win32",
    webgl_vendor="Intel Inc.",
    renderer="Intel Iris"
)
wait = WebDriverWait(driver, 12)

def click_if_visible(xpath: str) -> None:
    """Clicks the first element matching XPath if it exists and is clickable."""
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
    except Exception:
        pass

def collect_links_on_page(url: str) -> set[str]:
    """
    Open one list page, scroll until no new cards appear,
    return the set of listing URLs found.
    """
    driver.get(url)
    if not collect_links_on_page.cookie_clicked:
        click_if_visible('//button[contains(.,"Alle akzeptieren")]')  # cookie banner
        collect_links_on_page.cookie_clicked = True
    human_delay()

    links, previous_count = set(), -1
    while True:
        cards = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="list-item"]')
        if len(cards) == previous_count:
            break
        previous_count = len(cards)
        for c in cards:
            try:
                href = c.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                links.add(href.split('?')[0])            # remove tracking query-string
            except Exception:
                pass
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        human_delay(0.4, 0.9)
    return links
collect_links_on_page.cookie_clicked = False

# ════════════ PHASE 1 – gather every listing link ════════════
all_links = set()

for page in range(1, MAX_PAGES + 1):
    page_url = BASE_URL + (f"&page={page}" if page > 1 else "")
    print(f"🔍 Page {page} …", end="", flush=True)
    new_links = collect_links_on_page(page_url) - all_links
    if not new_links:
        print(" stop (no new listings).")
        break
    all_links.update(new_links)
    print(f" {len(new_links)} new (total {len(all_links)})")
    human_delay(0.8, 1.2)

print(f"🗂  Total listing links collected: {len(all_links)}")

# ════════════ PHASE 2 – visit each detail page & write CSV ════════════
csv_header = [
    "car_name", "price", "mileage_km", "fuel",
    "power_kw", "transmission", "first_registration",
    "seller_type", "description"
]

with open(CSV_NAME, "w", newline="", encoding="utf-8") as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(csv_header)

    for idx, url in enumerate(all_links, start=1):
        driver.get(url)
        human_delay(0.6, 1.1)

        # Extract the JSON blob injected by Next.js
        match = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            driver.page_source
        )
        if not match:
            print(f"⚠️  __NEXT_DATA__ missing on {url}")
            continue

        data = json.loads(match.group(1))
        try:
            listing = data["props"]["pageProps"]["listingDetails"]
        except KeyError:
            print(f"⚠️  Unexpected JSON schema on {url}")
            continue

        vehicle = listing.get("vehicle", {})
        price   = listing.get("price",  {})

        row = [
            " ".join(filter(None, (
                vehicle.get("make", ""),
                vehicle.get("model", ""),
                vehicle.get("modelVersionInput", "")
            ))),
            price.get("priceFormatted", ""),
            vehicle.get("mileageInKmRaw", ""),
            vehicle.get("fuelCategory", {}).get("formatted", ""),
            vehicle.get("powerInKw", ""),
            vehicle.get("rawData", {}).get("engine", {})
                   .get("transmissionType", {}).get("formatted", ""),
            vehicle.get("firstRegistrationDate", ""),
            listing.get("seller", {}).get("type", ""),
            Soup(listing.get("description", ""), "lxml").get_text(" ", strip=True)
        ]
        writer.writerow(row)
        print(f"✓ {idx:>4}/{len(all_links)}  {row[0][:55]}")
        human_delay(0.2, 0.35)

driver.quit()
print(f"🎉 Completed — data written to {CSV_NAME}")