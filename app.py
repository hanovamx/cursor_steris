import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import re
from pathlib import Path
from fuzzywuzzy import process
from utils.template_filler import fill_po_template

# Constantes
PRODUCT_DB_PATH = "data/XLSX1_product_database.xlsx"
CUSTOMER_DB_PATH = "data/XLSX3_customer_database.xlsx"
PO_TEMPLATE_PATH = "data/main_template.xlsx"

# Umbral para coincidencia difusa
description_threshold = 80

def load_databases():
    """Cargar bases de datos de productos y clientes, eliminando espacios en los encabezados"""
    products = pd.read_excel(PRODUCT_DB_PATH)
    products.columns = products.columns.str.strip()
    customers = pd.read_excel(CUSTOMER_DB_PATH)
    customers.columns = customers.columns.str.strip()
    return products, customers

def extract_products_from_pdf(pdf_file):
    products = []
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    lines = []
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            # Clean up: remove empty lines
            lines.extend([l for l in text.split('\n') if l.strip()])
    i = 0
    while i < len(lines):
        first_line = lines[i].strip()
        m1 = re.match(r'^(\d+)\s+(\d+)\s+(.+)$', first_line)
        m2 = None
        if i + 1 < len(lines):
            second_line = lines[i+1].strip()
            m2 = re.match(r'^(\d+)\s+([A-Z]+\sC/\d+)\s+([\d.,]+)\s+([\d.,]+)$', second_line)
        if m1 and m2:
            pos = m1.group(1)
            material = m1.group(2)
            description = m1.group(3)
            quantity = int(m2.group(1))
            unit = m2.group(2)
            price_str = m2.group(3).replace('.', '').replace(',', '.')
            total_str = m2.group(4).replace('.', '').replace(',', '.')
            try:
                unit_price = float(price_str)
            except Exception:
                unit_price = None
            try:
                total = float(total_str)
            except Exception:
                total = None
            products.append({
                'position': pos,
                'material': material,
                'description': description,
                'quantity': quantity,
                'unit': unit,
                'unit_price': unit_price,
                'total': total,
                'raw_first': first_line,
                'raw_second': second_line
            })
            i += 2
        elif m1:
            # Try to extract info from the next line, even if not strict pattern
            pos = m1.group(1)
            material = m1.group(2)
            description = m1.group(3)
            quantity = None
            unit = None
            unit_price = None
            total = None
            raw_second = None
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                # Flexible regex: look for quantity, unit, price, total anywhere in the line
                flex = re.match(r'(\d+)\s+([A-Z]+\sC/\d+)?\s*([\d.,]+)?\s*([\d.,]+)?', next_line)
                if flex:
                    try:
                        quantity = int(flex.group(1))
                    except Exception:
                        quantity = None
                    unit = flex.group(2) if flex.group(2) else None
                    try:
                        unit_price = float(flex.group(3).replace('.', '').replace(',', '.')) if flex.group(3) else None
                    except Exception:
                        unit_price = None
                    try:
                        total = float(flex.group(4).replace('.', '').replace(',', '.')) if flex.group(4) else None
                    except Exception:
                        total = None
                    raw_second = next_line
            # If still not enough info, here is where you could call OpenAI for extraction
            products.append({
                'position': pos,
                'material': material,
                'description': description,
                'quantity': quantity,
                'unit': unit,
                'unit_price': unit_price,
                'total': total,
                'raw_first': first_line,
                'raw_second': raw_second
            })
            i += 2 if raw_second else 1
        else:
            i += 1
    return products

def match_products(customer_products, product_db):
    matched_products = []
    for product in customer_products:
        if product['unit_price'] is None:
            matched_products.append({
                **product,
                'matched_code': None,
                'matched_name': product['description'],
                'matched_unit': product['unit'],
                'match_type': 'No encontrado'
            })
            continue
        matches = product_db[product_db['Precio unitario 2025 SIN IVA'] == product['unit_price']]
        if not matches.empty:
            matched_product = matches.iloc[0]
            matched_products.append({
                **product,
                'matched_code': matched_product['Código'],
                'matched_name': matched_product['Concepto'],
                'matched_unit': matched_product['Unidad'],
                'match_type': 'Precio exacto'
            })
        else:
            choices = product_db['Concepto'].tolist()
            best_match, score = process.extractOne(product['description'], choices)
            if score >= description_threshold:
                matched_row = product_db[product_db['Concepto'] == best_match].iloc[0]
                matched_products.append({
                    **product,
                    'matched_code': matched_row['Código'],
                    'matched_name': matched_row['Concepto'],
                    'matched_unit': matched_row['Unidad'],
                    'match_type': f'Fuzzy ({score})'
                })
            else:
                matched_products.append({
                    **product,
                    'matched_code': None,
                    'matched_name': product['description'],
                    'matched_unit': product['unit'],
                    'match_type': 'No encontrado'
                })
    return matched_products

def generate_po(matched_products, customer_info, template_path):
    output_path, po_number = fill_po_template(template_path, matched_products, customer_info)
    return output_path

def main():
    st.set_page_config(page_title="Generador de Orden de Compra", layout="wide")
    st.title("Generador de Orden de Compra")
    st.write("Sube el PDF de la orden del cliente y revisa los productos identificados.")

    products, customers = load_databases()
    archivo_pdf = st.file_uploader("Subir Orden de Compra del Cliente (PDF)", type=['pdf'])

    if archivo_pdf:
        productos_cliente = extract_products_from_pdf(archivo_pdf)
        if productos_cliente:
            st.success(f"{len(productos_cliente)} productos encontrados en el PDF.")
            productos_conciliados = match_products(productos_cliente, products)
            cliente = st.selectbox("Selecciona el cliente", customers['Unidades Maduras'].tolist())
            st.subheader("Productos identificados y conciliados")
            for idx, producto in enumerate(productos_conciliados):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"<div style='font-size:13px'><b>Extraído del PDF de cliente</b><br>"
                        f"Posición: {producto['position']}<br>"
                        f"Material: {producto['material']}<br>"
                        f"Descripción: {producto['description']}<br>"
                        f"Cantidad: {producto['quantity']}<br>"
                        f"Unidad: {producto['unit']}<br>"
                        f"Precio unitario: {producto['unit_price'] if producto['unit_price'] is not None else 'N/A'}<br>"
                        f"Total: {producto['total'] if producto['total'] is not None else 'N/A'}<br>"
                        f"</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<div style='font-size:13px'><b>Coincidencia en base de datos Steris</b><br>"
                        f"Código: {producto['matched_code'] if producto['matched_code'] else 'N/A'}<br>"
                        f"Nombre: {producto['matched_name']}<br>"
                        f"Unidad: {producto['matched_unit']}<br>"
                        f"</div>", unsafe_allow_html=True)
                st.markdown("<hr style='margin:8px 0'>", unsafe_allow_html=True)
            if st.button("Generar Orden de Compra"):
                info_cliente = customers[customers['Unidades Maduras'] == cliente].iloc[0]
                po_path = generate_po(productos_conciliados, info_cliente, PO_TEMPLATE_PATH)
                st.success("¡Orden de compra generada exitosamente!")
                with open(po_path, 'rb') as f:
                    st.download_button(
                        "Descargar Orden de Compra",
                        f,
                        file_name=po_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

if __name__ == "__main__":
    main() 