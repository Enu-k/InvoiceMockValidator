# KodoAP Invoice Processing System

An advanced invoice processing system that leverages multiple OCR technologies to extract and validate financial document data with high accuracy.

## Overview

KodoAP is a comprehensive invoice processing solution that combines traditional OCR with AI-powered extraction to provide highly accurate data capture from invoice documents. The system includes features for:

- Invoice image/PDF upload and processing
- Automatic data extraction using OCR technology
- Enhanced data extraction using OpenAI Vision API
- Field validation against business rules and master data
- Web-based user interface for reviewing and managing extracted data
- Database storage of processed invoices

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL database
- Tesseract OCR (for standard OCR processing)
- OpenAI API key (for enhanced OCR processing)

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/invoice_db

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Session Secret
SESSION_SECRET=your_secure_random_string
```

### Local Setup Instructions

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/kodoap-invoice-processing.git
   cd kodoap-invoice-processing
   ```

2. **Install required packages**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Tesseract OCR**

   - For Ubuntu/Debian:
     ```bash
     sudo apt-get update
     sudo apt-get install tesseract-ocr
     ```
   
   - For macOS:
     ```bash
     brew install tesseract
     ```
   
   - For Windows:
     Download and install from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

4. **Set up PostgreSQL database**

   ```bash
   createdb invoice_db
   ```

5. **Initialize the database**

   The application will automatically create the required tables when it first runs. Alternatively:

   ```bash
   python
   >>> from app import app, db
   >>> with app.app_context():
   >>>     db.create_all()
   ```

6. **Run the application**

   ```bash
   gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
   ```

   or

   ```bash
   python -m flask run --host=0.0.0.0 --port=5000
   ```

7. **Access the application**

   Open your browser and navigate to http://localhost:5000

## OpenAI OCR Validation Process

The enhanced OCR processing using OpenAI Vision API follows these steps:

### 1. Image Preprocessing

The application first processes the invoice image to optimize it for text extraction:
- Converts image to base64 format for OpenAI API consumption
- Maintains original quality for best results

### 2. OpenAI API Integration

The image is sent to OpenAI's Vision API with a specialized system prompt:
- Utilizes the `gpt-4o` model (latest as of May 2024)
- Uses a structured JSON prompt to guide information extraction
- Specifies expected fields such as vendor information, customer details, line items, and financial figures

### 3. Data Extraction and Transformation

Once OpenAI returns the JSON results:
- The system parses the extracted data
- Validates field formats (especially dates and numerical values)
- Maps the results to the application's data structure
- Adds confidence scores based on the extraction quality

### 4. Error Handling and Validation

The system employs robust error handling:
- Validates JSON structure and required fields
- Handles missing or invalid data gracefully
- Provides detailed logs of the extraction process
- Offers fallback to standard OCR when needed

### 5. Data Presentation

Extracted data is presented to the user for review:
- Form-based view for editing and verification
- Raw JSON view for technical analysis
- Validation against master data (companies, items) to ensure accuracy

## Switching Between OCR Methods

The application offers two OCR processing methods:

1. **Standard OCR (Tesseract)**: Faster but less accurate, especially for complex layouts
2. **Enhanced OCR (OpenAI Vision)**: Higher accuracy but requires API key and internet connection

Users can toggle between these methods on the upload page using the "Use OpenAI for enhanced OCR" checkbox.

## System Architecture

The application follows a modular architecture:

- **Flask Backend**: Handles HTTP requests, routing, and business logic
- **OCR Processing**: Extracts text and data from invoice images
- **Field Validation**: Validates extracted data against business rules
- **Database Storage**: Persists processed invoices and master data
- **Web Frontend**: Provides user interface for reviewing and managing invoices

## License

This project is licensed under the MIT License - see the LICENSE file for details.