import csv
import time
import random

from stem import Signal
from stem.control import Controller

import undetected_chromedriver as uc
from fake_useragent import UserAgent
from selenium_stealth import stealth
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURAZIONE TOR ---
TOR_SOCKS_HOST       = "127.0.0.1"
TOR_SOCKS_PORT       = 9050
TOR_CONTROL_PORT     = 9051
CONTROL_PASSWORD     = "laTuaPwSegreta"  # ← sostituisci con la tua password in chiaro

# --- CONFIGURAZIONE SCRAPER ---
INPUT_ZIPS_CSV = 'FranceZips.csv'
OUTPUT_CSV      = 'DataFrance.csv'
DELAY_MIN       = 0.1
DELAY_MAX       = 0.2
TIMEOUT         = 10   # secondi per WebDriverWait
MAX_RETRIES     = 3    # quante volte riprovo pagina se bloccato

# --- FUNZIONI UTILI ---
def renew_tor_identity():
    """Invia NEWNYM a Tor per cambiare IP."""
    with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
        ctrl.authenticate(password=CONTROL_PASSWORD)
        ctrl.signal(Signal.NEWNYM)
    # attendo nuovo circuito
    time.sleep(5)

def human_delay(a=DELAY_MIN, b=DELAY_MAX):
    time.sleep(random.uniform(a, b))

def human_scroll(driver):
    h = driver.execute_script("return document.body.scrollHeight")
    y = random.randint(100, max(100, h // 2))
    driver.execute_script(f"window.scrollTo(0, {y});")
    human_delay(0.2, 0.5)

def safe_text(driver, selector):
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text.strip()
    except:
        return 'NOTFOUND'

def is_blocked(driver):
    """Rileva se siamo finiti sul CAPTCHA/puzzle."""
    src = driver.page_source.lower()
    return 'captcha' in src or 'puzzle' in src or 'slider' in src

# --- SETUP CHROME STEALTH VIA TOR SOCKS5 ---
ua = UserAgent().random
options = uc.ChromeOptions()
options.add_argument(f"--user-agent={ua}")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(f"--proxy-server=socks5://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}")
# options.add_argument("--headless=new")  # se vuoi provare headless

driver = uc.Chrome(options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.navigator.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['it-IT','it']});
"""})
stealth(driver,
    languages=["it-IT","it"],
    vendor="Google Inc.",
    platform="Win32",
    webgl_vendor="Intel Inc.",
    renderer="Intel Iris OpenGL Engine",
    fix_hairline=True,
)

wait = WebDriverWait(driver, TIMEOUT)

# --- CARICA ZIP CODES ---
zip_codes = []
with open(INPUT_ZIPS_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        zip_codes.append(row['zip_code'])

# --- PREPARA OUTPUT CSV ---
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as out_f:
    fieldnames = ['zip_code','title','price','year','km','fuel','power','gearbox','color']
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    writer.writeheader()

    # --- MAIN LOOP ---
    for zip_code in zip_codes:
        page = 1
        while True:
            url = (
                f"https://www.lacentrale.fr/listing"
                f"?distance=4&dptCp={zip_code}&options=&page={page}"
            )

            # tentativo multiplo se bloccato
            for attempt in range(1, MAX_RETRIES+1):
                driver.get(url)
                human_delay()
                human_scroll(driver)

                if is_blocked(driver):
                    print(f"[!] Bloccato su ZIP {zip_code} page {page}, renew tor (tentativo {attempt})")
                    renew_tor_identity()
                    continue
                break
            else:
                print(f"[x] Saltata ZIP {zip_code} page {page} dopo {MAX_RETRIES} blocchi")
                break

            # recupera le card
            try:
                cards = wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div.AdCard')
                ))
            except:
                break
            if not cards:
                break

            # processa ogni annuncio
            for card in cards:
                try:
                    link = card.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                except:
                    continue

                driver.execute_script("window.open(arguments[0]);", link)
                driver.switch_to.window(driver.window_handles[-1])
                human_delay()
                human_scroll(driver)

                title = safe_text(driver, 'h1.adlisting-title')
                price = safe_text(driver, '.jsRefinedQuotPrice')
                details = {}
                for li in driver.find_elements(By.CSS_SELECTOR, 'ul.adParams li'):
                    text = li.text
                    if 'Année-modèle'       in text: details['year']    = text.split('\n')[-1]
                    elif 'Kilométrage'       in text: details['km']      = text.split('\n')[-1]
                    elif 'Carburant'         in text: details['fuel']    = text.split('\n')[-1]
                    elif 'Puissance fiscale' in text: details['power']   = text.split('\n')[-1]
                    elif 'Boîte de vitesses' in text: details['gearbox'] = text.split('\n')[-1]
                    elif 'Couleur'           in text: details['color']   = text.split('\n')[-1]

                writer.writerow({
                    'zip_code': zip_code,
                    'title':     title,
                    'price':     price,
                    'year':      details.get('year',    'NOTFOUND'),
                    'km':        details.get('km',      'NOTFOUND'),
                    'fuel':      details.get('fuel',    'NOTFOUND'),
                    'power':     details.get('power',   'NOTFOUND'),
                    'gearbox':   details.get('gearbox', 'NOTFOUND'),
                    'color':     details.get('color',   'NOTFOUND'),
                })

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                human_delay()

            page += 1

driver.quit()
print(f"✅ Fatto! Dati salvati in `{OUTPUT_CSV}`")