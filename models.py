from datetime import datetime
from app import db

class Company(db.Model):
    """Model for company data (vendors and customers)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    gstin = db.Column(db.String(15), unique=True, nullable=False)
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(10))
    country = db.Column(db.String(100), default="India")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gstin': self.gstin,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'pin_code': self.pin_code,
            'country': self.country
        }

class Item(db.Model):
    """Model for inventory items"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    hsn_sac = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'hsn_sac': self.hsn_sac,
            'description': self.description
        }

class Invoice(db.Model):
    """Model for invoice data"""
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    po_number = db.Column(db.String(50), nullable=True)
    
    vendor_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    vendor = db.relationship('Company', foreign_keys=[vendor_id])
    
    customer_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    customer = db.relationship('Company', foreign_keys=[customer_id])
    
    place_of_supply = db.Column(db.String(100), nullable=True)
    
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    
    terms = db.Column(db.String(100), default="Immediate")
    notes = db.Column(db.Text, nullable=True)
    
    # OCR and processing metadata
    ocr_confidence = db.Column(db.Float, default=0.0)  # Average OCR confidence
    processing_status = db.Column(db.String(20), default="pending")  # pending, processing, completed, error
    validation_errors = db.Column(db.Text, nullable=True)  # JSON string of validation errors
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    line_items = db.relationship('InvoiceLineItem', backref='invoice', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'po_number': self.po_number,
            'vendor': self.vendor.to_dict() if self.vendor else None,
            'customer': self.customer.to_dict() if self.customer else None,
            'place_of_supply': self.place_of_supply,
            'subtotal': self.subtotal,
            'tax_amount': self.tax_amount,
            'discount': self.discount,
            'total_amount': self.total_amount,
            'terms': self.terms,
            'notes': self.notes,
            'ocr_confidence': self.ocr_confidence,
            'processing_status': self.processing_status,
            'line_items': [item.to_dict() for item in self.line_items],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class InvoiceLineItem(db.Model):
    """Model for invoice line items"""
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    item = db.relationship('Item')
    
    description = db.Column(db.String(255), nullable=False)
    hsn_sac = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    tax_percentage = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'hsn_sac': self.hsn_sac,
            'quantity': self.quantity,
            'rate': self.rate,
            'tax_percentage': self.tax_percentage,
            'tax_amount': self.tax_amount,
            'amount': self.amount,
            'item': self.item.to_dict() if self.item else None
        }

class ProcessingJob(db.Model):
    """Model for tracking OCR processing jobs"""
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, processing, completed, error
    result = db.Column(db.Text, nullable=True)  # JSON string of OCR results
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    invoice = db.relationship('Invoice')
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'file_path': self.file_path,
            'status': self.status,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'invoice_id': self.invoice_id
        }
