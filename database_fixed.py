"""
Database module for competitor tracking - Production Ready
Handles all database operations with proper resource management and error handling
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

logger = logging.getLogger('competitor_dashboard.database')

# Constants
MAX_CONTENT_SIZE = 1_000_000  # 1MB max content storage


class CompetitorDB:
    def __init__(self, db_path="competitor_data.db"):
        self.db_path = db_path
        self.init_database()
        logger.info(f"Database initialized: {db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """Initialize database tables with proper schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Competitors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    website TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Pages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    page_type TEXT NOT NULL,
                    selector TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE,
                    UNIQUE(competitor_id, url)
                )
            ''')
            
            # Snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_name TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    page_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    CONSTRAINT check_content_size CHECK(length(content) <= ?)
                )
            ''', (MAX_CONTENT_SIZE,))
            
            # Changes table
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
            
            # Indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_competitor_url 
                ON snapshots(competitor_name, page_url)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_changes_date 
                ON changes(detected_at DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_competitor_name
                ON competitors(name)
            ''')
            
            conn.commit()
            logger.info("Database schema initialized successfully")
    
    def save_snapshot(self, competitor_name: str, page_url: str, page_type: str, 
                     content_hash: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Save a snapshot of scraped content"""
        # Truncate content if too large
        if len(content) > MAX_CONTENT_SIZE:
            logger.warning(f"Content truncated for {page_url}: {len(content)} bytes")
            content = content[:MAX_CONTENT_SIZE]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO snapshots (competitor_name, page_url, page_type, content_hash, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (competitor_name, page_url, page_type, content_hash, content, 
                 json.dumps(metadata) if metadata else None))
            
            conn.commit()
            snapshot_id = cursor.lastrowid
            logger.debug(f"Snapshot saved: {competitor_name} - {page_url}")
            return snapshot_id
    
    def get_latest_snapshot(self, competitor_name: str, page_url: str) -> Optional[Dict[str, Any]]:
        """Get the most recent snapshot for a specific page"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, content_hash, content, scraped_at, metadata
                FROM snapshots
                WHERE competitor_name = ? AND page_url = ?
                ORDER BY scraped_at DESC
                LIMIT 1
            ''', (competitor_name, page_url))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'content_hash': result[1],
                    'content': result[2],
                    'scraped_at': result[3],
                    'metadata': json.loads(result[4]) if result[4] else None
                }
            return None
    
    def record_change(self, competitor_name: str, page_url: str, page_type: str, 
                     change_description: str, old_content: str, new_content: str) -> int:
        """Record a detected change"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO changes (competitor_name, page_url, page_type, 
                                   change_description, old_content, new_content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (competitor_name, page_url, page_type, change_description, 
                 old_content[:1000], new_content[:1000]))  # Limit stored content
            
            conn.commit()
            change_id = cursor.lastrowid
            logger.info(f"Change recorded: {competitor_name} - {change_description[:50]}")
            return change_id
    
    def get_recent_changes(self, limit: int = 50, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent changes with input validation"""
        # Validate inputs
        if not isinstance(limit, int) or limit < 1:
            limit = 50
        if not isinstance(days, int) or days < 1:
            days = 30
        
        # Cap maximum values
        limit = min(limit, 1000)
        days = min(days, 365)
        
        with self.get_connection() as conn:
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
    
    def get_competitor_stats(self) -> Dict[str, Any]:
        """Get statistics for dashboard"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Use COALESCE for null safety
            cursor.execute('SELECT COUNT(DISTINCT competitor_name) FROM snapshots')
            total_competitors = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM changes')
            total_changes = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*) FROM changes 
                WHERE detected_at >= datetime('now', '-7 days')
            """)
            recent_changes = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT competitor_name, COUNT(*) as change_count
                FROM changes
                GROUP BY competitor_name
                ORDER BY change_count DESC
                LIMIT 1
            ''')
            most_active = cursor.fetchone()
            
            return {
                'total_competitors': total_competitors,
                'total_changes': total_changes,
                'recent_changes': recent_changes,
                'most_active_competitor': most_active[0] if most_active else None,
                'most_active_change_count': most_active[1] if most_active else 0
            }
    
    def get_all_competitors(self) -> List[Dict[str, Any]]:
        """Get list of all competitors with details (legacy method)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    s.competitor_name,
                    COUNT(DISTINCT s.page_url) as page_count,
                    MAX(s.scraped_at) as last_scraped,
                    COALESCE((
                        SELECT COUNT(*) 
                        FROM changes c 
                        WHERE c.competitor_name = s.competitor_name
                    ), 0) as change_count
                FROM snapshots s
                GROUP BY s.competitor_name
                ORDER BY s.competitor_name
            ''')
            
            results = cursor.fetchall()
            
            competitors = []
            for row in results:
                competitors.append({
                    'name': row[0],
                    'page_count': row[1],
                    'last_scraped': row[2],
                    'change_count': row[3]
                })
            
            return competitors
    
    def _ensure_competitor_tables(self, cursor):
        """Ensure competitors and pages tables exist"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                website TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                page_type TEXT NOT NULL,
                selector TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE,
                UNIQUE(competitor_id, url)
            )
        ''')
    
    def add_competitor(self, name: str, website: str, pages: List[Dict[str, str]]) -> bool:
        """Add a new competitor with pages to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure tables exist
                self._ensure_competitor_tables(cursor)
                
                # Insert competitor
                cursor.execute('''
                    INSERT INTO competitors (name, website)
                    VALUES (?, ?)
                ''', (name, website))
                
                competitor_id = cursor.lastrowid
                
                # Insert pages
                for page in pages:
                    cursor.execute('''
                        INSERT INTO pages (competitor_id, url, page_type, selector)
                        VALUES (?, ?, ?, ?)
                    ''', (competitor_id, page['url'], page['type'], page.get('selector', '')))
                
                conn.commit()
                logger.info(f"Competitor added: {name} with {len(pages)} pages")
                return True
                
        except sqlite3.IntegrityError as e:
            logger.warning(f"Failed to add competitor {name}: {e}")
            return False
    
    def update_competitor(self, old_name: str, new_name: str, website: str, 
                         pages: List[Dict[str, str]]) -> bool:
        """Update competitor information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get competitor ID
                cursor.execute('SELECT id FROM competitors WHERE name = ?', (old_name,))
                result = cursor.fetchone()
                
                if not result:
                    logger.warning(f"Competitor not found for update: {old_name}")
                    return False
                
                competitor_id = result[0]
                
                # Update competitor
                cursor.execute('''
                    UPDATE competitors 
                    SET name = ?, website = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_name, website, competitor_id))
                
                # Delete old pages
                cursor.execute('DELETE FROM pages WHERE competitor_id = ?', (competitor_id,))
                
                # Insert new pages
                for page in pages:
                    cursor.execute('''
                        INSERT INTO pages (competitor_id, url, page_type, selector)
                        VALUES (?, ?, ?, ?)
                    ''', (competitor_id, page['url'], page['type'], page.get('selector', '')))
                
                # Update snapshots and changes if name changed
                if old_name != new_name:
                    cursor.execute('''
                        UPDATE snapshots 
                        SET competitor_name = ? 
                        WHERE competitor_name = ?
                    ''', (new_name, old_name))
                    
                    cursor.execute('''
                        UPDATE changes 
                        SET competitor_name = ? 
                        WHERE competitor_name = ?
                    ''', (new_name, old_name))
                
                conn.commit()
                logger.info(f"Competitor updated: {old_name} -> {new_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating competitor {old_name}: {e}")
            return False
    
    def get_competitor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get competitor details by name"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, name, website
                    FROM competitors
                    WHERE name = ?
                ''', (name,))
                
                result = cursor.fetchone()
                
                if not result:
                    return None
                
                competitor_id, name, website = result
                
                # Get pages
                cursor.execute('''
                    SELECT url, page_type, selector
                    FROM pages
                    WHERE competitor_id = ?
                    ORDER BY created_at
                ''', (competitor_id,))
                
                pages = []
                for row in cursor.fetchall():
                    pages.append({
                        'url': row[0],
                        'type': row[1],
                        'selector': row[2] or ''
                    })
                
                return {
                    'name': name,
                    'website': website or '',
                    'pages': pages
                }
                
        except sqlite3.OperationalError:
            # Table doesn't exist
            return None
    
    def get_all_competitors_from_db(self) -> List[Dict[str, Any]]:
        """Get all competitors with their pages from database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, name, website
                    FROM competitors
                    ORDER BY name
                ''')
                
                competitors = []
                for row in cursor.fetchall():
                    competitor_id, name, website = row
                    
                    # Get pages for this competitor
                    cursor.execute('''
                        SELECT url, page_type, selector
                        FROM pages
                        WHERE competitor_id = ?
                        ORDER BY created_at
                    ''', (competitor_id,))
                    
                    pages = []
                    for page_row in cursor.fetchall():
                        pages.append({
                            'url': page_row[0],
                            'type': page_row[1],
                            'selector': page_row[2] or ''
                        })
                    
                    competitors.append({
                        'name': name,
                        'website': website or '',
                        'pages': pages
                    })
                
                return competitors
                
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return []
    
    def delete_competitor_from_db(self, name: str) -> bool:
        """Delete competitor and all associated data from database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get competitor ID
                cursor.execute('SELECT id FROM competitors WHERE name = ?', (name,))
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                competitor_id = result[0]
                
                # Delete pages (will cascade delete due to foreign key)
                cursor.execute('DELETE FROM pages WHERE competitor_id = ?', (competitor_id,))
                
                # Delete competitor
                cursor.execute('DELETE FROM competitors WHERE id = ?', (competitor_id,))
                
                # Delete snapshots and changes
                cursor.execute('DELETE FROM snapshots WHERE competitor_name = ?', (name,))
                cursor.execute('DELETE FROM changes WHERE competitor_name = ?', (name,))
                
                conn.commit()
                logger.info(f"Competitor deleted: {name}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting competitor {name}: {e}")
            return False
    
    def get_competitor_pages(self, competitor_name: str) -> List[Dict[str, str]]:
        """Get all pages tracked for a competitor (legacy method)"""
        with self.get_connection() as conn:
            cursor = cursor.cursor()
            
            cursor.execute('''
                SELECT DISTINCT page_url, page_type
                FROM snapshots
                WHERE competitor_name = ?
                ORDER BY page_url
            ''', (competitor_name,))
            
            results = cursor.fetchall()
            
            pages = []
            for row in results:
                pages.append({
                    'url': row[0],
                    'type': row[1]
                })
            
            return pages
