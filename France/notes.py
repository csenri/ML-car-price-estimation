from selenium import webdriver
from selenium.webdriver.common.keys import Keys # if I need to search inside the page
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Crea un'istanza del browser (Chrome in questo caso)
driver = webdriver.Chrome()

# Vai al sito desiderato
driver.get("https://www.subito.it")
print(driver.title)

search = driver.find_element(By.NAME, "main-keyword-field")  # Trova il campo di ricerca
search.send_keys("trattore")  # qui inserisci l'elemento da cercare in quello che hai trovato nel search
search.send_keys(Keys.RETURN)  # poi preme invio per cercare
#print(driver.page_source) # stampa html della pagina


# to wait for the page to load and the element to be present
try:
    # name of our driver, how many seconds to wait
    time.sleep(5)  # Attendi che la pagina si carichi completamente
    main = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "ItemListContainer_container__D_wWL"))
    )
    articles  = main.find_elements(By.CLASS_NAME, "items__item item-card item-card--big BigCard-module_card__Exzqv")  # Trova gli articoli nella lista
    # now in the main I have at least one element of the list of items
    # need to iterate through all of them )
    for article in articles:
        title = article.find_element(By.CLASS_NAME, "headline-6 ItemTitle-module_item-title__VuKDo BigCard-module_card-title__Cgcnt").text  # Trova il titolo dell'articolo
        print(title)
except:
    driver.quit()

  # Stampa il testo dell'elemento principale
print(main.text)
# Chiudi il browser
driver.quit()