"""CLI interface for MA2 Forums Miner."""

import asyncio
import json
from pathlib import Path

import click
import aiohttp

from .scraper import ForumScraper
from .downloader import Downloader
from .manifest import Manifest
from .clustering import ThreadClusterer


@click.group()
def main():
    """MA2 Forums Miner - Async scraper and clustering for GrandMA2 Macro Share forum."""
    pass


@main.command()
@click.option(
    '--output-dir',
    default='output',
    help='Output directory for scraped data'
)
@click.option(
    '--manifest',
    default='manifest.json',
    help='Path to manifest file'
)
@click.option(
    '--full',
    is_flag=True,
    help='Force full scrape (ignore manifest)'
)
@click.option(
    '--no-attachments',
    is_flag=True,
    help='Skip downloading attachments'
)
def scrape(output_dir, manifest, full, no_attachments):
    """Scrape threads from the forum."""
    asyncio.run(_scrape(output_dir, manifest, full, no_attachments))


async def _scrape(output_dir: str, manifest_path: str, full: bool, no_attachments: bool):
    """Async scraping implementation."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load manifest
    manifest_obj = Manifest(manifest_path)
    
    if full:
        print("Running full scrape (ignoring manifest)...")
    else:
        stats = manifest_obj.get_statistics()
        print(f"Loaded manifest: {stats['total_threads']} threads already scraped")
        
    # Create session
    async with aiohttp.ClientSession() as session:
        scraper = ForumScraper(session)
        downloader = Downloader(output_dir, session)
        
        # Get all threads
        print("Fetching thread list...")
        threads = await scraper.get_all_threads()
        print(f"Found {len(threads)} threads")
        
        # Filter threads based on manifest
        if not full:
            scraped_ids = manifest_obj.get_scraped_thread_ids()
            threads = [t for t in threads if t['thread_id'] not in scraped_ids]
            print(f"New threads to scrape: {len(threads)}")
            
        if not threads:
            print("No new threads to scrape!")
            return
            
        # Scrape each thread
        for i, thread in enumerate(threads, 1):
            thread_id = thread['thread_id']
            print(f"\n[{i}/{len(threads)}] Scraping thread {thread_id}: {thread['title']}")
            
            try:
                # Get thread details
                details = await scraper.get_thread_details(thread['url'])
                
                # Merge metadata
                thread_data = {**thread, **details}
                
                # Create thread directory
                safe_title = "".join(c for c in thread['title'] if c.isalnum() or c in (' ', '-', '_'))[:50]
                thread_dir = output_path / f"{thread_id}_{safe_title}"
                thread_dir.mkdir(parents=True, exist_ok=True)
                
                # Download attachments
                downloaded = []
                if not no_attachments and details['attachments']:
                    print(f"  Downloading {len(details['attachments'])} attachments...")
                    downloaded = await downloader.download_attachments(
                        details['attachments'],
                        thread_dir
                    )
                    print(f"  Downloaded {len(downloaded)} attachments")
                    
                # Save metadata
                thread_data['downloaded_attachments'] = downloaded
                metadata_file = thread_dir / "metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(thread_data, f, indent=2, ensure_ascii=False)
                    
                # Update manifest
                manifest_obj.mark_thread_scraped(
                    thread_id,
                    thread_data,
                    str(thread_dir),
                    len(downloaded)
                )
                manifest_obj.save()
                
                print(f"  Saved to {thread_dir}")
                
                # Be nice to the server
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"  Error scraping thread {thread_id}: {e}")
                continue
                
    # Print final statistics
    final_stats = manifest_obj.get_statistics()
    print("\n" + "="*60)
    print("Scraping complete!")
    print(f"Total threads scraped: {final_stats['total_threads']}")
    print(f"Total attachments: {final_stats['total_attachments']}")
    print(f"Total posts: {final_stats['total_posts']}")
    print("="*60)


@main.command()
@click.option(
    '--output-dir',
    default='output',
    help='Directory containing scraped data'
)
@click.option(
    '--model',
    default='all-MiniLM-L6-v2',
    help='Sentence transformer model name'
)
@click.option(
    '--min-cluster-size',
    default=5,
    type=int,
    help='Minimum cluster size for HDBSCAN'
)
@click.option(
    '--result-file',
    default='clusters.json',
    help='Output file for clustering results'
)
def cluster(output_dir, model, min_cluster_size, result_file):
    """Run NLP clustering on scraped threads."""
    clusterer = ThreadClusterer(model, min_cluster_size)
    results = clusterer.run_clustering_pipeline(output_dir, result_file)
    
    if results:
        print("\nCluster Summary:")
        for cluster_id, info in results.get('cluster_info', {}).items():
            if cluster_id == 'noise':
                continue
            print(f"\nCluster {cluster_id}:")
            print(f"  Size: {info['size']}")
            print(f"  Representative: {info['representative_title']}")


@main.command()
@click.option(
    '--manifest',
    default='manifest.json',
    help='Path to manifest file'
)
def stats(manifest):
    """Show statistics about scraped data."""
    manifest_obj = Manifest(manifest)
    stats = manifest_obj.get_statistics()
    
    print("\n" + "="*60)
    print("MA2 Forums Miner Statistics")
    print("="*60)
    print(f"Total threads scraped: {stats['total_threads']}")
    print(f"Total attachments: {stats['total_attachments']}")
    print(f"Total posts: {stats['total_posts']}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
