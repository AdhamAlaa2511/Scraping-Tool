# 🚀 IMPLEMENTATION GUIDE
## Moving from Current to Production-Ready Code

---

## 📋 QUICK START (For the Impatient)

### Option A: Apply Critical Fixes Only (2 hours)

```bash
# 1. Backup current code
cp dashboard.py dashboard_backup.py
cp database.py database_backup.py

# 2. Replace with fixed versions
cp dashboard_fixed.py dashboard.py
cp database_fixed.py database.py

# 3. Install new dependencies
pip install Flask-WTF python-dotenv

# 4. Set environment variable
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 5. Restart
python dashboard.py
```

### Option B: Full Production Deployment (1 day)

Follow the detailed guide below.

---

## 🔐 STEP 1: Security Hardening (CRITICAL)

### 1.1 Add Secret Key

**In dashboard.py:**
```python
import secrets
import os

# Add after app creation
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
```

**In production, set environment variable:**
```bash
# Linux/Mac
export SECRET_KEY="your-secret-key-here"

# Windows
set SECRET_KEY=your-secret-key-here
```

### 1.2 Enable CSRF Protection

**Install Flask-WTF:**
```bash
pip install Flask-WTF
```

**Add to dashboard.py:**
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
```

**Add CSRF token to HTML template** (in `<head>`):
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

**Update JavaScript fetch calls:**
```javascript
// Get CSRF token
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

// Add to all POST/PUT/DELETE requests
fetch('/api/competitors', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken  // Add this
    },
    body: JSON.stringify(payload)
})
```

---

## 📊 STEP 2: Add Logging (HIGH PRIORITY)

### 2.1 Setup Logging

**Create logs directory:**
```bash
mkdir logs
```

**Add logging setup to dashboard.py:**
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger('competitor_dashboard')
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = RotatingFileHandler(
        'logs/dashboard.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    logger.addHandler(file_handler)
    return logger

logger = setup_logging()
```

### 2.2 Replace print statements

**Before:**
```python
print(f"Scraping started: {datetime.now()}")
```

**After:**
```python
logger.info(f"Scraping started: {datetime.now()}")
```

---

## ✅ STEP 3: Input Validation (HIGH PRIORITY)

### 3.1 Add Validation Functions

**Add to dashboard.py:**
```python
from urllib.parse import urlparse
import re

def validate_url(url):
    """Validate URL format"""
    if not url or not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        return all([
            result.scheme in ['http', 'https'],
            result.netloc,
            len(url) <= 2048
        ])
    except:
        return False

def validate_competitor_name(name):
    """Validate competitor name"""
    if not name or not isinstance(name, str):
        return False
    if len(name) < 2 or len(name) > 100:
        return False
    return bool(re.match(r'^[a-zA-Z0-9\s\.\-&\(\)]+$', name))
```

### 3.2 Apply Validation to API Endpoints

**Update `/api/competitors` endpoint:**
```python
@app.route('/api/competitors', methods=['POST'])
def api_add():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    # Validate name
    name = (data.get('name') or '').strip()
    if not validate_competitor_name(name):
        return jsonify({'success': False, 'message': 'Invalid name'}), 400
    
    # Validate URL
    website = (data.get('website') or '').strip()
    if website and not validate_url(website):
        return jsonify({'success': False, 'message': 'Invalid URL'}), 400
    
    # ... rest of code
```

---

## 🔧 STEP 4: Fix Database Connection Leaks

### 4.1 Use Context Managers

**In database.py, change:**
```python
# BEFORE:
def get_connection(self):
    return sqlite3.connect(self.db_path)

# AFTER:
from contextmanager import contextmanager

@contextmanager
def get_connection(self):
    conn = None
    try:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        yield conn
    finally:
        if conn:
            conn.close()
```

### 4.2 Update All Methods to Use Context Manager

**Before:**
```python
def save_snapshot(self, ...):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute(...)
    conn.commit()
    conn.close()
```

**After:**
```python
def save_snapshot(self, ...):
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(...)
        conn.commit()
```

---

## 📈 STEP 5: Performance Optimization

### 5.1 Add Rate Limiting

**Add to scraper.py:**
```python
from time import sleep, time
from collections import defaultdict
from urllib.parse import urlparse

class RateLimiter:
    def __init__(self, requests_per_second=0.5):
        self.requests_per_second = requests_per_second
        self.last_request_time = defaultdict(float)
    
    def wait_if_needed(self, domain):
        now = time()
        time_since_last = now - self.last_request_time[domain]
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            sleep(min_interval - time_since_last)
        
        self.last_request_time[domain] = time()

# In scraper __init__:
self.rate_limiter = RateLimiter(requests_per_second=0.5)

# Before each request:
domain = urlparse(url).netloc
self.rate_limiter.wait_if_needed(domain)
```

### 5.2 Add Content Size Limits

**In database.py:**
```python
MAX_CONTENT_SIZE = 1_000_000  # 1MB

def save_snapshot(self, competitor_name, page_url, page_type, content_hash, content, metadata=None):
    # Truncate if too large
    if len(content) > MAX_CONTENT_SIZE:
        logger.warning(f"Content truncated for {page_url}")
        content = content[:MAX_CONTENT_SIZE]
    
    # ... rest of code
```

---

## 🧪 STEP 6: Testing (Optional but Recommended)

### 6.1 Create Test File

**Create `tests/test_database.py`:**
```python
import unittest
from database import CompetitorDB

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = CompetitorDB(':memory:')
    
    def test_add_competitor(self):
        result = self.db.add_competitor('Test', 'https://test.com', [
            {'url': 'https://test.com/pricing', 'type': 'pricing', 'selector': ''}
        ])
        self.assertTrue(result)
    
    def test_duplicate_competitor(self):
        self.db.add_competitor('Test', 'https://test.com', [])
        result = self.db.add_competitor('Test', 'https://test.com', [])
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
```

### 6.2 Run Tests

```bash
python -m pytest tests/
```

---

## 🌐 STEP 7: Production Deployment

### 7.1 Use Production WSGI Server

**Install Gunicorn:**
```bash
pip install gunicorn
```

**Run with Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 dashboard:app
```

### 7.2 Use Environment Variables

**Create `.env` file:**
```bash
SECRET_KEY=your-secret-key-here
DEBUG=False
DATABASE_PATH=/var/lib/competitor_tracker/data.db
LOG_LEVEL=INFO
```

**Load in dashboard.py:**
```python
from dotenv import load_dotenv
load_dotenv()

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['DEBUG'] = os.environ.get('DEBUG', 'False') == 'True'
```

### 7.3 Setup Systemd Service (Linux)

**Create `/etc/systemd/system/competitor-tracker.service`:**
```ini
[Unit]
Description=Competitor Intelligence Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/competitor-tracker
Environment="PATH=/var/www/competitor-tracker/venv/bin"
ExecStart=/var/www/competitor-tracker/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 dashboard:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable competitor-tracker
sudo systemctl start competitor-tracker
```

### 7.4 Setup Nginx Reverse Proxy

**Create `/etc/nginx/sites-available/competitor-tracker`:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /var/www/competitor-tracker/static;
    }
}
```

---

## 📊 STEP 8: Monitoring

### 8.1 Add Health Check Endpoint

```python
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
```

### 8.2 Setup Log Monitoring

**Use logrotate** (`/etc/logrotate.d/competitor-tracker`):
```
/var/log/competitor-tracker/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
```

---

## 🔄 STEP 9: Database Backups

### 9.1 Create Backup Script

**Create `backup.sh`:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/competitor-tracker"
DB_PATH="/var/lib/competitor-tracker/competitor_data.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/competitor_data_$DATE.db
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
```

### 9.2 Setup Cron Job

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /opt/competitor-tracker/backup.sh
```

---

## ✅ VERIFICATION CHECKLIST

After implementation, verify:

- [ ] Flask has SECRET_KEY set
- [ ] CSRF protection enabled
- [ ] All API endpoints validate input
- [ ] Logging is working (check `logs/dashboard.log`)
- [ ] Database connections use context managers
- [ ] Rate limiting is active
- [ ] Tests pass (if implemented)
- [ ] Health check endpoint responds
- [ ] Backups are running
- [ ] Application runs with Gunicorn
- [ ] Nginx reverse proxy configured
- [ ] SSL certificate installed (use Let's Encrypt)

---

## 📚 RESOURCES

**Flask Security:**
- https://flask.palletsprojects.com/en/latest/security/

**OWASP Top 10:**
- https://owasp.org/www-project-top-ten/

**Python Logging:**
- https://docs.python.org/3/library/logging.html

**Gunicorn Deployment:**
- https://gunicorn.org/

---

## 🆘 TROUBLESHOOTING

### Issue: CSRF Token Missing
**Solution**: Ensure `<meta name="csrf-token">` is in HTML and JavaScript sends `X-CSRFToken` header

### Issue: Database Locked
**Solution**: Check if multiple processes are accessing database. Use `timeout` parameter in `sqlite3.connect()`

### Issue: Import Errors
**Solution**: Verify all dependencies installed: `pip install -r requirements.txt`

### Issue: Permission Denied (Production)
**Solution**: Check file permissions: `chown -R www-data:www-data /var/www/competitor-tracker`

---

**Good luck with your deployment! 🚀**
