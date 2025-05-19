# PO Generator

A Streamlit application that automates the generation of purchase orders from customer PDFs.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure your data files are in the correct location:
- `data/XLSX1_product_database.xlsx` - Product database
- `data/XLSX2_po_template.xlsx` - PO template
- `data/XLSX3_customer_database.xlsx` - Customer database

## Usage

1. Run the Streamlit app:
```bash
streamlit run app.py
```

2. Upload a customer PO in PDF format
3. Select the customer from the dropdown
4. Review the matched products
5. Click "Generate PO" to create and download the purchase order

## Features

- PDF parsing for customer POs
- Product matching by price
- Customer selection from database
- PO generation using template
- Download generated POs

## File Structure

```
po_generator/
├── app.py              # Main Streamlit application
├── utils/
│   ├── __init__.py
│   └── template_filler.py  # PO template handling
├── data/              # Data files
│   ├── XLSX1_product_database.xlsx
│   ├── XLSX2_po_template.xlsx
│   └── XLSX3_customer_database.xlsx
├── generated_pos/     # Generated POs will be saved here
├── requirements.txt
└── README.md
``` 