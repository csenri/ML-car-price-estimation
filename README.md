# ML Car Price Estimation

This project aims to estimate car prices using machine learning, based on data scraped from popular European car listing websites. The workflow includes web scraping, data preprocessing, exploratory data analysis, model training, and evaluation.

## Project Structure

```
ML-car-price-estimation/
├── data/                # Raw and processed data
│   └── raw-data/
|   └── cleaned-daata/
├── notebooks/           # Jupyter notebooks for EDA and experiments
│   └── data_analysis.ipynb
├── src/                 # Source code
│   ├── scraping/        # Web scraping scripts
│   ├── preprocessing/   # Data cleaning and feature engineering
│   ├── modeling/        # Model training and evaluation
│   └── utils/           # Helper functions
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Data Sources

Car data is scraped from the following websites:

- AutoScout24 (Europe): https://www.autoscout24.com  
- Mobile.de (Germany): https://www.mobile.de  
- CarGurus (UK): https://www.cargurus.co.uk  
- CarNext (Europe): https://www.carnext.com  
- AutoUncle (Europe): https://www.autouncle.com  
- CarVertical (Europe): https://www.carvertical.com  
- Bilbasen (Denmark): https://www.bilbasen.dk  
- La Centrale (France): https://www.lacentrale.fr  
- Leboncoin (France): https://www.leboncoin.fr/voitures/  
- Marktplaats (Netherlands): https://www.marktplaats.nl/l/auto-s/  
- Autoscout24.nl (Netherlands): https://www.autoscout24.nl  
- Subito.it (Italy): https://www.subito.it/annunci-italia/vendita/auto/  

## Workflow

1. **Web Scraping:** Collect car listings and features from the above sources.
2. **Data Preprocessing:** Clean and structure the data for analysis.
3. **Exploratory Data Analysis:** Understand feature distributions and relationships.
4. **Modeling:** Train machine learning models to predict car prices.
5. **Evaluation:** Assess model performance and refine as needed.

## Getting Started

1. Clone the repository.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the scraping scripts in `src/scraping/` to collect data.
4. Follow the notebooks in `notebooks/` for data analysis and modeling.

## License

This project is for educational purposes.