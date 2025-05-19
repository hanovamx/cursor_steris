import pandas as pd

def analyze_excel(file_path):
    print(f"\n{'='*50}")
    print(f"Analyzing: {file_path}")
    print('='*50)
    
    # Read the Excel file
    df = pd.read_excel(file_path)
    
    # Print basic information
    print("\nDataFrame Info:")
    print(df.info())
    
    print("\nFirst few rows:")
    print(df.head())
    
    print("\nColumn names:")
    print(df.columns.tolist())
    
    print("\nData types:")
    print(df.dtypes)
    
    print("\nBasic statistics:")
    print(df.describe())

# Analyze each Excel file
files = [
    "data/XLSX1_product_database.xlsx",
    "data/XLSX2_po_template.xlsx",
    "data/XLSX3_customer_database.xlsx",
    "data/main_template.xlsx"
]

for file in files:
    try:
        analyze_excel(file)
    except Exception as e:
        print(f"Error analyzing {file}: {str(e)}") 