#!/usr/bin/env python3
"""Example script demonstrating MA2 Forums Miner usage."""

import asyncio
import sys
from pathlib import Path

# Add src to path if running from repository
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ma2_miner.scraper import ForumScraper
from ma2_miner.downloader import Downloader
from ma2_miner.manifest import Manifest
from ma2_miner.clustering import ThreadClusterer


async def example_scraper():
    """Example of using the scraper directly."""
    print("="*60)
    print("Example 1: Basic Scraper Usage")
    print("="*60)
    
    async with ForumScraper() as scraper:
        # Get first page of threads
        print("\nFetching first page of threads...")
        first_page = await scraper.get_thread_list_page(1)
        max_pages = scraper.get_max_page_number(first_page)
        threads = scraper.extract_threads_from_page(first_page)
        
        print(f"Found {len(threads)} threads on first page")
        print(f"Total pages: {max_pages}")
        
        if threads:
            print(f"\nFirst thread:")
            print(f"  ID: {threads[0]['thread_id']}")
            print(f"  Title: {threads[0]['title']}")
            print(f"  Author: {threads[0]['author']}")
            print(f"  Replies: {threads[0]['replies']}")
            print(f"  Views: {threads[0]['views']}")


async def example_detailed_thread():
    """Example of getting detailed thread information."""
    print("\n" + "="*60)
    print("Example 2: Thread Details")
    print("="*60)
    
    async with ForumScraper() as scraper:
        # Get first thread
        first_page = await scraper.get_thread_list_page(1)
        threads = scraper.extract_threads_from_page(first_page)
        
        if threads:
            thread = threads[0]
            print(f"\nGetting details for: {thread['title']}")
            
            details = await scraper.get_thread_details(thread['url'])
            
            print(f"Posts: {len(details['posts'])}")
            print(f"Attachments: {len(details['attachments'])}")
            
            if details['attachments']:
                print("\nAttachments:")
                for att in details['attachments'][:3]:
                    print(f"  - {att['filename']}")


def example_manifest():
    """Example of using the manifest for delta scraping."""
    print("\n" + "="*60)
    print("Example 3: Manifest Usage")
    print("="*60)
    
    # Create a test manifest
    manifest = Manifest("/tmp/example_manifest.json")
    
    # Mark some threads as scraped
    manifest.mark_thread_scraped(
        "12345",
        {"title": "Example Thread", "url": "https://example.com"},
        "/tmp/output/12345",
        5
    )
    
    manifest.mark_thread_scraped(
        "67890",
        {"title": "Another Thread", "url": "https://example.com"},
        "/tmp/output/67890",
        3
    )
    
    manifest.save()
    
    # Load and display stats
    manifest2 = Manifest("/tmp/example_manifest.json")
    stats = manifest2.get_statistics()
    
    print(f"\nManifest statistics:")
    print(f"  Total threads: {stats['total_threads']}")
    print(f"  Total attachments: {stats['total_attachments']}")
    print(f"  Total posts: {stats['total_posts']}")
    
    print(f"\nScraped thread IDs: {manifest2.get_scraped_thread_ids()}")
    
    # Check if thread is scraped
    print(f"\nIs thread 12345 scraped? {manifest2.is_thread_scraped('12345')}")
    print(f"Is thread 99999 scraped? {manifest2.is_thread_scraped('99999')}")


def example_clustering():
    """Example of using the clustering module."""
    print("\n" + "="*60)
    print("Example 4: Clustering")
    print("="*60)
    
    print("\nNote: This requires scraped data in the output directory.")
    print("Run 'ma2-miner scrape' first, then use:")
    print("  ma2-miner cluster --output-dir output")
    print("\nThe clustering module will:")
    print("  1. Load all threads from metadata.json files")
    print("  2. Generate semantic embeddings using sentence-transformers")
    print("  3. Cluster threads using HDBSCAN")
    print("  4. Save results to clusters.json")


async def main():
    """Run all examples."""
    print("\nMA2 Forums Miner - Examples")
    print("="*60)
    
    # Example 1: Basic scraper
    await example_scraper()
    
    # Example 2: Detailed thread
    await example_detailed_thread()
    
    # Example 3: Manifest
    example_manifest()
    
    # Example 4: Clustering info
    example_clustering()
    
    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)
    print("\nFor full scraping, use:")
    print("  ma2-miner scrape")
    print("\nFor clustering:")
    print("  ma2-miner cluster")
    print("\nFor statistics:")
    print("  ma2-miner stats")
    print()


if __name__ == "__main__":
    asyncio.run(main())
