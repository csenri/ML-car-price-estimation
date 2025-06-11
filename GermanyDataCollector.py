
"""
AutoScout24 Germany – ZIP‑based Scraper  (v3.9 • Jun 2025)
===========================================================
• **New rule:** keep only ZIP coordinates that are at least `MIN_DISTANCE_KM`
  apart (great‑circle) from every coordinate already selected.  That prevents
  querying heavily overlapping 100‑km radii.
• Everything else (exception‑proof parsing, per‑ZIP CSV flush, fsync) is
  unchanged from v3.8.

Adjustable parameters live in the CONFIG block below.
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
import re
import time
from pathlib import Path
from typing import List, Tuple
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup as Soup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth

# ───────────────────── CONFIG ─────────────────────
CSV_ZIPCODES = Path("postal-code-germany.csv")
OUTPUT_CSV   = "AutoScout24_ZIP.csv"
HEADLESS     = True
MAX_PAGES    = 20          # site shows max 20 list pages
ZIP_LIMIT: int | None = None   # limit after distance filtering (None = all)
ROUND_COOR   = 5           # decimals to dedup identical coords
MIN_DISTANCE_KM = 70     # keep next ZIP only if ≥ this distance from prev.
HUMAN_MIN, HUMAN_MAX = 0.10, 0.20

BASE_MASK = (
    "https://www.autoscout24.de/lst?sort=standard&desc=0"
    "&ustate=N%2CU&atype=C&cy=D&ocs_listing=include"
    "&lat={lat}&lon={lon}&zip={zip}&zipr=100&source=homepage_search-mask"
)
# ─────────────────────────────────────────────────

def human_delay(a: float = HUMAN_MIN, b: float = HUMAN_MAX) -> None:
    time.sleep(random.uniform(a, b))

# ────────── GEO HELPERS ──────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great‑circle distance in kilometres (Haversine formula)."""
    R = 6371.0  # km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = p2 - p1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# ────────── LOAD, DEDUP & DISTANCE FILTER ──────────

def load_unique_zip_rows(csv_path: Path, limit: int | None = None) -> List[Tuple[str, float, float]]:
    df = pd.read_csv(csv_path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(5)
    df["lat_r"] = df["lat"].round(ROUND_COOR)
    df["lon_r"] = df["lon"].round(ROUND_COOR)
    df = df.drop_duplicates(subset=["lat_r", "lon_r"], keep="first")

    selected: List[Tuple[str, float, float]] = []
    for code, lat, lon in zip(df["code"], df["lat_r"], df["lon_r"]):
        if not selected:
            selected.append((code, lat, lon))
            if limit and len(selected) >= limit:
                break
            continue
        if all(haversine(lat, lon, s_lat, s_lon) >= MIN_DISTANCE_KM for _, s_lat, s_lon in selected):
            selected.append((code, lat, lon))
            if limit and len(selected) >= limit:
                break
    return selected

# ────────── SELENIUM SETUP ──────────

def make_driver(headless: bool = True):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE")
    driver = uc.Chrome(options=options)
    stealth(driver,
            languages=["de-DE"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris",
            )
    return driver

def click_if_visible(driver, xpath: str) -> None:
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
    except Exception:
        pass

# ────────── PAGE HELPERS ──────────

def collect_links_on_page(driver, url: str) -> set[str]:
    driver.get(url)
    if not collect_links_on_page.cookie_clicked:
        click_if_visible(driver, '//button[contains(.,"Alle akzeptieren") or contains(.,"Alles akzeptieren")]')
        collect_links_on_page.cookie_clicked = True
    human_delay()

    links: set[str] = set()
    prev = -1
    while True:
        cards = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="list-item"]')
        if len(cards) == prev:
            break
        prev = len(cards)
        for c in cards:
            try:
                href = c.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                if href:
                    links.add(href.split("?")[0])
            except Exception:
                pass
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        human_delay()
    return links
collect_links_on_page.cookie_clicked = False


def extract_details(driver, url: str):
    """Return a CSV row list or None; never raises."""
    try:
        driver.get(url)
        human_delay(0.45, 0.90)
        m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', driver.page_source)
        if not m:
            return None
        listing = json.loads(m.group(1))["props"]["pageProps"]["listingDetails"]
        v, p = listing.get("vehicle", {}), listing.get("price", {})
        return [
            " ".join(filter(None, (v.get("make", ""), v.get("model", ""), v.get("modelVersionInput", "")))),
            p.get("priceFormatted", ""),
            v.get("mileageInKmRaw", ""),
            v.get("fuelCategory", {}).get("formatted", ""),
            v.get("powerInKw", ""),
            v.get("rawData", {}).get("engine", {}).get("transmissionType", {}).get("formatted", ""),
            v.get("firstRegistrationDate", ""),
            listing.get("seller", {}).get("type", ""),
            Soup((listing.get("description") or ""), "lxml").get_text(" ", strip=True),
            url,
        ]
    except Exception as e:
        print(f"   ⚠️  skipped {url} — {e}")
        return None

# ────────── RESUME SUPPORT ──────────
# Set START_FROM_IDX to the 1-based index printed in the log where you want
# to resume. Example: log shows "[28/67]" → START_FROM_IDX = 28.
# Use 1 to start from the beginning.
START_FROM_IDX = 28  # ⇦ CHANGE HERE when you need to resume

# ────────── MAIN ──────────

def main():
    print("➜ Loading ZIP coordinates & enforcing ≥", MIN_DISTANCE_KM, "km spacing …")
    zips = load_unique_zip_rows(CSV_ZIPCODES, ZIP_LIMIT)
    total_zips = len(zips)

    # slice the list so we resume
    zips = zips[START_FROM_IDX - 1:]
    print(f"   {len(zips):,} coordinates left after filtering")

    driver = make_driver(HEADLESS)
    header = ["car_name", "price", "mileage_km", "fuel", "power_kw", "transmission",
              "first_registration", "seller_type", "description", "url"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for idx, (zip_code, lat, lon) in enumerate(zips, 1):
            base_first = BASE_MASK.format(lat=lat, lon=lon, zip=quote_plus(zip_code))
            print(f"\n🔍  [{idx}/{len(zips)}] ZIP {zip_code}  lat={lat} lon={lon}  url={base_first}")

            zip_links = collect_links_on_page(driver, base_first)
            human_delay(0.6, 1.1)

            parsed = urlparse(driver.current_url)
            qs = parse_qs(parsed.query)
            qs.setdefault("page", ["1"])
            def page_url(p: int):
                qs["page"] = [str(p)]
                return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

            for page in range(2, MAX_PAGES + 1):
                new = collect_links_on_page(driver, page_url(page)) - zip_links
                if not new:
                    print(f"   stop at page {page}")
                    break
                zip_links.update(new)
                print(f"   +{len(new):4} (zip total {len(zip_links)})")
                human_delay(0.7, 1.3)

            for n, url in enumerate(zip_links, 1):
                row = extract_details(driver, url)
                if row:
                    writer.writerow(row)
                    f.flush(); os.fsync(f.fileno())
                    print(f"✓ {n:>5}/{len(zip_links)}  {row[0][:55]}")
                human_delay(0.2, 0.4)
            f.flush()
            print(f"   ZIP {zip_code} done → {len(zip_links)} listings written")

    driver.quit()
    print(f"🎉 Completed — data saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            driver.quit()
        except Exception:
            pass
