"""NLP clustering module using sentence-transformers and HDBSCAN."""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    print("Warning: HDBSCAN not available. Install with: pip install hdbscan")


class ThreadClusterer:
    """NLP-based clustering for forum threads."""
    
    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        min_cluster_size: int = 5
    ):
        """Initialize the clusterer.
        
        Args:
            model_name: Sentence transformer model name
            min_cluster_size: Minimum cluster size for HDBSCAN
        """
        self.model_name = model_name
        self.min_cluster_size = min_cluster_size
        self.model: Optional[SentenceTransformer] = None
        
    def load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            print(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
    def load_threads_from_output(self, output_dir: str) -> List[Dict]:
        """Load thread data from output directory.
        
        Args:
            output_dir: Directory containing thread folders
            
        Returns:
            List of thread dictionaries with metadata
        """
        threads = []
        output_path = Path(output_dir)
        
        if not output_path.exists():
            print(f"Output directory not found: {output_dir}")
            return threads
            
        # Find all metadata.json files
        for thread_dir in output_path.iterdir():
            if not thread_dir.is_dir():
                continue
                
            metadata_file = thread_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        thread_data = json.load(f)
                        thread_data['_dir'] = str(thread_dir)
                        threads.append(thread_data)
                except Exception as e:
                    print(f"Error loading {metadata_file}: {e}")
                    
        return threads
        
    def extract_text_for_embedding(self, thread: Dict) -> str:
        """Extract text from thread for embedding.
        
        Args:
            thread: Thread dictionary
            
        Returns:
            Combined text for embedding
        """
        texts = []
        
        # Add title
        title = thread.get('title', '')
        if title:
            texts.append(title)
            
        # Add post contents
        posts = thread.get('posts', [])
        for post in posts[:10]:  # Limit to first 10 posts
            content = post.get('content', '')
            if content:
                texts.append(content)
                
        # Combine with space
        combined = ' '.join(texts)
        
        # Truncate to reasonable length (8000 chars)
        if len(combined) > 8000:
            combined = combined[:8000]
            
        return combined
        
    def generate_embeddings(self, threads: List[Dict]) -> np.ndarray:
        """Generate embeddings for threads.
        
        Args:
            threads: List of thread dictionaries
            
        Returns:
            Numpy array of embeddings
        """
        self.load_model()
        
        # Extract text from each thread
        texts = [self.extract_text_for_embedding(t) for t in threads]
        
        # Generate embeddings
        print(f"Generating embeddings for {len(texts)} threads...")
        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        return embeddings
        
    def cluster_threads(
        self,
        threads: List[Dict],
        embeddings: Optional[np.ndarray] = None
    ) -> Tuple[List[int], Dict]:
        """Cluster threads using HDBSCAN.
        
        Args:
            threads: List of thread dictionaries
            embeddings: Optional pre-computed embeddings
            
        Returns:
            Tuple of (cluster labels, cluster info dict)
        """
        if not HDBSCAN_AVAILABLE:
            print("HDBSCAN not available. Returning dummy clusters.")
            return [-1] * len(threads), {}
            
        # Generate embeddings if not provided
        if embeddings is None:
            embeddings = self.generate_embeddings(threads)
            
        # Perform clustering
        print("Performing HDBSCAN clustering...")
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        
        labels = clusterer.fit_predict(embeddings)
        
        # Analyze clusters
        cluster_info = self._analyze_clusters(threads, labels, embeddings)
        
        return labels.tolist(), cluster_info
        
    def _analyze_clusters(
        self,
        threads: List[Dict],
        labels: np.ndarray,
        embeddings: np.ndarray
    ) -> Dict:
        """Analyze cluster composition and characteristics.
        
        Args:
            threads: List of thread dictionaries
            labels: Cluster labels
            embeddings: Thread embeddings
            
        Returns:
            Dictionary with cluster analysis
        """
        unique_labels = set(labels)
        cluster_info = {}
        
        for label in unique_labels:
            if label == -1:
                continue  # Skip noise
                
            # Get threads in this cluster
            cluster_mask = labels == label
            cluster_threads = [t for i, t in enumerate(threads) if cluster_mask[i]]
            cluster_embeddings = embeddings[cluster_mask]
            
            # Calculate centroid
            centroid = cluster_embeddings.mean(axis=0)
            
            # Find most representative thread (closest to centroid)
            similarities = cosine_similarity([centroid], cluster_embeddings)[0]
            most_representative_idx = similarities.argmax()
            representative_thread = cluster_threads[most_representative_idx]
            
            cluster_info[int(label)] = {
                'size': len(cluster_threads),
                'representative_title': representative_thread.get('title', ''),
                'thread_ids': [t.get('thread_id', '') for t in cluster_threads],
            }
            
        # Add noise info
        noise_count = sum(1 for l in labels if l == -1)
        cluster_info['noise'] = {
            'size': noise_count,
            'description': 'Threads that did not fit into any cluster',
        }
        
        return cluster_info
        
    def run_clustering_pipeline(
        self,
        output_dir: str,
        result_file: str = "clusters.json"
    ) -> Dict:
        """Run the complete clustering pipeline.
        
        Args:
            output_dir: Directory containing scraped threads
            result_file: Output file for cluster results
            
        Returns:
            Dictionary with clustering results
        """
        # Load threads
        print(f"Loading threads from {output_dir}...")
        threads = self.load_threads_from_output(output_dir)
        
        if not threads:
            print("No threads found.")
            return {}
            
        print(f"Loaded {len(threads)} threads")
        
        # Generate embeddings
        embeddings = self.generate_embeddings(threads)
        
        # Cluster
        labels, cluster_info = self.cluster_threads(threads, embeddings)
        
        # Add cluster labels to thread data
        for thread, label in zip(threads, labels):
            thread['cluster'] = int(label)
            
        # Prepare results
        results = {
            'num_threads': len(threads),
            'num_clusters': len([l for l in set(labels) if l != -1]),
            'cluster_info': cluster_info,
            'threads': [
                {
                    'thread_id': t.get('thread_id', ''),
                    'title': t.get('title', ''),
                    'cluster': t['cluster'],
                }
                for t in threads
            ],
        }
        
        # Save results
        result_path = Path(output_dir) / result_file
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"\nClustering results saved to {result_path}")
        print(f"Found {results['num_clusters']} clusters")
        print(f"Noise points: {cluster_info.get('noise', {}).get('size', 0)}")
        
        return results
