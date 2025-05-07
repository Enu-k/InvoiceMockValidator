import os
import logging
import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ocr_processor import InvoiceOCRProcessor
from field_validator import InvoiceFieldValidator
from models import db, Invoice, InvoiceLineItem, Company, Item, ProcessingJob

# Initialize blueprint
api_bp = Blueprint('api', __name__)

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize processors
ocr_processor = InvoiceOCRProcessor()
field_validator = InvoiceFieldValidator()

# Initialize processors with app in a function that can be called from app.py
def setup_processors(app):
    """Set up processors with Flask app"""
    ocr_processor.init_app(app)
    field_validator.init_app(app)

@api_bp.route('/upload', methods=['POST'])
def upload_invoice():
    """
    Upload an invoice image/PDF for OCR processing
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'tiff', 'tif'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid file type. Allowed types: png, jpg, jpeg, pdf, tiff, tif'}), 400
    
    try:
        # Save file
        file_path = ocr_processor.save_uploaded_file(file)
        
        # Start OCR processing asynchronously
        job_id = ocr_processor.process_async(file_path)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Invoice uploaded and processing started'
        }), 202
        
    except Exception as e:
        logger.exception(f"Error uploading file: {str(e)}")
        return jsonify({'error': f'Error uploading file: {str(e)}'}), 500

@api_bp.route('/processing/<job_id>', methods=['GET'])
def get_processing_status(job_id):
    """
    Get the status of an OCR processing job
    """
    try:
        job_status = ocr_processor.get_job_status(job_id)
        
        if not job_status:
            return jsonify({'error': 'Job not found'}), 404
            
        return jsonify(job_status), 200
        
    except Exception as e:
        logger.exception(f"Error getting job status: {str(e)}")
        return jsonify({'error': f'Error getting job status: {str(e)}'}), 500

@api_bp.route('/validate-invoice', methods=['POST'])
def validate_invoice():
    """
    Validate extracted invoice data against business rules and master data
    """
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Validate the invoice data
        is_valid, errors = field_validator.validate_invoice(data)
        
        response = {
            'valid': is_valid,
            'errors': errors if not is_valid else None
        }
        
        # Include confidence scores for fields
        if 'ocr_confidence' in data:
            response['ocr_confidence'] = data['ocr_confidence']
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.exception(f"Error validating invoice: {str(e)}")
        return jsonify({'error': f'Error validating invoice: {str(e)}'}), 500

@api_bp.route('/submit-invoice', methods=['POST'])
def submit_invoice():
    """
    Submit validated invoice data to the database
    """
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Validate the invoice first
        is_valid, errors = field_validator.validate_invoice(data)
        
        if not is_valid:
            return jsonify({
                'error': 'Invalid invoice data',
                'validation_errors': errors
            }), 400
            
        # Get vendor and customer by GSTIN
        vendor = Company.query.filter_by(gstin=data['vendor']['gstin']).first()
        customer = Company.query.filter_by(gstin=data['customer']['gstin']).first()
        
        if not vendor or not customer:
            return jsonify({'error': 'Vendor or customer not found in master data'}), 400
            
        # Create new invoice
        invoice = Invoice(
            invoice_number=data['invoice_number'],
            invoice_date=datetime.strptime(data['invoice_date'], '%Y-%m-%d').date(),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            po_number=data.get('po_number'),
            vendor_id=vendor.id,
            customer_id=customer.id,
            place_of_supply=data.get('place_of_supply'),
            subtotal=float(data['subtotal']),
            tax_amount=float(data['tax_amount']),
            discount=float(data.get('discount', 0)),
            total_amount=float(data['total_amount']),
            terms=data.get('terms', 'Immediate'),
            ocr_confidence=float(data.get('ocr_confidence', 0)),
            processing_status='completed',
            notes=data.get('notes')
        )
        
        db.session.add(invoice)
        db.session.flush()  # Get the invoice ID
        
        # Create line items
        for item_data in data['line_items']:
            # Check if item exists in master data
            item = None
            if 'hsn_sac' in item_data:
                item = Item.query.filter_by(hsn_sac=item_data['hsn_sac']).first()
            
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                item_id=item.id if item else None,
                description=item_data['description'],
                hsn_sac=item_data.get('hsn_sac'),
                quantity=float(item_data['quantity']),
                rate=float(item_data['rate']),
                tax_percentage=float(item_data['tax_percentage']),
                tax_amount=float(item_data['tax_amount']),
                amount=float(item_data['amount'])
            )
            db.session.add(line_item)
        
        # Update the processing job with the invoice ID if job_id provided
        if 'job_id' in data:
            job = ProcessingJob.query.filter_by(job_id=data['job_id']).first()
            if job:
                job.invoice_id = invoice.id
                
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice submitted successfully',
            'invoice_id': invoice.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error submitting invoice: {str(e)}")
        return jsonify({'error': f'Error submitting invoice: {str(e)}'}), 500

@api_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """
    Get invoice details by ID
    """
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
            
        return jsonify(invoice.to_dict()), 200
        
    except Exception as e:
        logger.exception(f"Error getting invoice: {str(e)}")
        return jsonify({'error': f'Error getting invoice: {str(e)}'}), 500

@api_bp.route('/invoices', methods=['GET'])
def get_invoices():
    """
    Get all invoices with pagination
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).paginate(page=page, per_page=per_page)
        
        result = {
            'items': [invoice.to_dict() for invoice in invoices.items],
            'page': invoices.page,
            'per_page': invoices.per_page,
            'total': invoices.total,
            'pages': invoices.pages
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.exception(f"Error getting invoices: {str(e)}")
        return jsonify({'error': f'Error getting invoices: {str(e)}'}), 500

@api_bp.route('/companies', methods=['GET'])
def get_companies():
    """
    Get all companies (vendors and customers)
    """
    try:
        companies = Company.query.all()
        return jsonify([company.to_dict() for company in companies]), 200
        
    except Exception as e:
        logger.exception(f"Error getting companies: {str(e)}")
        return jsonify({'error': f'Error getting companies: {str(e)}'}), 500
        
@api_bp.route('/items', methods=['GET'])
def get_items():
    """
    Get all inventory items
    """
    try:
        items = Item.query.all()
        return jsonify([item.to_dict() for item in items]), 200
        
    except Exception as e:
        logger.exception(f"Error getting items: {str(e)}")
        return jsonify({'error': f'Error getting items: {str(e)}'}), 500

@api_bp.route('/test-openai-ocr', methods=['POST'])
def test_openai_ocr():
    """
    Test endpoint to process an invoice with OpenAI directly without async handling
    """
    if 'file' not in request.files:
        logger.error("No file provided in request")
        return jsonify({'error': 'No file provided', 'success': False}), 400
        
    file = request.files['file']
    if file.filename == '':
        logger.error("Empty filename in request")
        return jsonify({'error': 'No file selected', 'success': False}), 400
        
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'tiff', 'tif'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        logger.error(f"Invalid file type: {file.filename}")
        return jsonify({
            'error': 'Invalid file type. Allowed types: png, jpg, jpeg, pdf, tiff, tif',
            'success': False
        }), 400
    
    try:
        # Check if OpenAI API key is configured
        if not os.environ.get("OPENAI_API_KEY"):
            logger.error("OpenAI API key not configured")
            return jsonify({
                'error': 'OpenAI API key not configured. Set the OPENAI_API_KEY environment variable.',
                'success': False
            }), 400

        # Log file info
        logger.info(f"Processing file: {file.filename}, size: {file.content_length or 'unknown'}")
        
        # Save file
        file_path = ocr_processor.save_uploaded_file(file)
        logger.info(f"File saved to: {file_path}")
        
        # Process directly with OpenAI
        from openai_processor import OpenAIInvoiceProcessor
        openai_processor_inst = OpenAIInvoiceProcessor(current_app)
        
        logger.info("Starting OpenAI processing")
        result = openai_processor_inst.process_invoice_image(file_path)
        
        if not result:
            logger.error("Empty result returned from OpenAI processor")
            return jsonify({
                'error': 'Failed to extract data from the invoice',
                'success': False
            }), 500
            
        # Log success details
        logger.info(f"Successfully processed invoice with OpenAI. Extracted fields: {list(result.keys())}")
        
        # Check if we have essential data
        if not result.get('vendor', {}).get('name') or not result.get('invoice_number'):
            logger.warning("Missing essential data in OpenAI results")
            
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Invoice processed with OpenAI Vision API'
        }), 200
        
    except Exception as e:
        logger.exception(f"Error processing with OpenAI: {str(e)}")
        return jsonify({
            'error': f'Error processing with OpenAI: {str(e)}',
            'success': False
        }), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
