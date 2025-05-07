import os
import json
import base64
import logging
from datetime import datetime
import re
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

class OpenAIInvoiceProcessor:
    """
    Class for processing invoice images with OpenAI Vision API and extracting structured data
    """
    def __init__(self, app=None):
        self.app = app
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self.upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Ensure upload folder exists
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def encode_image_to_base64(self, image_path):
        """Convert image to base64 for OpenAI API"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def process_invoice_image(self, image_path):
        """
        Process an invoice image using OpenAI Vision API
        Returns a dict with extracted fields and confidence values
        """
        logger.info(f"Processing invoice image with OpenAI: {image_path}")
        
        try:
            # Encode the image to base64
            base64_image = self.encode_image_to_base64(image_path)
            
            # Create the prompt for invoice data extraction
            system_prompt = """
            You are an expert invoice data extractor. Analyze the invoice image carefully and extract the following details:
            
            1. Vendor information (name, GSTIN, address)
            2. Customer information (name, GSTIN, address)
            3. Invoice details (number, date, due date, PO number)
            4. Line items (description, HSN/SAC code, quantity, rate, tax percentage, tax amount, amount)
            5. Financial details (subtotal, tax amount, discount, total amount)
            6. Other details (place of supply, terms)
            
            Format your response as a JSON object with these fields. Use the following structure:
            {
              "vendor": {
                "name": "Vendor Name", 
                "gstin": "GSTIN Number",
                "address": "Vendor Address"
              },
              "customer": {
                "name": "Customer Name",
                "gstin": "GSTIN Number",
                "address": "Customer Address"
              },
              "invoice_number": "INV-12345",
              "invoice_date": "YYYY-MM-DD",
              "due_date": "YYYY-MM-DD",
              "po_number": "PO-12345",
              "place_of_supply": "Place",
              "line_items": [
                {
                  "description": "Item description",
                  "hsn_sac": "HSN/SAC code",
                  "quantity": 1,
                  "rate": 100.00,
                  "tax_percentage": 18,
                  "tax_amount": 18.00,
                  "amount": 118.00
                }
              ],
              "subtotal": 100.00,
              "tax_amount": 18.00,
              "discount": 0.00,
              "total_amount": 118.00,
              "terms": "Payment terms"
            }
            
            If you can't find a value, use null. Be very precise and extract the exact values as they appear on the invoice.
            For numeric fields (quantity, rate, tax_percentage, tax_amount, amount, subtotal, discount, total_amount), 
            ensure they are numeric values, not strings.
            """
            
            logger.info("Sending request to OpenAI API")
            
            # Call OpenAI API with the image
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": "Extract all invoice data from this image as a structured JSON."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=4000
            )
            
            logger.info("Received response from OpenAI API")
            
            # Get the JSON content from the response
            content = response.choices[0].message.content
            logger.info(f"OpenAI response content: {content[:200]}...")  # Log first 200 chars to avoid huge logs
            
            # Extract and parse the structured data
            result_json = json.loads(content)
            logger.info(f"Parsed JSON keys: {list(result_json.keys())}")
            
            # Process the result into our expected format
            extracted_data = self.process_openai_response(result_json)
            
            # Log some key fields for debugging
            if extracted_data:
                vendor_name = extracted_data.get('vendor', {}).get('name')
                invoice_num = extracted_data.get('invoice_number')
                line_items_count = len(extracted_data.get('line_items', []))
                logger.info(f"Extracted: Vendor={vendor_name}, Invoice={invoice_num}, Items={line_items_count}")
            
            logger.info(f"Successfully processed invoice image with OpenAI: {image_path}")
            return extracted_data
            
        except Exception as e:
            logger.exception(f"Error processing invoice image with OpenAI {image_path}: {str(e)}")
            raise
    
    def process_openai_response(self, openai_data):
        """
        Process OpenAI's response into our standard format
        """
        # Default result structure
        extracted_data = {
            'vendor': {'name': None, 'gstin': None, 'address': None},
            'customer': {'name': None, 'gstin': None, 'address': None},
            'invoice_number': None,
            'invoice_date': None,
            'due_date': None,
            'po_number': None,
            'place_of_supply': None,
            'line_items': [],
            'subtotal': None,
            'tax_amount': None,
            'discount': 0.0,
            'total_amount': None,
            'terms': 'Immediate',
            'ocr_confidence': 95.0  # OpenAI generally has high confidence
        }
        
        # Map OpenAI response to our structure
        try:
            # Vendor information
            if 'vendor' in openai_data:
                vendor = openai_data['vendor']
                if isinstance(vendor, dict):
                    extracted_data['vendor']['name'] = vendor.get('name')
                    extracted_data['vendor']['gstin'] = vendor.get('gstin')
                    extracted_data['vendor']['address'] = vendor.get('address')
                elif isinstance(vendor, str):
                    extracted_data['vendor']['name'] = vendor
            
            # Customer information
            if 'customer' in openai_data:
                customer = openai_data['customer']
                if isinstance(customer, dict):
                    extracted_data['customer']['name'] = customer.get('name')
                    extracted_data['customer']['gstin'] = customer.get('gstin')
                    extracted_data['customer']['address'] = customer.get('address')
                elif isinstance(customer, str):
                    extracted_data['customer']['name'] = customer
            
            # Invoice details
            extracted_data['invoice_number'] = openai_data.get('invoice_number')
            
            # Handle date formats
            if 'invoice_date' in openai_data and openai_data['invoice_date']:
                try:
                    # Try to parse and standardize the date format
                    date_str = openai_data['invoice_date']
                    # Handle common date formats
                    if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', date_str):  # MM/DD/YYYY or DD/MM/YYYY
                        parts = date_str.split('/')
                        if len(parts[2]) == 2:  # Two-digit year
                            parts[2] = '20' + parts[2]  # Assume 2000s
                        date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                    elif re.match(r'\d{1,2}-\d{1,2}-\d{2,4}', date_str):  # DD-MM-YYYY
                        parts = date_str.split('-')
                        if len(parts[2]) == 2:  # Two-digit year
                            parts[2] = '20' + parts[2]  # Assume 2000s
                        date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    # Use the standardized date
                    extracted_data['invoice_date'] = date_str
                except Exception as e:
                    logger.warning(f"Failed to parse invoice date: {openai_data['invoice_date']} - {str(e)}")
                    extracted_data['invoice_date'] = openai_data['invoice_date']
            
            if 'due_date' in openai_data and openai_data['due_date']:
                try:
                    # Try to parse and standardize the date format
                    date_str = openai_data['due_date']
                    # Handle common date formats
                    if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', date_str):  # MM/DD/YYYY or DD/MM/YYYY
                        parts = date_str.split('/')
                        if len(parts[2]) == 2:  # Two-digit year
                            parts[2] = '20' + parts[2]  # Assume 2000s
                        date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                    elif re.match(r'\d{1,2}-\d{1,2}-\d{2,4}', date_str):  # DD-MM-YYYY
                        parts = date_str.split('-')
                        if len(parts[2]) == 2:  # Two-digit year
                            parts[2] = '20' + parts[2]  # Assume 2000s
                        date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    # Use the standardized date
                    extracted_data['due_date'] = date_str
                except Exception as e:
                    logger.warning(f"Failed to parse due date: {openai_data['due_date']} - {str(e)}")
                    extracted_data['due_date'] = openai_data['due_date']
            
            extracted_data['po_number'] = openai_data.get('po_number')
            extracted_data['place_of_supply'] = openai_data.get('place_of_supply')
            
            # Line items
            if 'line_items' in openai_data and isinstance(openai_data['line_items'], list):
                for item in openai_data['line_items']:
                    line_item = {
                        'description': item.get('description'),
                        'hsn_sac': item.get('hsn_sac'),
                        'quantity': float(item.get('quantity', 0)),
                        'rate': float(item.get('rate', 0)),
                        'tax_percentage': float(item.get('tax_percentage', 0)),
                        'tax_amount': float(item.get('tax_amount', 0)),
                        'amount': float(item.get('amount', 0))
                    }
                    extracted_data['line_items'].append(line_item)
            
            # Financial details
            if 'subtotal' in openai_data:
                extracted_data['subtotal'] = float(openai_data['subtotal']) if openai_data['subtotal'] else None
            
            if 'tax_amount' in openai_data:
                extracted_data['tax_amount'] = float(openai_data['tax_amount']) if openai_data['tax_amount'] else None
            
            if 'discount' in openai_data:
                extracted_data['discount'] = float(openai_data['discount']) if openai_data['discount'] else 0.0
            
            if 'total_amount' in openai_data:
                extracted_data['total_amount'] = float(openai_data['total_amount']) if openai_data['total_amount'] else None
            
            # Other details
            if 'terms' in openai_data:
                extracted_data['terms'] = openai_data['terms']
            
        except Exception as e:
            logger.exception(f"Error processing OpenAI response: {str(e)}")
        
        return extracted_data