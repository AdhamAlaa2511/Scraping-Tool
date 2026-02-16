"""
Scheduler module for automated competitor tracking
Runs scraper and notifications at regular intervals
"""

import schedule
import time
import yaml
from scraper import CompetitorScraper
from notifier import Notifier
from datetime import datetime


def load_config():
    """Load configuration"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def run_scraping_job():
    """Job to run scraper and send notifications"""
    print(f"\n{'='*60}")
    print(f"SCHEDULED JOB STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Run scraper
    scraper = CompetitorScraper()
    changes_detected = scraper.scrape_all_competitors()
    
    # Send notifications if changes detected
    if changes_detected > 0:
        print(f"\n{changes_detected} changes detected. Sending notifications...")
        notifier = Notifier()
        notifier.notify_changes()
    else:
        print("\nNo changes detected. Skipping notifications.")
    
    print(f"\n{'='*60}")
    print(f"JOB COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


def main():
    """Main scheduler loop"""
    config = load_config()
    interval_hours = config['scraping']['check_interval_hours']
    
    print("Competitor Tracker Scheduler Started")
    print(f"Check interval: Every {interval_hours} hours")
    print(f"Press Ctrl+C to stop\n")
    
    # Schedule the job
    schedule.every(interval_hours).hours.do(run_scraping_job)
    
    # Run once immediately on startup
    print("Running initial scrape...")
    run_scraping_job()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user")
