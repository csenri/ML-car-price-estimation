import pandas as pd
import glob
import os

# Trova tutti i CSV nella cartella regions
file_list = glob.glob("./regions/*.csv")

df_list = []

for file in file_list:
    # Estrai il nome della regione dal nome del file
    nome_file = os.path.basename(file)  # es: subito_cars_abruzzo.csv
    regione = nome_file.replace("subito_cars_", "").replace(".csv", "")

    # Leggi il CSV
    df = pd.read_csv(file)

    # Aggiungi la colonna 'region'
    df["region"] = regione

    # Aggiungi alla lista
    df_list.append(df)

# Unisci tutti i DataFrame
df_totale = pd.concat(df_list, ignore_index=True)

# Mostra le prime righe
print(df_totale.head())
print("the shape of the dataframe is: ", df_totale.shape)