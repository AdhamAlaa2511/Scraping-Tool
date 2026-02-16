"""
Notification module for competitor tracking
Sends email and Slack alerts when changes are detected
"""

import smtplib
import requests
import yaml
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import CompetitorDB


class Notifier:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.db = CompetitorDB()
        self.email_config = self.config['notifications']['email']
        self.slack_config = self.config['notifications']['slack']
    
    def send_email(self, subject, body):
        """Send email notification"""
        if not self.email_config['enabled']:
            print("Email notifications disabled")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipient_emails'])
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(
                self.email_config['smtp_server'], 
                self.email_config['smtp_port']
            )
            server.starttls()
            server.login(
                self.email_config['sender_email'], 
                self.email_config['sender_password']
            )
            
            server.send_message(msg)
            server.quit()
            
            print(f"✓ Email sent to {len(self.email_config['recipient_emails'])} recipients")
            return True
            
        except Exception as e:
            print(f"✗ Error sending email: {str(e)}")
            return False
    
    def send_slack(self, message):
        """Send Slack notification"""
        if not self.slack_config['enabled']:
            print("Slack notifications disabled")
            return False
        
        try:
            payload = {
                "text": message,
                "username": "Competitor Tracker",
                "icon_emoji": ":mag:"
            }
            
            response = requests.post(
                self.slack_config['webhook_url'],
                json=payload
            )
            
            if response.status_code == 200:
                print("✓ Slack notification sent")
                return True
            else:
                print(f"✗ Slack notification failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Error sending Slack notification: {str(e)}")
            return False
    
    def format_changes_for_email(self, changes):
        """Format changes into email body"""
        if not changes:
            return "No new changes to report."
        
        body = f"COMPETITOR CHANGES DETECTED\n"
        body += f"{'='*60}\n\n"
        body += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body += f"Total Changes: {len(changes)}\n\n"
        
        # Group by competitor
        by_competitor = {}
        for change in changes:
            comp_name = change['competitor_name']
            if comp_name not in by_competitor:
                by_competitor[comp_name] = []
            by_competitor[comp_name].append(change)
        
        for competitor, comp_changes in by_competitor.items():
            body += f"\n{competitor}\n"
            body += f"{'-'*len(competitor)}\n"
            
            for change in comp_changes:
                body += f"\n  • {change['page_type'].upper()}\n"
                body += f"    Change: {change['change_description']}\n"
                body += f"    URL: {change['page_url']}\n"
                body += f"    Detected: {change['detected_at']}\n"
        
        body += f"\n{'='*60}\n"
        body += f"\nView full details in your dashboard.\n"
        
        return body
    
    def format_changes_for_slack(self, changes):
        """Format changes into Slack message"""
        if not changes:
            return "No new changes detected."
        
        message = f"🔍 *Competitor Changes Detected* ({len(changes)} updates)\n\n"
        
        # Group by competitor
        by_competitor = {}
        for change in changes:
            comp_name = change['competitor_name']
            if comp_name not in by_competitor:
                by_competitor[comp_name] = []
            by_competitor[comp_name].append(change)
        
        for competitor, comp_changes in by_competitor.items():
            message += f"*{competitor}*\n"
            
            for change in comp_changes:
                message += f"  • {change['page_type'].title()}: {change['change_description']}\n"
                message += f"    <{change['page_url']}|View Page>\n"
        
        return message
    
    def notify_changes(self):
        """Check for unnotified changes and send notifications"""
        changes = self.db.get_unnotified_changes()
        
        if not changes:
            print("No new changes to notify")
            return
        
        print(f"\nNotifying {len(changes)} new changes...")
        
        # Send email
        if self.email_config['enabled']:
            email_body = self.format_changes_for_email(changes)
            subject = f"Competitor Alert: {len(changes)} Changes Detected"
            self.send_email(subject, email_body)
        
        # Send Slack
        if self.slack_config['enabled']:
            slack_message = self.format_changes_for_slack(changes)
            self.send_slack(slack_message)
        
        # Mark changes as notified
        change_ids = [c['id'] for c in changes]
        self.db.mark_changes_notified(change_ids)
        
        print(f"✓ {len(changes)} changes marked as notified")


if __name__ == "__main__":
    notifier = Notifier()
    notifier.notify_changes()
