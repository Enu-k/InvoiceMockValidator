import re
import logging
import json
from datetime import datetime
from models import Company, Item

logger = logging.getLogger(__name__)

class InvoiceFieldValidator:
    """
    Class for validating extracted invoice fields against business rules and master data
    """
    def __init__(self, app=None):
        self.app = app
        
        # Define field validation rules
        self.validation_rules = {
            'invoice_number': {
                'required': True,
                'pattern': r'^INV-\d{2}-\d{3}$',
                'error_msg': 'Invoice number must be in format INV-XX-XXX'
            },
            'invoice_date': {
                'required': True,
                'date_format': '%Y-%m-%d',
                'error_msg': 'Invoice date must be in format YYYY-MM-DD'
            },
            'due_date': {
                'required': False,
                'date_format': '%Y-%m-%d',
                'error_msg': 'Due date must be in format YYYY-MM-DD'
            },
            'po_number': {
                'required': False,
                'pattern': r'^PO-\d{2}-\d{3}$',
                'error_msg': 'PO number must be in format PO-XX-XXX'
            },
            'vendor_gstin': {
                'required': True,
                'pattern': r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$',
                'error_msg': 'GSTIN must be a valid 15-character code'
            },
            'customer_gstin': {
                'required': True,
                'pattern': r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$',
                'error_msg': 'GSTIN must be a valid 15-character code'
            },
            'place_of_supply': {
                'required': False,
                'error_msg': 'Place of supply must be a valid state name'
            },
            'subtotal': {
                'required': True,
                'min_value': 0,
                'error_msg': 'Subtotal must be a positive number'
            },
            'tax_amount': {
                'required': True,
                'min_value': 0,
                'error_msg': 'Tax amount must be a positive number'
            },
            'total_amount': {
                'required': True,
                'min_value': 0,
                'error_msg': 'Total amount must be a positive number'
            }
        }
        
        # Valid Indian states for place of supply
        self.valid_states = [
            'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
            'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
            'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
            'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
            'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
            'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli',
            'Daman and Diu', 'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry'
        ]
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def validate_invoice(self, invoice_data):
        """
        Validate all invoice fields against business rules and master data
        Returns a tuple (is_valid, errors_dict)
        """
        errors = {}
        
        # Validate basic fields
        for field, rules in self.validation_rules.items():
            if field == 'vendor_gstin':
                value = invoice_data.get('vendor', {}).get('gstin')
            elif field == 'customer_gstin':
                value = invoice_data.get('customer', {}).get('gstin')
            else:
                value = invoice_data.get(field)
                
            # Check required fields
            if rules.get('required', False) and not value:
                errors[field] = f"{field.replace('_', ' ').title()} is required"
                continue
                
            # Skip validation if field is empty and not required
            if not value and not rules.get('required', False):
                continue
                
            # Validate patterns
            if 'pattern' in rules and value:
                if not re.match(rules['pattern'], value):
                    errors[field] = rules['error_msg']
                    
            # Validate date formats
            if 'date_format' in rules and value:
                try:
                    datetime.strptime(value, rules['date_format'])
                except ValueError:
                    errors[field] = rules['error_msg']
                    
            # Validate numeric minimum values
            if 'min_value' in rules and value is not None:
                try:
                    num_value = float(value)
                    if num_value < rules['min_value']:
                        errors[field] = rules['error_msg']
                except (ValueError, TypeError):
                    errors[field] = f"{field.replace('_', ' ').title()} must be a number"
        
        # Validate place of supply
        if invoice_data.get('place_of_supply') and invoice_data['place_of_supply'] not in self.valid_states:
            errors['place_of_supply'] = f"Place of supply must be a valid Indian state"
        
        # Validate company data against database
        if invoice_data.get('vendor', {}).get('gstin'):
            company = self.validate_company(invoice_data['vendor']['gstin'])
            if not company:
                errors['vendor'] = f"Vendor with GSTIN {invoice_data['vendor']['gstin']} not found in master data"
        
        if invoice_data.get('customer', {}).get('gstin'):
            company = self.validate_company(invoice_data['customer']['gstin'])
            if not company:
                errors['customer'] = f"Customer with GSTIN {invoice_data['customer']['gstin']} not found in master data"
        
        # Validate line items
        if not invoice_data.get('line_items'):
            errors['line_items'] = "At least one line item is required"
        else:
            line_item_errors = []
            for idx, item in enumerate(invoice_data['line_items']):
                item_errors = {}
                
                # Required fields
                for field in ['description', 'quantity', 'rate', 'tax_percentage', 'amount']:
                    if field not in item or item[field] is None or (isinstance(item[field], str) and not item[field].strip()):
                        item_errors[field] = f"{field.replace('_', ' ').title()} is required"
                
                # Validate HSN/SAC code exists in master data
                if 'hsn_sac' in item and item['hsn_sac']:
                    hsn_valid = self.validate_hsn_sac(item['hsn_sac'])
                    if not hsn_valid:
                        item_errors['hsn_sac'] = f"HSN/SAC code {item['hsn_sac']} not found in master data"
                
                # Check numeric fields
                for field in ['quantity', 'rate', 'tax_percentage', 'amount']:
                    if field in item and not item_errors.get(field):
                        try:
                            value = float(item[field]) if isinstance(item[field], str) else item[field]
                            if value < 0:
                                item_errors[field] = f"{field.replace('_', ' ').title()} must be a positive number"
                        except (ValueError, TypeError):
                            item_errors[field] = f"{field.replace('_', ' ').title()} must be a number"
                
                if item_errors:
                    line_item_errors.append({
                        'index': idx,
                        'errors': item_errors
                    })
            
            if line_item_errors:
                errors['line_items'] = line_item_errors
        
        # Calculate and validate totals
        if not errors.get('line_items') and not errors.get('subtotal') and not errors.get('tax_amount') and not errors.get('total_amount'):
            # Calculate expected values
            calculated_subtotal = sum(float(item['amount']) for item in invoice_data['line_items'])
            calculated_tax = sum(float(item['tax_amount']) for item in invoice_data['line_items'])
            calculated_total = calculated_subtotal - float(invoice_data.get('discount', 0)) + calculated_tax
            
            # Allow for small floating point differences
            subtotal_diff = abs(calculated_subtotal - float(invoice_data['subtotal']))
            tax_diff = abs(calculated_tax - float(invoice_data['tax_amount']))
            total_diff = abs(calculated_total - float(invoice_data['total_amount']))
            
            tolerance = 0.05  # Allow small differences due to rounding
            
            if subtotal_diff > tolerance:
                errors['subtotal'] = f"Calculated subtotal ({calculated_subtotal:.2f}) doesn't match invoice subtotal ({invoice_data['subtotal']})"
            
            if tax_diff > tolerance:
                errors['tax_amount'] = f"Calculated tax ({calculated_tax:.2f}) doesn't match invoice tax ({invoice_data['tax_amount']})"
                
            if total_diff > tolerance:
                errors['total_amount'] = f"Calculated total ({calculated_total:.2f}) doesn't match invoice total ({invoice_data['total_amount']})"
        
        return (len(errors) == 0, errors)
    
    def validate_company(self, gstin):
        """
        Validate company GSTIN against master data
        Returns company object if found, None otherwise
        """
        try:
            company = Company.query.filter_by(gstin=gstin).first()
            return company
        except Exception as e:
            logger.error(f"Error validating company GSTIN {gstin}: {str(e)}")
            return None
    
    def validate_hsn_sac(self, hsn_sac):
        """
        Validate HSN/SAC code against master data
        Returns True if valid, False otherwise
        """
        try:
            item = Item.query.filter_by(hsn_sac=hsn_sac).first()
            return item is not None
        except Exception as e:
            logger.error(f"Error validating HSN/SAC {hsn_sac}: {str(e)}")
            return False
    
    def format_validation_errors(self, errors):
        """Format validation errors as a JSON string"""
        return json.dumps(errors)
