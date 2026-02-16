import sqlite3
import json
import yaml
import os

def restore_config():
    print("Restoring config from database...")
    
    # Connect to DB
    conn = sqlite3.connect('competitor_data.db')
    cursor = conn.cursor()
    
    # Get all competitors
    cursor.execute("SELECT DISTINCT competitor_name FROM snapshots")
    competitors = [row[0] for row in cursor.fetchall()]
    
    config_competitors = []
    
    for comp_name in competitors:
        print(f"Processing {comp_name}...")
        
        # Get website (try to find a homepage or just leave empty)
        # We don't store the main website URL explicitly in snapshots, so we'll leave it empty or try to infer
        website = "" 
        
        # Get pages
        cursor.execute("""
            SELECT DISTINCT page_url, page_type 
            FROM snapshots 
            WHERE competitor_name = ?
        """, (comp_name,))
        
        pages_rows = cursor.fetchall()
        pages_config = []
        
        for url, ptype in pages_rows:
            # Get latest selector from metadata
            cursor.execute("""
                SELECT metadata 
                FROM snapshots 
                WHERE competitor_name = ? AND page_url = ? 
                ORDER BY scraped_at DESC 
                LIMIT 1
            """, (comp_name, url))
            
            meta_row = cursor.fetchone()
            selector = ""
            if meta_row and meta_row[0]:
                try:
                    meta = json.loads(meta_row[0])
                    selector = meta.get('selector', '')
                except:
                    pass
            
            pages_config.append({
                "url": url,
                "type": ptype,
                "selector": selector
            })
        
        config_competitors.append({
            "name": comp_name,
            "website": website,
            "pages": pages_config
        })
    
    conn.close()
    
    # Read existing config
    if os.path.exists('config.yaml'):
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {'dashboard': {'host': '0.0.0.0', 'port': 5000, 'debug': True}, 'scraping': {}}
    
    # Update competitors
    config['competitors'] = config_competitors
    
    # Write back
    with open('config.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"Restored {len(config_competitors)} competitors to config.yaml")

if __name__ == "__main__":
    restore_config()
