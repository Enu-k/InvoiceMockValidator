import os
import uuid
import logging
import time
import json
import re
from datetime import datetime
import pytesseract
from PIL import Image
import cv2
import numpy as np
from openai_processor import OpenAIInvoiceProcessor

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = '/nix/store/44vcjbcy1p2yhc974bcw250k2r5x5cpa-tesseract-5.3.4/bin/tesseract'

# Initialize OpenAI processor
openai_processor = OpenAIInvoiceProcessor()
from werkzeug.utils import secure_filename
from threading import Thread
from flask import current_app
from models import ProcessingJob, db

logger = logging.getLogger(__name__)

class InvoiceOCRProcessor:
    """
    Class for processing invoice images with OCR and extracting structured data
    """
    def __init__(self, app=None):
        self.app = app
        self.confidence_threshold = 80
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self.confidence_threshold = app.config.get('OCR_CONFIDENCE_THRESHOLD', 80)
        self.upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Ensure upload folder exists
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # Initialize OpenAI processor with app
        if openai_processor:
            openai_processor.init_app(app)
    
    def save_uploaded_file(self, file_obj):
        """Save an uploaded file and return the path"""
        if not file_obj:
            return None
            
        filename = secure_filename(file_obj.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(self.upload_folder, unique_filename)
        file_obj.save(file_path)
        return file_path
    
    def process_async(self, file_path):
        """Start asynchronous processing of an invoice image"""
        job_id = str(uuid.uuid4())
        
        # Create a processing job record
        with self.app.app_context():
            job = ProcessingJob(
                job_id=job_id,
                file_path=file_path,
                status="pending"
            )
            db.session.add(job)
            db.session.commit()
        
        # Start processing in a background thread
        thread = Thread(target=self._process_invoice_job, args=(job_id, file_path))
        thread.daemon = True
        thread.start()
        
        return job_id
    
    def _process_invoice_job(self, job_id, file_path):
        """Background task to process an invoice image"""
        with self.app.app_context():
            try:
                # Update job status to processing
                job = ProcessingJob.query.filter_by(job_id=job_id).first()
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return
                
                job.status = "processing"
                db.session.commit()
                
                # Process the invoice
                results = self.process_invoice_image(file_path)
                
                # Update job with results
                job.status = "completed"
                job.result = json.dumps(results)
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
                logger.info(f"Job {job_id} completed successfully")
                
            except Exception as e:
                logger.exception(f"Error processing job {job_id}: {str(e)}")
                
                # Update job with error
                job = ProcessingJob.query.filter_by(job_id=job_id).first()
                if job:
                    job.status = "error"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
    
    def process_invoice_image(self, image_path):
        """
        Process an invoice image and extract structured data
        Returns a dict with extracted fields and confidence scores
        """
        logger.info(f"Processing invoice image: {image_path}")
        
        try:
            # Use OpenAI for processing instead of traditional OCR
            if openai_processor and os.environ.get("OPENAI_API_KEY"):
                logger.info("Using OpenAI Vision API for invoice processing")
                # Initialize OpenAI processor with app
                if self.app and not openai_processor.app:
                    openai_processor.init_app(self.app)
                
                # Process with OpenAI
                extracted_data = openai_processor.process_invoice_image(image_path)
                logger.info(f"Successfully processed invoice image with OpenAI: {image_path}")
                return extracted_data
            else:
                logger.info("OpenAI processing not available, using standard OCR")
                # Load image with OpenCV for preprocessing
                img = cv2.imread(image_path)
                if img is None:
                    raise ValueError(f"Failed to load image from {image_path}")
                
                # Preprocess image for better OCR results
                preprocessed_img = self._preprocess_image(img)
                
                # Convert back to PIL Image for Tesseract
                pil_img = Image.fromarray(preprocessed_img)
                
                # Extract text with Tesseract OCR with additional configuration for structured output
                ocr_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
                ocr_data = pytesseract.image_to_data(pil_img, config=ocr_config, output_type=pytesseract.Output.DICT)
                
                # Extract text with Tesseract OCR
                raw_text = pytesseract.image_to_string(pil_img)
                
                # Process the OCR data to extract structured information
                extracted_data = self._extract_invoice_data(raw_text, ocr_data)
                
                logger.info(f"Successfully processed invoice image with standard OCR: {image_path}")
                return extracted_data
            
        except Exception as e:
            logger.exception(f"Error processing invoice image {image_path}: {str(e)}")
            raise
    
    def _preprocess_image(self, img):
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Apply morphological operations to clean up the image
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return opening
    
    def _extract_invoice_data(self, raw_text, ocr_data):
        """
        Extract structured data from OCR results
        Returns a dict with extracted fields and confidence values
        """
        # Calculate average confidence
        conf_values = [c for c in ocr_data['conf'] if c != -1]
        avg_confidence = sum(conf_values) / len(conf_values) if conf_values else 0
        
        # Split text into lines for processing
        lines = raw_text.split('\n')
        
        # Initialize extracted data dict
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
            'terms': None,
            'ocr_confidence': avg_confidence
        }
        
        # Extract vendor information
        vendor_pattern = re.compile(r'^([A-Za-z0-9\s]+(?:Pvt|Private|Ltd|Limited|Co\.|Corporation|Industries|Technologies|Systems|Components)\s*(?:Ltd|Limited|LLP|Co\.|Corporation)?)', re.IGNORECASE)
        gstin_pattern = re.compile(r'GSTIN:\s*([0-9A-Z]{15})')
        
        # Extract invoice details
        invoice_num_pattern = re.compile(r'Invoice\s*No\s*[.:]\s*(INV-[0-9-]+)', re.IGNORECASE)
        invoice_date_pattern = re.compile(r'Invoice\s*Date\s*[.:]\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
        due_date_pattern = re.compile(r'Due\s*Date\s*[.:]\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
        po_pattern = re.compile(r'P\.?O\.?\s*#?\s*[.:]\s*(PO-[0-9-]+)', re.IGNORECASE)
        
        # Extract billing and shipping information
        bill_to_pattern = re.compile(r'Bill\s*To\s*([A-Za-z0-9\s]+)', re.IGNORECASE)
        ship_to_pattern = re.compile(r'Ship\s*To\s*([A-Za-z0-9\s,]+)', re.IGNORECASE)
        
        # Extract totals
        subtotal_pattern = re.compile(r'Subtotal\s*([0-9,.]+)', re.IGNORECASE)
        tax_pattern = re.compile(r'(?:GST|Tax|IGST)\s*(?:18%|18)\s*([0-9,.]+)', re.IGNORECASE)
        discount_pattern = re.compile(r'Discount\s*\([0-9%]+\)\s*-?([0-9,.]+)', re.IGNORECASE)
        total_pattern = re.compile(r'Total\s*([₹₨]?\s*[0-9,.]+)', re.IGNORECASE)
        
        # Extract line items - this is more complex and depends on the table structure
        item_section = False
        item_rows = []
        
        # Process each line
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                continue
                
            # Look for vendor name at the beginning
            if i < 5 and not extracted_data['vendor']['name']:
                vendor_match = vendor_pattern.search(line)
                if vendor_match:
                    extracted_data['vendor']['name'] = vendor_match.group(1).strip()
                    continue
            
            # Look for GSTIN
            gstin_match = gstin_pattern.search(line)
            if gstin_match and not extracted_data['vendor']['gstin']:
                extracted_data['vendor']['gstin'] = gstin_match.group(1).strip()
                continue
            
            # Invoice number
            invoice_match = invoice_num_pattern.search(line)
            if invoice_match and not extracted_data['invoice_number']:
                extracted_data['invoice_number'] = invoice_match.group(1).strip()
                continue
            
            # Invoice date
            date_match = invoice_date_pattern.search(line)
            if date_match and not extracted_data['invoice_date']:
                extracted_data['invoice_date'] = date_match.group(1).strip()
                continue
            
            # Due date
            due_date_match = due_date_pattern.search(line)
            if due_date_match and not extracted_data['due_date']:
                extracted_data['due_date'] = due_date_match.group(1).strip()
                continue
            
            # PO number
            po_match = po_pattern.search(line)
            if po_match and not extracted_data['po_number']:
                extracted_data['po_number'] = po_match.group(1).strip()
                continue
            
            # Bill To
            bill_match = bill_to_pattern.search(line)
            if bill_match and not extracted_data['customer']['name']:
                extracted_data['customer']['name'] = bill_match.group(1).strip()
                # Look for customer GSTIN in the next few lines
                for j in range(i+1, min(i+5, len(lines))):
                    gstin_match = gstin_pattern.search(lines[j])
                    if gstin_match:
                        extracted_data['customer']['gstin'] = gstin_match.group(1).strip()
                        break
                continue
            
            # Ship To address
            ship_match = ship_to_pattern.search(line)
            if ship_match and not extracted_data['customer']['address']:
                extracted_data['customer']['address'] = ship_match.group(1).strip()
                continue
            
            # Look for place of supply
            if "Place Of Supply" in line and not extracted_data['place_of_supply']:
                pos_parts = line.split(":")
                if len(pos_parts) > 1:
                    extracted_data['place_of_supply'] = pos_parts[1].strip()
                continue
            
            # Check for line items section start
            if re.search(r'#\s*Item\s*&\s*Description|HSN/SAC\s*Qty\s*Rate', line, re.IGNORECASE):
                item_section = True
                continue
            
            # Check for the end of line items section
            if item_section and re.search(r'Subtotal|Total\s*Taxable', line, re.IGNORECASE):
                item_section = False
            
            # Collect line item rows
            if item_section and re.search(r'\d+\s+\S+', line):
                item_rows.append(line.strip())
            
            # Extract totals
            subtotal_match = subtotal_pattern.search(line)
            if subtotal_match and not extracted_data['subtotal']:
                subtotal_str = subtotal_match.group(1).replace(',', '')
                try:
                    extracted_data['subtotal'] = float(subtotal_str)
                except ValueError:
                    pass
                continue
            
            tax_match = tax_pattern.search(line)
            if tax_match and not extracted_data['tax_amount']:
                tax_str = tax_match.group(1).replace(',', '')
                try:
                    extracted_data['tax_amount'] = float(tax_str)
                except ValueError:
                    pass
                continue
            
            discount_match = discount_pattern.search(line)
            if discount_match:
                discount_str = discount_match.group(1).replace(',', '')
                try:
                    extracted_data['discount'] = float(discount_str)
                except ValueError:
                    pass
                continue
            
            total_match = total_pattern.search(line)
            if total_match and not extracted_data['total_amount'] and 'Balance Due' in line:
                total_str = total_match.group(1).replace('₹', '').replace('₨', '').replace(',', '').strip()
                try:
                    extracted_data['total_amount'] = float(total_str)
                except ValueError:
                    pass
                continue
        
        # Process line items
        for row in item_rows:
            # This logic will depend on the specific format of line items in your invoices
            # Using regex to parse line items with a common structure
            item_match = re.search(r'(\d+)\s+([^0-9]+)\s+(\d+)\s+(\d+)\s+([0-9,.]+)\s+(\d+)%\s+([0-9,.]+)\s+([0-9,.]+)', row)
            if item_match:
                try:
                    line_item = {
                        'description': item_match.group(2).strip(),
                        'hsn_sac': item_match.group(3).strip(),
                        'quantity': float(item_match.group(4)),
                        'rate': float(item_match.group(5).replace(',', '')),
                        'tax_percentage': float(item_match.group(6)),
                        'tax_amount': float(item_match.group(7).replace(',', '')),
                        'amount': float(item_match.group(8).replace(',', ''))
                    }
                    extracted_data['line_items'].append(line_item)
                except (ValueError, IndexError):
                    pass
        
        # Set default terms
        extracted_data['terms'] = "Immediate"  # Default observed in sample invoices
        
        return extracted_data
    
    def get_job_status(self, job_id):
        """Get the status of a processing job"""
        with self.app.app_context():
            job = ProcessingJob.query.filter_by(job_id=job_id).first()
            if not job:
                return None
                
            return {
                'status': job.status,
                'error': job.error_message,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'result': json.loads(job.result) if job.result else None
            }
