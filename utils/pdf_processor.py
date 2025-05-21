import io
import re
import json
from PIL import Image
from openai import OpenAI
from typing import List, Dict, Optional
import base64

def is_product_incomplete(product: dict) -> bool:
    required_fields = ["description", "quantity", "unit", "unit_price"]
    for f in required_fields:
        v = product.get(f)
        if v is None or str(v).strip().lower() in ('', 'none', 'n/a'):
            return True
    return False

def extract_products_openai(pdf_bytes: bytes, api_key: str) -> Optional[Dict]:
    client = OpenAI(api_key=api_key)
    # Convert first page of PDF to image using PIL (if possible)
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
        image = images[0]
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        image_content = {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
    except Exception:
        # If pdf2image is not available, just send the PDF bytes as is (OpenAI may still process it)
        image_content = {"type": "file", "file": pdf_bytes}
    prompt = """
Please analyze this purchase order document and extract all products in the following JSON format:
{
  "products": [
    {
      "position": "string",        // Position number in the document
      "material": "string",        // Material code or reference
      "description": "string",     // Product description
      "quantity": number,          // Quantity ordered
      "unit": "string",           // Unit of measurement (e.g., "PZA C/1")
      "unit_price": number,       // Price per unit
      "total": number,            // Total price for the line
      "confidence": number,       // Confidence score of the extraction (0-1)
      "raw_text": "string"        // Original text extracted for reference
    }
  ]
}
The document contains product information including position numbers, material codes, descriptions, quantities, units, and prices. Please extract this information accurately, maintaining the numerical values and units as they appear in the document.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured data from purchase orders. You are very accurate and precise in your extractions."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    image_content
                ]}
            ],
            max_tokens=1024,
            response_format={ "type": "json_object" }
        )
        text = response.choices[0].message.content
        return json.loads(text)
    except Exception as e:
        print(f"Error in OpenAI extraction: {e}")
        return None

def process_pdf(pdf_file: bytes, api_key: str) -> List[Dict]:
    from app import extract_products_from_pdf
    try:
        products = extract_products_from_pdf(io.BytesIO(pdf_file))
        complete_products = [p for p in products if not is_product_incomplete(p)]
        if complete_products:
            return complete_products
    except Exception as e:
        print(f"PyPDF2 extraction failed: {e}")
    # Fallback to OpenAI Vision
    products_json = extract_products_openai(pdf_file, api_key)
    products = products_json.get("products", []) if products_json else []
    return products 