# Competitor Intelligence Dashboard

A web-based tool for tracking competitor pricing, features, and blog updates.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install flask pyyaml beautifulsoup4 requests reportlab
```

### 2. Run the Dashboard

```bash
python dashboard.py
```

Then open your browser to: http://localhost:5000

### 3. Add Competitors Through Web Interface

All competitor management is done through the web dashboard:

1. Go to the **Competitors** tab
2. Click "Add Competitor"
3. Fill in the form with competitor details
4. Add pages to track (pricing, features, blog)
5. Click "Save Competitor"

**That's it!** No need to edit config files manually.

### 4. (Optional) Migrate from config.yaml

If you have existing competitors in `config.yaml`, run the migration script once:

```bash
python migrate_to_db.py
```

This will move all competitors from the YAML file to the database.

## 📖 How It Works

### Adding Competitors

1. Go to the **Competitors** tab
2. Fill in the competitor name and website
3. Add one or more pages to track
4. Click "Save Competitor"

### Running the Scraper

1. Go to the **Overview** tab
2. Click "Run Scraper Now"
3. The scraper will:
   - Visit each configured page
   - Extract structured data (plans, prices, features)
   - Compare with previous snapshots
   - Record any changes detected

### Viewing Changes

1. Go to the **Changes** tab
2. See all detected changes with:
   - Plain English descriptions
   - Timestamp
   - Direct link to the page

### Exporting Reports

Click "Download Report" on the Overview tab to get a PDF report of all changes.

## 🔧 Configuration

### config.yaml Structure

```yaml
dashboard:
  host: '0.0.0.0'      # Server host
  port: 5000            # Server port
  debug: true           # Enable debug mode

scraping:
  timeout: 30           # Request timeout in seconds
  user_agent: 'Mozilla/5.0...'  # User agent string

# Note: Competitors are managed through the web interface
# No need to add them here!
```

**Important:** Competitors are now stored in the database, not in config.yaml. This makes deployment much easier since you don't need to sync config files across environments.

### Using CSS Selectors (Advanced)

If a page has content outside the main area you want to track, use a CSS selector:

```yaml
selector: ".pricing-container"  # Only scrape this section
selector: "#main-content"       # Use ID selector
selector: ""                    # Leave empty for full page (default)
```

## 📊 Features

- **Smart Extraction**: Automatically detects pricing plans, features, and blog posts
- **Change Detection**: Plain English descriptions of what changed
- **Dashboard**: Clean web interface for managing competitors
- **PDF Reports**: Export changes as formatted PDF documents
- **SQLite Database**: All data stored locally in `competitor_data.db`

## 🗂️ File Structure

```
your-project/
├── dashboard.py          # Main Flask application
├── scraper.py           # Web scraping logic
├── extractors.py        # HTML parsing & extraction
├── database.py          # SQLite database operations
├── config.yaml          # Configuration (settings only)
├── migrate_to_db.py     # One-time migration script (optional)
└── competitor_data.db   # SQLite database (auto-created)
```

**Database Schema:**
- `competitors` - Competitor information (name, website)
- `pages` - Pages to track for each competitor
- `snapshots` - Historical content snapshots
- `changes` - Detected changes log

## 🐛 Troubleshooting

### Error: "No competitors configured"

**Solution**: Edit `config.yaml` and add at least one competitor with at least one page.

### Error: "Failed to fetch URL"

**Possible causes:**
- Website is blocking requests (try different user agent)
- Invalid URL
- Network connection issues
- Website requires authentication

### Changes not detected

**Check:**
- Is the content actually changing?
- Is your CSS selector too specific/narrow?
- Are you scraping the right page type? (pricing vs features vs blog)

### Database locked errors

**Solution**: Make sure only one instance of the dashboard is running.

## 📝 Best Practices

1. **Don't Over-Scrape**: Run the scraper once per day or week, not every minute
2. **Respect robots.txt**: Check if the website allows scraping
3. **Use Specific Selectors**: If pages have lots of navigation/footer content, use CSS selectors
4. **Monitor Competitor Changes**: Review the Changes tab regularly
5. **Backup Your Database**: Copy `competitor_data.db` periodically

## 🔒 Legal & Ethical Considerations

- Only scrape publicly available information
- Respect rate limits and robots.txt
- Don't use scraped data to copy/plagiarize content
- This tool is for competitive intelligence, not data theft
- Check terms of service of websites you're scraping

## 🆘 Getting Help

### Common Issues

**Q: Competitor names with quotes/special characters break the UI**
A: This is now fixed in the latest version with proper HTML escaping.

**Q: "Free" pricing plans aren't detected**
A: This is now fixed - the price validator recognizes "Free" plans.

**Q: Last scraped time never updates**
A: This is now fixed - timestamps update even when content hasn't changed.

### Debug Mode

Enable debug mode in `config.yaml`:

```yaml
dashboard:
  debug: true
```

This will show detailed error messages in the browser.

## 📦 Example Competitors to Track

Here are some example configurations you can add via the web interface:

**SaaS Competitor:**
- Name: `Competitor SaaS`
- Website: `https://competitor.com`
- Pages:
  - URL: `https://competitor.com/pricing` | Type: `pricing`
  - URL: `https://competitor.com/features` | Type: `features`
  - URL: `https://competitor.com/blog` | Type: `blog`

**E-commerce Competitor:**
- Name: `Competitor Store`
- Website: `https://store.com`
- Pages:
  - URL: `https://store.com/products/widget` | Type: `pricing`

## 🚀 Deployment to Production

### Why This Approach is Better

**Before (config.yaml):**
- Had to manually sync config files across environments
- Changes required code deployment
- Risk of config drift between dev/prod

**Now (Database):**
- All competitors stored in database
- Add/edit/delete through web interface
- Just backup and restore the database file
- Config.yaml only has settings (same across all environments)

### Deployment Steps

1. **Copy files to production server:**
   ```bash
   # Copy Python files
   scp *.py user@server:/path/to/app/
   
   # Copy config (settings only)
   scp config.yaml user@server:/path/to/app/
   ```

2. **Set up database on production:**
   ```bash
   # Option A: Start fresh (database auto-created)
   python dashboard.py
   
   # Option B: Copy existing database
   scp competitor_data.db user@server:/path/to/app/
   ```

3. **Add competitors through web interface:**
   - No need to edit files on the server
   - Just log into the dashboard and add them

4. **Schedule scraper (optional):**
   ```bash
   # Linux cron example
   0 9 * * * cd /path/to/app && python -c "from scraper import CompetitorScraper; CompetitorScraper().scrape_all_competitors()"
   ```

### Backing Up Production Data

```bash
# Backup database
scp user@server:/path/to/app/competitor_data.db ./backup_$(date +%Y%m%d).db

# Or backup on server
cp competitor_data.db competitor_data_backup_$(date +%Y%m%d).db
```

### Moving Between Environments

```bash
# Development → Production
scp competitor_data.db user@prod-server:/path/to/app/

# Production → Development (for testing)
scp user@prod-server:/path/to/app/competitor_data.db ./competitor_data_dev.db
```

## 🎯 Advanced Tips

### Scheduling Automatic Scrapes

**Windows (Task Scheduler):**
Create a batch file `run_scraper.bat`:
```batch
cd E:\The New Tool\18-test
python -c "from scraper import CompetitorScraper; CompetitorScraper().scrape_all_competitors()"
```

**Linux/Mac (cron):**
```bash
0 9 * * * cd /path/to/project && python -c "from scraper import CompetitorScraper; CompetitorScraper().scrape_all_competitors()"
```

### Backing Up Data

```bash
# Backup database
cp competitor_data.db competitor_data_backup.db

# Backup config
cp config.yaml config_backup.yaml
```

### Viewing Database Directly

```bash
sqlite3 competitor_data.db
```

```sql
-- View all competitors
SELECT DISTINCT competitor_name FROM snapshots;

-- View recent changes
SELECT * FROM changes ORDER BY detected_at DESC LIMIT 10;

-- Count changes by competitor
SELECT competitor_name, COUNT(*) as changes 
FROM changes 
GROUP BY competitor_name 
ORDER BY changes DESC;
```

## 📈 Version History

### v1.1 (Current)
- ✅ Fixed table header parsing bug
- ✅ Fixed "Free" plan detection
- ✅ Fixed timestamp update issue
- ✅ Fixed HTML escaping security issue
- ✅ Improved error handling
- ✅ Better CSS selector support

### v1.0 (Initial)
- Basic scraping functionality
- Dashboard interface
- PDF reports
- Change detection

---

Made with ❤️ for business and data analysts
