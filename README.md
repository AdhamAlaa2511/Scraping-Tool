# Competitor Intelligence Tracker

A comprehensive automated system for monitoring competitor websites, detecting changes, and sending notifications.

## Features

- 🔍 **Automated Web Scraping** - Monitor competitor product pages, pricing, and blogs
- 📊 **Web Dashboard** - Beautiful interface to view all changes and trends
- 📧 **Email Notifications** - Get alerts when competitors make changes
- 💬 **Slack Integration** - Send updates to your team's Slack channel
- 📈 **Change Detection** - Smart tracking of content modifications
- 📋 **Report Generation** - Generate text reports for your team
- ⏰ **Scheduled Execution** - Run automatically at your preferred intervals
- 💾 **SQLite Database** - Store historical data and track trends over time

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `config.yaml` to add your competitors:

```yaml
competitors:
  - name: "Acme Corp"
    website: "https://acme.com"
    pages:
      - url: "https://acme.com/features"
        type: "features"
        selector: ".features-section"
      - url: "https://acme.com/pricing"
        type: "pricing"
        selector: ".pricing-table"
```

**Finding CSS Selectors:**
1. Open competitor's website in Chrome/Firefox
2. Right-click the content area you want to track → Inspect
3. Right-click the HTML element → Copy → Copy selector
4. Paste into the `selector` field

### 3. Run the Dashboard

```bash
python dashboard.py
```

Open http://localhost:5000 in your browser

### 4. Run Manual Scrape

```bash
python scraper.py
```

### 5. Run Automated Scheduler

```bash
python scheduler.py
```

This will run continuously and check competitors at your configured interval.

## Usage Guide

### Dashboard Features

The web dashboard provides:

- **Statistics Cards** - Overview of total competitors, changes, and activity
- **Quick Actions** - Run scraper manually, download reports, refresh data
- **Change Feed** - See all detected changes with filters
- **Real-time Scraping** - Trigger scraping directly from the browser

### Notification Setup

#### Email Notifications

1. Enable Gmail 2-factor authentication
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Update `config.yaml`:

```yaml
notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    sender_email: "your-email@gmail.com"
    sender_password: "your-app-password"
    recipient_emails:
      - "analyst@yourcompany.com"
```

#### Slack Notifications

1. Create an Incoming Webhook: https://api.slack.com/messaging/webhooks
2. Update `config.yaml`:

```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Running on a Server

For continuous monitoring, deploy to a server:

**Option 1: Using screen (Linux/Mac)**

```bash
screen -S competitor-tracker
python scheduler.py
# Press Ctrl+A then D to detach
# Use 'screen -r competitor-tracker' to reattach
```

**Option 2: Using systemd (Linux)**

Create `/etc/systemd/system/competitor-tracker.service`:

```ini
[Unit]
Description=Competitor Intelligence Tracker
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/competitor-tracker
ExecStart=/usr/bin/python3 scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable competitor-tracker
sudo systemctl start competitor-tracker
```

**Option 3: Using cron**

```bash
crontab -e
# Add: 0 */6 * * * cd /path/to/competitor-tracker && python scraper.py && python notifier.py
```

## Project Structure

```
competitor-tracker/
├── config.yaml           # Configuration file
├── database.py           # Database operations
├── scraper.py           # Web scraping logic
├── dashboard.py         # Flask web dashboard
├── notifier.py          # Email/Slack notifications
├── scheduler.py         # Automated scheduling
├── requirements.txt     # Python dependencies
├── competitor_data.db   # SQLite database (auto-created)
└── README.md           # This file
```

## Database Schema

The tool uses SQLite with two main tables:

**snapshots** - Stores every scrape of each page
- competitor_name, page_url, page_type
- content_hash, content
- scraped_at timestamp
- metadata (JSON)

**changes** - Records detected changes
- competitor_name, page_url, page_type
- change_description
- old_content, new_content
- detected_at timestamp
- notified flag

## Advanced Configuration

### Custom Selectors

Different page types may need different selectors:

```yaml
pages:
  # For feature lists
  - url: "https://example.com/features"
    type: "features"
    selector: ".feature-grid, .features-section"
  
  # For pricing tables
  - url: "https://example.com/pricing"
    type: "pricing"
    selector: "[data-pricing-table]"
  
  # For blog posts
  - url: "https://example.com/blog"
    type: "blog"
    selector: "article.post"
```

### Scraping Frequency

Adjust check intervals in `config.yaml`:

```yaml
scraping:
  check_interval_hours: 24  # Daily
  # check_interval_hours: 6   # 4 times per day
  # check_interval_hours: 1   # Hourly
```

## Troubleshooting

### Scraper Not Finding Content

**Problem:** Changes not being detected even when content changes

**Solutions:**
1. Check CSS selector is correct - test in browser DevTools
2. Try a more general selector (e.g., `main` instead of `.specific-class`)
3. Remove selector entirely to capture all page text
4. Some sites load content via JavaScript - you may need Selenium (see below)

### JavaScript-Heavy Websites

If competitor uses heavy JavaScript:

```bash
pip install selenium webdriver-manager
```

Modify scraper.py to use Selenium instead of requests.

### Rate Limiting

If getting blocked:

1. Increase delay between requests in `scraper.py` (line with `time.sleep(2)`)
2. Reduce scraping frequency
3. Use different User-Agent strings
4. Consider using proxies for high-volume monitoring

### Database Too Large

```bash
# Backup database
cp competitor_data.db competitor_data.backup.db

# Delete old snapshots (keeps changes table)
sqlite3 competitor_data.db "DELETE FROM snapshots WHERE scraped_at < datetime('now', '-90 days');"
sqlite3 competitor_data.db "VACUUM;"
```

## API Endpoints

The dashboard exposes REST APIs:

- `POST /api/scrape` - Trigger scraping
- `GET /api/changes?days=30&competitor=Name` - Get changes with filters
- `GET /api/report?days=7` - Generate text report
- `GET /api/stats` - Get statistics

Example:
```bash
curl -X POST http://localhost:5000/api/scrape
curl "http://localhost:5000/api/changes?days=7"
```

## Best Practices

1. **Start Small** - Begin with 2-3 competitors to test
2. **Test Selectors** - Verify your CSS selectors work before automating
3. **Monitor Respectfully** - Don't scrape too frequently (24h is good)
4. **Check robots.txt** - Respect website rules
5. **Keep Backups** - Regularly backup your database
6. **Review Changes** - Regularly check dashboard to ensure quality data

## Legal & Ethical Considerations

- Only scrape publicly available information
- Respect robots.txt and Terms of Service
- Don't overload competitor servers
- Use reasonable scraping intervals
- This tool is for competitive intelligence, not data theft
- Consult legal counsel for your specific use case

## Extending the Tool

### Add New Page Types

You can track any page type:

```yaml
- url: "https://example.com/careers"
  type: "hiring"
  selector: ".job-listing"

- url: "https://example.com/press"
  type: "press"
  selector: ".press-release"
```

### Custom Change Detection

Edit `scraper.py` `detect_changes()` method to add custom logic, like:
- Keyword detection
- Price change alerts
- Specific feature additions

### Export to Other Tools

Export data to CSV for analysis:

```python
import sqlite3
import csv

conn = sqlite3.connect('competitor_data.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM changes")

with open('changes_export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Competitor', 'URL', 'Type', 'Description', 'Date'])
    writer.writerows(cursor.fetchall())
```

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review example configurations
3. Test with simple competitors first

## License

This tool is for internal business intelligence use. Ensure compliance with applicable laws and website terms of service.

---

**Happy Tracking! 🚀**
#   T r a c k i n g - T o o l  
 #   S c r a p i n g - T o o l  
 #   S c r a p i n g - T o o l  
 