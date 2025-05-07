import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from models import db, Invoice, Company, Item, ProcessingJob
from ocr_processor import InvoiceOCRProcessor
from field_validator import InvoiceFieldValidator
from mock_data import create_mock_data, create_sample_invoice

# Initialize blueprint
view_bp = Blueprint('views', __name__)

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize processors
ocr_processor = InvoiceOCRProcessor()
field_validator = InvoiceFieldValidator()

# Function to set up the app with initial data and processors
def setup_app(app):
    """Set up the app with initial data and processors"""
    ocr_processor.init_app(app)
    field_validator.init_app(app)
    
    # Create mock data
    try:
        create_mock_data()
    except Exception as e:
        logger.exception(f"Error creating mock data: {str(e)}")

@view_bp.route('/')
def index():
    """Render the home page"""
    return render_template('index.html')

@view_bp.route('/upload')
def upload_page():
    """Render the upload page"""
    return render_template('upload.html')

@view_bp.route('/dashboard')
def dashboard():
    """Render the dashboard page"""
    # Get recent invoices
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(10).all()
    
    # Get processing jobs
    processing_jobs = ProcessingJob.query.order_by(ProcessingJob.started_at.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html',
        invoices=recent_invoices,
        jobs=processing_jobs
    )

@view_bp.route('/invoices')
def invoices_list():
    """Render the invoices list page"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).paginate(page=page, per_page=per_page)
    
    return render_template(
        'invoices.html',
        invoices=invoices
    )

@view_bp.route('/invoices/<int:invoice_id>')
def invoice_detail(invoice_id):
    """Render the invoice detail page"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    return render_template(
        'invoice_details.html',
        invoice=invoice
    )

@view_bp.route('/processing/<job_id>')
def processing_status(job_id):
    """Render the processing status page"""
    job = ProcessingJob.query.filter_by(job_id=job_id).first_or_404()
    
    return render_template(
        'processing.html',
        job=job
    )

@view_bp.route('/results/<job_id>')
def results(job_id):
    """Render the OCR results page"""
    job = ProcessingJob.query.filter_by(job_id=job_id).first_or_404()
    
    if job.status != 'completed':
        flash('Processing is not yet complete.', 'warning')
        return redirect(url_for('views.processing_status', job_id=job_id))
    
    # Parse the OCR results
    ocr_results = {}
    if job.result:
        try:
            # Use json.loads instead of eval for security and reliability
            import json
            ocr_results = json.loads(job.result)
            logger.debug(f"Successfully parsed OCR results: {ocr_results}")
        except Exception as e:
            logger.error(f"Error parsing OCR results: {str(e)}")
            flash(f'Error parsing OCR results: {str(e)}', 'error')
    
    return render_template(
        'results.html',
        job=job,
        results=ocr_results
    )

@view_bp.route('/create-sample')
def create_sample():
    """Create a sample invoice for testing"""
    try:
        invoice = create_sample_invoice()
        if invoice:
            flash(f'Sample invoice {invoice.invoice_number} created successfully.', 'success')
        else:
            flash('Failed to create sample invoice.', 'error')
    except Exception as e:
        logger.exception(f"Error creating sample invoice: {str(e)}")
        flash(f'Error creating sample invoice: {str(e)}', 'error')
    
    return redirect(url_for('views.dashboard'))
