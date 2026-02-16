"""
Database module for competitor tracking
Handles all database operations using SQLite
"""

import sqlite3
import json
from datetime import datetime


class CompetitorDB:
    def __init__(self, db_path="competitor_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create a database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_name TEXT NOT NULL,
                page_url TEXT NOT NULL,
                page_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_name TEXT NOT NULL,
                page_url TEXT NOT NULL,
                page_type TEXT NOT NULL,
                change_description TEXT,
                old_content TEXT,
                new_content TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_competitor_url 
            ON snapshots(competitor_name, page_url)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_changes_date 
            ON changes(detected_at DESC)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_snapshot(self, competitor_name, page_url, page_type, content_hash, content, metadata=None):
        """Save a snapshot of scraped content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO snapshots (competitor_name, page_url, page_type, content_hash, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (competitor_name, page_url, page_type, content_hash, content, json.dumps(metadata) if metadata else None))
        
        conn.commit()
        snapshot_id = cursor.lastrowid
        conn.close()
        
        return snapshot_id
    
    def get_latest_snapshot(self, competitor_name, page_url):
        """Get the most recent snapshot for a specific page"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, content_hash, content, scraped_at, metadata
            FROM snapshots
            WHERE competitor_name = ? AND page_url = ?
            ORDER BY scraped_at DESC
            LIMIT 1
        ''', (competitor_name, page_url))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'content_hash': result[1],
                'content': result[2],
                'scraped_at': result[3],
                'metadata': json.loads(result[4]) if result[4] else None
            }
        return None
    
    def record_change(self, competitor_name, page_url, page_type, change_description, old_content, new_content):
        """Record a detected change"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO changes (competitor_name, page_url, page_type, change_description, old_content, new_content)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (competitor_name, page_url, page_type, change_description, old_content, new_content))
        
        conn.commit()
        change_id = cursor.lastrowid
        conn.close()
        
        return change_id
    
    def get_recent_changes(self, limit=50, days=30):
        """Get recent changes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, competitor_name, page_url, page_type, change_description, 
                   old_content, new_content, detected_at, notified
            FROM changes
            WHERE detected_at >= datetime('now', '-' || ? || ' days')
            ORDER BY detected_at DESC
            LIMIT ?
        ''', (days, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        changes = []
        for row in results:
            changes.append({
                'id': row[0],
                'competitor_name': row[1],
                'page_url': row[2],
                'page_type': row[3],
                'change_description': row[4],
                'old_content': row[5],
                'new_content': row[6],
                'detected_at': row[7],
                'notified': bool(row[8])
            })
        
        return changes
    
    def get_unnotified_changes(self):
        """Get changes that haven't been sent in notifications yet"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, competitor_name, page_url, page_type, change_description, detected_at
            FROM changes
            WHERE notified = 0
            ORDER BY detected_at DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        changes = []
        for row in results:
            changes.append({
                'id': row[0],
                'competitor_name': row[1],
                'page_url': row[2],
                'page_type': row[3],
                'change_description': row[4],
                'detected_at': row[5]
            })
        
        return changes
    
    def mark_changes_notified(self, change_ids):
        """Mark changes as notified"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(change_ids))
        cursor.execute(f'''
            UPDATE changes
            SET notified = 1
            WHERE id IN ({placeholders})
        ''', change_ids)
        
        conn.commit()
        conn.close()
    
    def get_competitor_stats(self):
        """Get statistics for dashboard"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT competitor_name) FROM snapshots')
        total_competitors = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM changes')
        total_changes = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM changes WHERE detected_at >= datetime('now', '-7 days')")
        recent_changes = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT competitor_name, COUNT(*) as change_count
            FROM changes
            GROUP BY competitor_name
            ORDER BY change_count DESC
            LIMIT 1
        ''')
        most_active = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_competitors': total_competitors,
            'total_changes': total_changes,
            'recent_changes': recent_changes,
            'most_active_competitor': most_active[0] if most_active else None,
            'most_active_change_count': most_active[1] if most_active else 0
        }
    
    def get_all_competitors(self):
        """Get list of all competitors with details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                s.competitor_name,
                COUNT(DISTINCT s.page_url) as page_count,
                MAX(s.scraped_at) as last_scraped,
                COALESCE(COUNT(DISTINCT c.id), 0) as change_count
            FROM snapshots s
            LEFT JOIN changes c ON s.competitor_name = c.competitor_name
            GROUP BY s.competitor_name
            ORDER BY s.competitor_name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        competitors = []
        for row in results:
            competitors.append({
                'name': row[0],
                'page_count': row[1],
                'last_scraped': row[2],
                'change_count': row[3]
            })
        
        return competitors
    
    def delete_competitor(self, competitor_name):
        """Delete all data for a competitor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM snapshots WHERE competitor_name = ?', (competitor_name,))
        cursor.execute('DELETE FROM changes WHERE competitor_name = ?', (competitor_name,))
        
        conn.commit()
        rows_deleted = cursor.rowcount
        conn.close()
        
        return rows_deleted > 0
    
    def get_competitor_pages(self, competitor_name):
        """Get all pages tracked for a competitor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT page_url, page_type
            FROM snapshots
            WHERE competitor_name = ?
        ''', (competitor_name,))
        
        results = cursor.fetchall()
        conn.close()
        
        pages = []
        for row in results:
            pages.append({
                'url': row[0],
                'type': row[1]
            })
        
        return pages
