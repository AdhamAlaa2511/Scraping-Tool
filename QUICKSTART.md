# Quick Start Guide

Get up and running in 5 minutes!

## Step 1: Install Dependencies (1 min)

```bash
pip install -r requirements.txt
```

## Step 2: Try the Demo (1 min)

See the dashboard with sample data:

```bash
python demo.py
python dashboard.py
```

Open http://localhost:5000 in your browser

You'll see:
- Sample competitor data
- Example changes detected
- Interactive dashboard

## Step 3: Add Your First Competitor (2 mins)

Edit `config.yaml`:

```yaml
competitors:
  - name: "Your Competitor Name"
    website: "https://theirwebsite.com"
    pages:
      - url: "https://theirwebsite.com/pricing"
        type: "pricing"
        selector: ""  # Leave empty to capture all text
```

## Step 4: Run Your First Scrape (1 min)

```bash
python scraper.py
```

This will:
1. Fetch the competitor's page
2. Extract the content
3. Store it in the database
4. Show you if any changes were detected

## Step 5: View in Dashboard

Refresh your dashboard at http://localhost:5000

You'll now see real data from your competitor!

## What's Next?

### Add More Competitors

Just add more entries to `config.yaml`:

```yaml
competitors:
  - name: "Competitor A"
    pages:
      - url: "https://competitor-a.com/features"
        type: "features"
  
  - name: "Competitor B"
    pages:
      - url: "https://competitor-b.com/pricing"
        type: "pricing"
```

### Set Up Notifications

**Email:**
```yaml
notifications:
  email:
    enabled: true
    sender_email: "your-email@gmail.com"
    sender_password: "your-app-password"  # From Google App Passwords
    recipient_emails:
      - "you@company.com"
```

**Slack:**
```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK"
```

### Automate It

Run continuously:
```bash
python scheduler.py
```

Or use cron:
```bash
crontab -e
# Add: 0 9 * * * cd /path/to/competitor-tracker && python scraper.py && python notifier.py
```

## Finding the Right CSS Selector

1. Go to competitor's website
2. Right-click the content you want to track
3. Click "Inspect" (opens DevTools)
4. Right-click the highlighted HTML element
5. Copy → Copy selector
6. Paste into `config.yaml`

**Examples:**

```yaml
# Capture entire pricing section
selector: ".pricing-container"

# Capture all product features
selector: ".features-list"

# Capture blog posts
selector: "article.post"

# Capture everything (no selector)
selector: ""
```

## Tips

- Start with 2-3 competitors
- Use empty selectors (`""`) first to see what gets captured
- Check the dashboard daily for the first week
- Adjust selectors if you're getting too much/little content
- Set scraping interval to 24 hours initially

## Need Help?

Check the full README.md for:
- Detailed configuration options
- Troubleshooting guide
- Advanced features
- API documentation

---

**You're all set! Happy tracking! 🎉**
