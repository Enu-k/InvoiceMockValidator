import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy base class
class Base(DeclarativeBase):
    pass

# Initialize database
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "kodo-ap-invoice-processing-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure upload folder
app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload size
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Configure OCR settings
app.config["OCR_CONFIDENCE_THRESHOLD"] = 80  # Confidence threshold for OCR results
app.config["OCR_TIMEOUT"] = 30  # Timeout for OCR processing in seconds

# Initialize database with app
db.init_app(app)

# Import routes and register blueprints
with app.app_context():
    from api_routes import api_bp, setup_processors
    from view_routes import view_bp, setup_app
    
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(view_bp)
    
    # Import models and create tables
    import models
    db.create_all()
    
    # Initialize processors and create mock data
    setup_processors(app)
    setup_app(app)
    
    logger.info("Application initialized successfully")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
