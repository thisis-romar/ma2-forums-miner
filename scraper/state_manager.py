"""
State management for MA2 Forums Miner using SQLAlchemy.

This module replaces the simple manifest.json with a robust SQLite database
to track thread scraping state, metadata, and enable smart update detection.

Key improvements over manifest.json:
- ACID compliance (no corruption on crashes)
- Track when threads were scraped (last_scraped_at)
- Track metadata like reply_count and view_count for update detection
- Query capabilities for advanced filtering
- Foundation for future "smart updates" feature
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models using modern declarative style."""
    pass


class ThreadState(Base):
    """
    SQLAlchemy model representing the state of a scraped thread.
    
    This stores metadata about each thread we've scraped, enabling:
    - Delta scraping (only scrape new threads)
    - Update detection (detect when threads have new replies)
    - Audit trails (track when threads were last scraped)
    
    Attributes:
        thread_id: Primary key, unique identifier from forum URL
        url: Full URL to the thread
        title: Thread title/subject line
        last_scraped_at: Timestamp when this thread was last scraped
        reply_count: Number of replies when last scraped (for update detection)
        view_count: Number of views when last scraped (for monitoring)
    """
    __tablename__ = "thread_state"
    
    thread_id: str = Column(String, primary_key=True)
    url: str = Column(String, nullable=False)
    title: str = Column(String, nullable=False)
    last_scraped_at: datetime = Column(DateTime, nullable=False)
    reply_count: int = Column(Integer, nullable=False, default=0)
    view_count: int = Column(Integer, nullable=False, default=0)
    
    def __repr__(self) -> str:
        return (
            f"ThreadState(thread_id={self.thread_id!r}, "
            f"title={self.title!r}, "
            f"last_scraped_at={self.last_scraped_at})"
        )


class StateManager:
    """
    Manages the SQLite database for thread state tracking.
    
    This class provides a clean interface for interacting with the thread
    state database, abstracting away SQLAlchemy details from the scraper.
    
    Usage:
        state_manager = StateManager("scraper_state.db")
        
        # Check if a thread needs scraping
        if state_manager.should_scrape("12345"):
            # Scrape the thread...
            metadata = scrape_thread(url)
            
            # Update the database
            state_manager.update_thread_state({
                'thread_id': "12345",
                'url': url,
                'title': metadata.title,
                'reply_count': metadata.replies,
                'view_count': metadata.views
            })
    """
    
    def __init__(self, db_path: str = "scraper_state.db"):
        """
        Initialize the state manager and database.
        
        Creates the database file and tables if they don't exist.
        Uses SQLite for simplicity and zero-configuration deployment.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        
        # Create SQLite engine
        # echo=False disables SQL logging for cleaner output
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False
        )
        
        # Create all tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False
        )
        
        print(f"📊 State manager initialized: {self.db_path}")
    
    def should_scrape(self, thread_id: str) -> bool:
        """
        Check if a thread should be scraped.
        
        Currently this is a simple existence check - if the thread is in
        the database, we've already scraped it, so return False.
        
        Future enhancement: Could check last_scraped_at and reply_count
        to determine if a thread needs re-scraping for updates.
        
        Args:
            thread_id: Unique thread identifier
            
        Returns:
            True if thread should be scraped, False if already scraped
        """
        with self.SessionLocal() as session:
            existing = session.query(ThreadState).filter_by(
                thread_id=thread_id
            ).first()
            return existing is None
    
    def update_thread_state(self, metadata: Dict[str, any]) -> None:
        """
        Update or insert thread state after successful scraping.
        
        This method is called after a thread is successfully scraped to
        record its state in the database. Uses upsert logic to handle
        both new threads and updates to existing threads.
        
        Args:
            metadata: Dictionary containing thread metadata with keys:
                - thread_id (str): Unique thread identifier
                - url (str): Full thread URL
                - title (str): Thread title
                - reply_count (int): Number of replies
                - view_count (int): Number of views
                
        Example:
            state_manager.update_thread_state({
                'thread_id': '30890',
                'url': 'https://forum.malighting.com/forum/thread/30890-...',
                'title': 'Moving Fixtures Between Layers',
                'reply_count': 5,
                'view_count': 1234
            })
        """
        with self.SessionLocal() as session:
            try:
                # Check if thread already exists
                existing = session.query(ThreadState).filter_by(
                    thread_id=metadata['thread_id']
                ).first()
                
                if existing:
                    # Update existing record
                    existing.url = metadata['url']
                    existing.title = metadata['title']
                    existing.last_scraped_at = datetime.utcnow()
                    existing.reply_count = metadata.get('reply_count', 0)
                    existing.view_count = metadata.get('view_count', 0)
                else:
                    # Create new record
                    thread_state = ThreadState(
                        thread_id=metadata['thread_id'],
                        url=metadata['url'],
                        title=metadata['title'],
                        last_scraped_at=datetime.utcnow(),
                        reply_count=metadata.get('reply_count', 0),
                        view_count=metadata.get('view_count', 0)
                    )
                    session.add(thread_state)
                
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"⚠️  Warning: Could not update thread state: {e}")
                raise
    
    def get_visited_set(self) -> Set[str]:
        """
        Get a set of all visited thread URLs.
        
        This method provides backward compatibility with the old manifest.json
        system by returning a set of URLs that have been scraped.
        
        Returns:
            Set of thread URLs that have been scraped
            
        Usage:
            visited_urls = state_manager.get_visited_set()
            new_threads = [url for url in all_urls if url not in visited_urls]
        """
        with self.SessionLocal() as session:
            threads = session.query(ThreadState).all()
            return {thread.url for thread in threads}
    
    def get_thread_count(self) -> int:
        """
        Get the total number of threads in the database.
        
        Returns:
            Total count of scraped threads
        """
        with self.SessionLocal() as session:
            return session.query(ThreadState).count()
    
    def get_thread_state(self, thread_id: str) -> Optional[ThreadState]:
        """
        Get the state record for a specific thread.
        
        Args:
            thread_id: Unique thread identifier
            
        Returns:
            ThreadState object if found, None otherwise
        """
        with self.SessionLocal() as session:
            return session.query(ThreadState).filter_by(
                thread_id=thread_id
            ).first()
