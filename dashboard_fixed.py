"""
Competitor Intelligence Dashboard - Production Ready Version
With security hardening, input validation, and proper error handling
"""

from flask import Flask, render_template_string, jsonify, request, Response, abort
from flask_wtf.csrf import CSRFProtect
import yaml
import io
import os
import secrets
import logging
from logging.handlers import RotatingFileHandler
from database import CompetitorDB
from scraper import CompetitorScraper
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from urllib.parse import urlparse
import re

# ============================================================
# LOGGING SETUP
# ============================================================
def setup_logging():
    """Setup application logging"""
    logger = logging.getLogger('competitor_dashboard')
    logger.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/dashboard.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create logs directory
os.makedirs('logs', exist_ok=True)
logger = setup_logging()

# ============================================================
# APP CONFIGURATION
# ============================================================
app = Flask(__name__)

# SECURITY: Set secret key from environment or generate secure one
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_TIME_LIMIT'] = None  # Don't expire CSRF tokens
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# CSRF Protection
csrf = CSRFProtect(app)

# Load configuration
config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {config_path}")
except FileNotFoundError:
    logger.error(f"Config file not found: {config_path}")
    raise RuntimeError(f"Config file not found: {config_path}")
except yaml.YAMLError as e:
    logger.error(f"Invalid YAML config: {e}")
    raise RuntimeError(f"Invalid YAML config: {e}")

# Validate config
required_keys = ['dashboard', 'scraping']
for key in required_keys:
    if key not in config:
        raise RuntimeError(f"Missing required config section: {key}")

# Initialize database and scraper
try:
    db = CompetitorDB()
    scraper = CompetitorScraper()
    logger.info("Database and scraper initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize: {e}")
    raise

# ============================================================
# INPUT VALIDATION
# ============================================================
def validate_url(url):
    """Validate URL format"""
    if not url or not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        return all([
            result.scheme in ['http', 'https'],
            result.netloc,
            len(url) <= 2048  # Max URL length
        ])
    except Exception:
        return False

def validate_competitor_name(name):
    """Validate competitor name"""
    if not name or not isinstance(name, str):
        return False
    if len(name) < 2 or len(name) > 100:
        return False
    # Allow alphanumeric, spaces, dots, hyphens, ampersands
    return bool(re.match(r'^[a-zA-Z0-9\s\.\-&\(\)]+$', name))

def validate_page_type(page_type):
    """Validate page type"""
    valid_types = ['pricing', 'features', 'blog', 'other']
    return page_type in valid_types

def sanitize_string(s, max_length=1000):
    """Sanitize string input"""
    if not s:
        return ''
    s = str(s).strip()
    return s[:max_length]

# ============================================================
# CONSTANTS
# ============================================================
DEFAULT_CHANGE_LIMIT = 50
DEFAULT_DAYS_LOOKBACK = 30
MAX_PAGES_PER_COMPETITOR = 50

# ============================================================
# HTML TEMPLATE (same as before, but with CSRF token)
# ============================================================
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<title>Competitor Intelligence Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="csrf-token" content="{{ csrf_token() }}">
<style>
/* [CSS styles remain the same] */
</style>
</head>
<body>
<!-- [HTML remains the same] -->
</body>
</html>"""

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        stats = db.get_competitor_stats()
        changes = db.get_recent_changes(limit=DEFAULT_CHANGE_LIMIT, days=DEFAULT_DAYS_LOOKBACK)
        
        # Try new database structure, fallback to old
        try:
            competitors_data = db.get_all_competitors_from_db()
            
            # Format for display
            competitors = []
            for comp in competitors_data:
                conn = None
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        SELECT MAX(scraped_at) 
                        FROM snapshots 
                        WHERE competitor_name = ?
                    ''', (comp['name'],))
                    last_scraped = cursor.fetchone()[0]
                    
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM changes 
                        WHERE competitor_name = ?
                    ''', (comp['name'],))
                    change_count = cursor.fetchone()[0]
                    
                    competitors.append({
                        'name': comp['name'],
                        'page_count': len(comp['pages']),
                        'last_scraped': last_scraped,
                        'change_count': change_count
                    })
                finally:
                    if conn:
                        conn.close()
                    
        except Exception as e:
            logger.warning(f"Failed to load from new structure, using fallback: {e}")
            competitors = db.get_all_competitors()
        
        return render_template_string(HTML, stats=stats, changes=changes, competitors=competitors)
    
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return "Internal server error", 500


@app.route('/static/app.js')
def serve_js():
    """Serve JavaScript file"""
    try:
        with open('app.js', 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='application/javascript')
    except FileNotFoundError:
        logger.error("app.js not found")
        abort(404)


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Trigger scraper run"""
    try:
        logger.info("Scraper run initiated")
        n = scraper.scrape_all_competitors()
        logger.info(f"Scraper completed: {n} changes detected")
        return jsonify({'success': True, 'changes_detected': n})
    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Scraper failed', 'changes_detected': 0}), 500


@app.route('/api/report')
def api_report():
    """Generate PDF report"""
    try:
        days = request.args.get('days', DEFAULT_DAYS_LOOKBACK, type=int)
        
        # Validate days parameter
        if days < 1 or days > 365:
            return "Invalid days parameter", 400
        
        changes = db.get_recent_changes(limit=200, days=days)
        pdf_bytes = generate_pdf_report(changes, days)
        
        logger.info(f"PDF report generated for last {days} days")
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=competitor-report-{datetime.now().strftime("%Y-%m-%d")}.pdf'
            }
        )
    except Exception as e:
        logger.error(f"Report generation error: {e}", exc_info=True)
        return "Failed to generate report", 500


@app.route('/api/competitors', methods=['POST'])
def api_add():
    """Add new competitor"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Validate competitor name
        name = sanitize_string(data.get('name', '')).strip()
        if not validate_competitor_name(name):
            return jsonify({'success': False, 'message': 'Invalid competitor name. Use only letters, numbers, spaces, dots, and hyphens (2-100 chars)'}), 400
        
        # Validate website
        website = sanitize_string(data.get('website', '')).strip()
        if website and not validate_url(website):
            return jsonify({'success': False, 'message': 'Invalid website URL'}), 400
        
        # Validate pages
        pages = data.get('pages', [])
        if not isinstance(pages, list):
            return jsonify({'success': False, 'message': 'Pages must be a list'}), 400
        
        if len(pages) == 0:
            return jsonify({'success': False, 'message': 'At least one page is required'}), 400
        
        if len(pages) > MAX_PAGES_PER_COMPETITOR:
            return jsonify({'success': False, 'message': f'Maximum {MAX_PAGES_PER_COMPETITOR} pages per competitor'}), 400
        
        # Validate each page
        validated_pages = []
        for idx, page in enumerate(pages):
            if not isinstance(page, dict):
                return jsonify({'success': False, 'message': f'Invalid page format at index {idx}'}), 400
            
            page_url = sanitize_string(page.get('url', '')).strip()
            if not validate_url(page_url):
                return jsonify({'success': False, 'message': f'Invalid page URL at index {idx}: {page_url[:50]}'}), 400
            
            page_type = page.get('type', 'other')
            if not validate_page_type(page_type):
                return jsonify({'success': False, 'message': f'Invalid page type at index {idx}: {page_type}'}), 400
            
            selector = sanitize_string(page.get('selector', ''), max_length=500)
            
            validated_pages.append({
                'url': page_url,
                'type': page_type,
                'selector': selector
            })
        
        # Add to database
        success = db.add_competitor(name, website, validated_pages)
        
        if success:
            logger.info(f"Competitor added: {name} with {len(validated_pages)} pages")
            return jsonify({'success': True, 'message': f'"{name}" added successfully!'})
        else:
            logger.warning(f"Failed to add competitor: {name} (already exists)")
            return jsonify({'success': False, 'message': f'"{name}" already exists'})
    
    except Exception as e:
        logger.error(f"Error adding competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/api/competitor')
def api_get():
    """Get competitor details"""
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'Name parameter required'}), 400
    
    try:
        comp = db.get_competitor_by_name(name)
        
        if comp:
            return jsonify(comp)
        
        # Fallback: try to get pages from snapshots
        pages = db.get_competitor_pages(name)
        return jsonify({'name': name, 'website': '', 'pages': pages})
    
    except Exception as e:
        logger.error(f"Error getting competitor {name}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/competitor', methods=['PUT'])
def api_update():
    """Update competitor"""
    name = request.args.get('name', '')
    if not name:
        return jsonify({'success': False, 'message': 'Name parameter required'}), 400
    
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        orig = sanitize_string(data.get('original_name', name))
        new_name = sanitize_string(data.get('name', '')).strip()
        
        if not validate_competitor_name(new_name):
            return jsonify({'success': False, 'message': 'Invalid competitor name'}), 400
        
        website = sanitize_string(data.get('website', '')).strip()
        if website and not validate_url(website):
            return jsonify({'success': False, 'message': 'Invalid website URL'}), 400
        
        pages = data.get('pages', [])
        if not isinstance(pages, list) or len(pages) == 0:
            return jsonify({'success': False, 'message': 'At least one page required'}), 400
        
        if len(pages) > MAX_PAGES_PER_COMPETITOR:
            return jsonify({'success': False, 'message': f'Maximum {MAX_PAGES_PER_COMPETITOR} pages allowed'}), 400
        
        # Validate pages
        validated_pages = []
        for page in pages:
            if not validate_url(page.get('url', '')):
                return jsonify({'success': False, 'message': 'Invalid page URL'}), 400
            if not validate_page_type(page.get('type', '')):
                return jsonify({'success': False, 'message': 'Invalid page type'}), 400
            
            validated_pages.append({
                'url': page['url'],
                'type': page['type'],
                'selector': sanitize_string(page.get('selector', ''), max_length=500)
            })
        
        success = db.update_competitor(orig, new_name, website, validated_pages)
        
        if success:
            logger.info(f"Competitor updated: {orig} -> {new_name}")
            return jsonify({'success': True, 'message': f'"{new_name}" updated!'})
        else:
            return jsonify({'success': False, 'message': 'Competitor not found'})
    
    except Exception as e:
        logger.error(f"Error updating competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/api/competitor', methods=['DELETE'])
def api_delete():
    """Delete competitor"""
    name = request.args.get('name', '')
    if not name:
        return jsonify({'success': False, 'message': 'Name parameter required'}), 400
    
    try:
        success = db.delete_competitor_from_db(name)
        
        if success:
            logger.info(f"Competitor deleted: {name}")
            return jsonify({'success': True, 'message': f'"{name}" deleted.'})
        else:
            return jsonify({'success': False, 'message': f'"{name}" not found.'})
    
    except Exception as e:
        logger.error(f"Error deleting competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


# ============================================================
# PDF REPORT GENERATION (same as before)
# ============================================================
def generate_pdf_report(changes, days=30):
    """Generate PDF report of changes"""
    # [PDF generation code remains the same]
    pass


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(400)
def bad_request(e):
    """Handle 400 errors"""
    return jsonify({'error': 'Bad request'}), 400


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    host = config['dashboard'].get('host', '0.0.0.0')
    port = config['dashboard'].get('port', 5000)
    debug = config['dashboard'].get('debug', False)
    
    logger.info(f"Starting dashboard on {host}:{port} (debug={debug})")
    
    app.run(host=host, port=port, debug=debug)
