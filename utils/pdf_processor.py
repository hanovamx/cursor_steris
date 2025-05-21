import io
import re
import json
import numpy as np
from PIL import Image
import pytesseract
import easyocr
from openai import OpenAI
from pdf2image import convert_from_bytes
from typing import List, Dict, Union, Optional
import base64

def pdf_to_images(pdf_file: bytes) -> List[Image.Image]:
    """Convert PDF bytes to a list of PIL Images."""
    return convert_from_bytes(pdf_file)

def extract_with_pytesseract(image: Image.Image) -> str:
    """Extract text from image using pytesseract."""
    return pytesseract.image_to_string(image, lang='spa+eng')

def extract_with_easyocr(image: Image.Image) -> str:
    """Extract text from image using easyocr."""
    reader = easyocr.Reader(['es', 'en'])
    result = reader.readtext(np.array(image), detail=0, paragraph=True)
    return "\n".join(result)

def is_text_valid_for_extraction(text: str) -> bool:
    """
    Heuristic to check if OCR result is likely good enough for regex extraction.
    Returns True if the text seems to contain product information.
    """
    lines = text.split('\n')
    # Check for common patterns in purchase orders
    has_product_codes = any(re.search(r'\d{5,}', l) for l in lines)  # Look for product codes
    has_quantities = any(re.search(r'\d+\s+[A-Z]+\s*C/\d+', l) for l in lines)  # Look for quantities and units
    has_prices = any(re.search(r'[\d.,]+\s*€|\$|MXN', l) for l in lines)  # Look for prices with currency
    
    return len(lines) > 10 and (has_product_codes or has_quantities or has_prices)

def encode_image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_products_openai(image: Image.Image, api_key: str) -> Optional[Dict]:
    """Send image to OpenAI GPT-4o model for structured extraction."""
    client = OpenAI(api_key=api_key)
    
    # Convert image to base64
    base64_image = encode_image_to_base64(image)
    
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
            model="gpt-4o",  # Using the GPT-4o model
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts structured data from purchase orders. You are very accurate and precise in your extractions."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1024,
            response_format={ "type": "json_object" }
        )
        
        # Extract JSON from response
        text = response.choices[0].message.content
        return json.loads(text)
    except Exception as e:
        print(f"Error in OpenAI extraction: {e}")
        return None

def is_product_incomplete(product: dict) -> bool:
    # Require all of these fields to be present and non-empty/non-None
    required_fields = ["description", "quantity", "unit", "unit_price"]
    for f in required_fields:
        v = product.get(f)
        if v is None or str(v).strip().lower() in ('', 'none', 'n/a'):
            return True
    return False

def process_pdf(pdf_file: bytes, api_key: str) -> List[Dict]:
    """
    Try PyPDF2+regex first. If no products, or only incomplete products, try EasyOCR, then OpenAI GPT-4o as last resort.
    """
    all_products = []
    from app import extract_products_from_pdf
    # Try PyPDF2+regex first
    try:
        products = extract_products_from_pdf(io.BytesIO(pdf_file))
        # Filter out incomplete products
        complete_products = [p for p in products if not is_product_incomplete(p)]
        if complete_products:
            return complete_products
    except Exception as e:
        print(f"PyPDF2 extraction failed: {e}")
    # Convert PDF to images
    images = pdf_to_images(pdf_file)
    for idx, image in enumerate(images):
        # Try EasyOCR
        text = extract_with_easyocr(image)
        if is_text_valid_for_extraction(text):
            products = extract_products_from_pdf(text)
            complete_products = [p for p in products if not is_product_incomplete(p)]
            if complete_products:
                all_products.extend(complete_products)
                continue
        # Fall back to OpenAI
        if api_key:
            products_json = extract_products_openai(image, api_key)
            products = products_json.get("products", []) if products_json else []
            all_products.extend(products)
    return all_products 