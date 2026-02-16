"""
Demo script to test the competitor tracker with example data
This creates sample data so you can see the dashboard in action
"""

from database import CompetitorDB
from datetime import datetime, timedelta
import random


def generate_demo_data():
    """Generate sample data for testing"""
    db = CompetitorDB()
    
    print("Generating demo data...")
    
    competitors = [
        {"name": "Acme Corp", "url": "https://acme.com/features"},
        {"name": "TechStart Inc", "url": "https://techstart.io/pricing"},
        {"name": "InnovateCo", "url": "https://innovateco.com/products"},
        {"name": "GlobalSoft", "url": "https://globalsoft.com/features"},
    ]
    
    page_types = ["features", "pricing", "blog"]
    
    # Generate snapshots
    print("Creating snapshots...")
    for i in range(20):
        comp = random.choice(competitors)
        page_type = random.choice(page_types)
        
        content = f"Sample content for {comp['name']} - {page_type} - Version {i}"
        content_hash = f"hash_{i}_{random.randint(1000, 9999)}"
        
        db.save_snapshot(
            competitor_name=comp['name'],
            page_url=comp['url'],
            page_type=page_type,
            content_hash=content_hash,
            content=content,
            metadata={"demo": True, "version": i}
        )
    
    # Generate some changes
    print("Creating change records...")
    changes = [
        {
            "competitor": "Acme Corp",
            "url": "https://acme.com/features",
            "type": "features",
            "desc": "Added new AI-powered analytics feature",
            "days_ago": 1
        },
        {
            "competitor": "TechStart Inc",
            "url": "https://techstart.io/pricing",
            "type": "pricing",
            "desc": "Reduced Enterprise plan price by 15%",
            "days_ago": 2
        },
        {
            "competitor": "InnovateCo",
            "url": "https://innovateco.com/products",
            "type": "features",
            "desc": "Launched mobile app integration",
            "days_ago": 3
        },
        {
            "competitor": "GlobalSoft",
            "url": "https://globalsoft.com/features",
            "type": "features",
            "desc": "Added real-time collaboration tools",
            "days_ago": 5
        },
        {
            "competitor": "Acme Corp",
            "url": "https://acme.com/blog",
            "type": "blog",
            "desc": "Published case study about Fortune 500 client",
            "days_ago": 7
        },
        {
            "competitor": "TechStart Inc",
            "url": "https://techstart.io/features",
            "type": "features",
            "desc": "Released API v2 with webhooks support",
            "days_ago": 10
        },
    ]
    
    for change in changes:
        db.record_change(
            competitor_name=change["competitor"],
            page_url=change["url"],
            page_type=change["type"],
            change_description=change["desc"],
            old_content="Previous version of content...",
            new_content="Updated version with changes..."
        )
    
    print(f"\n✓ Demo data generated successfully!")
    print(f"  - Created {len(competitors)} competitor records")
    print(f"  - Created 20 sample snapshots")
    print(f"  - Created {len(changes)} sample changes")
    print(f"\nNow run: python dashboard.py")
    print(f"Then open: http://localhost:5000\n")


if __name__ == "__main__":
    generate_demo_data()
