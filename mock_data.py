import logging
from datetime import datetime
from app import db
from models import Company, Item, Invoice, InvoiceLineItem

logger = logging.getLogger(__name__)

def create_mock_data():
    """Create mock master data for testing the application"""
    create_mock_companies()
    create_mock_items()
    logger.info("Mock data created successfully")

def create_mock_companies():
    """Create mock companies based on sample invoices"""
    companies = [
        # Vendors
        {
            'name': 'Apex Nova Pvt Ltd',
            'gstin': '27AAPCA1234F1Z2',
            'address': 'Plot 10, Tech Park, Sector 5',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pin_code': '400072',
            'country': 'India'
        },
        {
            'name': 'BrightEdge Industries Ltd',
            'gstin': '29AAICB2345K1ZX',
            'address': '45 Industrial Estate, Whitefield',
            'city': 'Bengaluru',
            'state': 'Karnataka',
            'pin_code': '560066',
            'country': 'India'
        },
        {
            'name': 'Crestline Systems Corporation',
            'gstin': '27AACCC6789M1Z3',
            'address': '12 Innov8 Hub, Hinjawadi',
            'city': 'Pune',
            'state': 'Maharashtra',
            'pin_code': '411057',
            'country': 'India'
        },
        {
            'name': 'DeltaWave Technologies LLP',
            'gstin': '36AADTD3456N1ZY',
            'address': '88 Business Plaza, Gachibowli',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pin_code': '500032',
            'country': 'India'
        },
        {
            'name': 'Evergreen Components Co.',
            'gstin': '19AAECE5678P1ZQ',
            'address': '7 Corporate Tower, Salt Lake',
            'city': 'Kolkata',
            'state': 'West Bengal',
            'pin_code': '700091',
            'country': 'India'
        },
        
        # Customers
        {
            'name': 'Galaxy Supplies',
            'gstin': '27AABCG9999Q1Z5',
            'address': 'Unit 4, Industrial Estate',
            'city': 'Pune',
            'state': 'Maharashtra',
            'pin_code': '411045',
            'country': 'India'
        },
        {
            'name': 'Horizon Materials',
            'gstin': '29AAAHM8888L1Z8',
            'address': '23 Commerce Center',
            'city': 'Bengaluru',
            'state': 'Karnataka',
            'pin_code': '560100',
            'country': 'India'
        },
        {
            'name': 'Infinity Traders',
            'gstin': '33AAAIT7777K1ZF',
            'address': 'Block B, Logistics Park',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pin_code': '600103',
            'country': 'India'
        },
        {
            'name': 'Jupiter Resources',
            'gstin': '06AAAJR6666R1Z2',
            'address': 'Sector 21',
            'city': 'Faridabad',
            'state': 'Haryana',
            'pin_code': '121005',
            'country': 'India'
        },
        {
            'name': 'Keystone Components',
            'gstin': '19AAAKC5555F1Z6',
            'address': 'Plot 6, Durgapur Industrial Area',
            'city': 'Durgapur',
            'state': 'West Bengal',
            'pin_code': '713212',
            'country': 'India'
        }
    ]
    
    # Only add companies that don't already exist
    for company_data in companies:
        # Check if company with this GSTIN already exists
        existing_company = Company.query.filter_by(gstin=company_data['gstin']).first()
        if not existing_company:
            company = Company(**company_data)
            db.session.add(company)
    
    db.session.commit()
    logger.info(f"Added {len(companies)} mock companies")

def create_mock_items():
    """Create mock items based on sample invoices"""
    items = [
        {
            'name': 'PVC Pipes (20mm)',
            'hsn_sac': '3917',
            'description': 'PVC Pipes, 20mm diameter'
        },
        {
            'name': 'Electrical Cable (roll)',
            'hsn_sac': '8544',
            'description': 'Electrical Cable, sold by roll'
        },
        {
            'name': 'Paint Bucket (20L)',
            'hsn_sac': '3208',
            'description': 'Paint Bucket, 20 Liter capacity'
        },
        {
            'name': 'Steel Rods (10mm)',
            'hsn_sac': '7214',
            'description': 'Steel Rods, 10mm diameter'
        },
        {
            'name': 'Cement Bags (50kg)',
            'hsn_sac': '2523',
            'description': 'Cement Bags, 50kg weight'
        },
        {
            'name': 'Glass Panel (sq.ft)',
            'hsn_sac': '7007',
            'description': 'Glass Panels, priced per sq.ft'
        },
        {
            'name': 'Wooden Door',
            'hsn_sac': '4418',
            'description': 'Standard Wooden Door'
        },
        {
            'name': 'Bricks',
            'hsn_sac': '6901',
            'description': 'Standard Bricks'
        },
        {
            'name': 'Rebar Mesh',
            'hsn_sac': '7314',
            'description': 'Reinforcement Mesh'
        },
        {
            'name': 'River Sand (cu.m)',
            'hsn_sac': '2505',
            'description': 'River Sand, per cubic meter'
        },
        {
            'name': 'Concrete Blocks',
            'hsn_sac': '6810',
            'description': 'Standard Concrete Blocks'
        }
    ]
    
    # Only add items that don't already exist
    for item_data in items:
        # Check if item with this HSN/SAC already exists
        existing_item = Item.query.filter_by(hsn_sac=item_data['hsn_sac'], name=item_data['name']).first()
        if not existing_item:
            item = Item(**item_data)
            db.session.add(item)
    
    db.session.commit()
    logger.info(f"Added {len(items)} mock items")

def create_sample_invoice():
    """Create a sample invoice for testing"""
    # Get vendor and customer
    vendor = Company.query.filter_by(name='Apex Nova Pvt Ltd').first()
    customer = Company.query.filter_by(name='Galaxy Supplies').first()
    
    if not vendor or not customer:
        logger.error("Cannot create sample invoice: vendor or customer not found")
        return None
    
    # Create invoice
    invoice = Invoice(
        invoice_number="INV-25-100",
        invoice_date=datetime.strptime("2025-05-07", "%Y-%m-%d").date(),
        due_date=datetime.strptime("2025-05-22", "%Y-%m-%d").date(),
        po_number="PO-25-100",
        vendor_id=vendor.id,
        customer_id=customer.id,
        place_of_supply="Karnataka",
        subtotal=117660.00,
        tax_amount=21178.80,
        discount=0.0,
        total_amount=138838.80,
        terms="Immediate",
        processing_status="completed",
        ocr_confidence=95.5
    )
    
    db.session.add(invoice)
    db.session.flush()  # Get the invoice ID
    
    # Get items
    pvc_pipes = Item.query.filter_by(hsn_sac='3917').first()
    electrical_cable = Item.query.filter_by(hsn_sac='8544').first()
    paint_bucket = Item.query.filter_by(hsn_sac='3208').first()
    steel_rods = Item.query.filter_by(hsn_sac='7214').first()
    
    if not all([pvc_pipes, electrical_cable, paint_bucket, steel_rods]):
        logger.error("Cannot create sample invoice line items: some items not found")
        db.session.rollback()
        return None
    
    # Create line items
    line_items = [
        InvoiceLineItem(
            invoice_id=invoice.id,
            item_id=pvc_pipes.id,
            description=pvc_pipes.name,
            hsn_sac=pvc_pipes.hsn_sac,
            quantity=34,
            rate=150.00,
            tax_percentage=18.0,
            tax_amount=918.00,
            amount=5100.00
        ),
        InvoiceLineItem(
            invoice_id=invoice.id,
            item_id=electrical_cable.id,
            description=electrical_cable.name,
            hsn_sac=electrical_cable.hsn_sac,
            quantity=20,
            rate=1200.00,
            tax_percentage=18.0,
            tax_amount=4320.00,
            amount=24000.00
        ),
        InvoiceLineItem(
            invoice_id=invoice.id,
            item_id=paint_bucket.id,
            description=paint_bucket.name,
            hsn_sac=paint_bucket.hsn_sac,
            quantity=46,
            rate=1800.00,
            tax_percentage=18.0,
            tax_amount=14904.00,
            amount=82800.00
        ),
        InvoiceLineItem(
            invoice_id=invoice.id,
            item_id=steel_rods.id,
            description=steel_rods.name,
            hsn_sac=steel_rods.hsn_sac,
            quantity=8,
            rate=720.00,
            tax_percentage=18.0,
            tax_amount=1036.80,
            amount=5760.00
        )
    ]
    
    for line_item in line_items:
        db.session.add(line_item)
    
    db.session.commit()
    logger.info(f"Created sample invoice {invoice.invoice_number}")
    
    return invoice
