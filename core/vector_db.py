"""
VectorDB - Custom Vector Database Implementation
A laboratory for experimenting with different distance calculation methods
"""

import numpy as np
import pickle
import json
from typing import List, Tuple, Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import threading
from enum import Enum


class DistanceMetric(Enum):
    """Available distance calculation methods"""
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"
    MINKOWSKI = "minkowski"
    HAMMING = "hamming"
    CANBERRA = "canberra"
    BRAYCURTIS = "braycurtis"
    # Custom experimental metrics
    CUSTOM_WEIGHTED = "custom_weighted"
    CUSTOM_ADAPTIVE = "custom_adaptive"


@dataclass
class VectorEntry:
    """Represents a single vector entry in the database"""
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self):
        return {
            'id': self.id,
            'vector': self.vector.tolist(),
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class DistanceCalculator:
    """Collection of distance calculation methods"""
    
    @staticmethod
    def euclidean(v1: np.ndarray, v2: np.ndarray) -> float:
        """Standard Euclidean distance: sqrt(sum((v1-v2)^2))"""
        return np.sqrt(np.sum((v1 - v2) ** 2))
    
    @staticmethod
    def cosine(v1: np.ndarray, v2: np.ndarray) -> float:
        """Cosine distance: 1 - (v1·v2)/(|v1||v2|)"""
        dot_product = np.dot(v1, v2)
        norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm_product == 0:
            return 1.0
        return 1.0 - (dot_product / norm_product)
    
    @staticmethod
    def manhattan(v1: np.ndarray, v2: np.ndarray) -> float:
        """Manhattan distance: sum(|v1-v2|)"""
        return np.sum(np.abs(v1 - v2))
    
    @staticmethod
    def chebyshev(v1: np.ndarray, v2: np.ndarray) -> float:
        """Chebyshev distance: max(|v1-v2|)"""
        return np.max(np.abs(v1 - v2))
    
    @staticmethod
    def minkowski(v1: np.ndarray, v2: np.ndarray, p: float = 3) -> float:
        """Minkowski distance: (sum(|v1-v2|^p))^(1/p)"""
        return np.power(np.sum(np.power(np.abs(v1 - v2), p)), 1/p)
    
    @staticmethod
    def hamming(v1: np.ndarray, v2: np.ndarray) -> float:
        """Hamming distance: proportion of differing elements"""
        return np.mean(v1 != v2)
    
    @staticmethod
    def canberra(v1: np.ndarray, v2: np.ndarray) -> float:
        """Canberra distance: sum(|v1-v2|/(|v1|+|v2|))"""
        numerator = np.abs(v1 - v2)
        denominator = np.abs(v1) + np.abs(v2)
        # Avoid division by zero
        mask = denominator != 0
        result = np.sum(numerator[mask] / denominator[mask])
        return result
    
    @staticmethod
    def braycurtis(v1: np.ndarray, v2: np.ndarray) -> float:
        """Bray-Curtis distance: sum(|v1-v2|)/sum(|v1+v2|)"""
        numerator = np.sum(np.abs(v1 - v2))
        denominator = np.sum(np.abs(v1 + v2))
        if denominator == 0:
            return 0.0
        return numerator / denominator
    
    @staticmethod
    def custom_weighted(v1: np.ndarray, v2: np.ndarray, weights: Optional[np.ndarray] = None) -> float:
        """
        Custom weighted Euclidean distance
        Allows emphasizing certain dimensions
        """
        if weights is None:
            weights = np.ones_like(v1)
        return np.sqrt(np.sum(weights * (v1 - v2) ** 2))
    
    @staticmethod
    def custom_adaptive(v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Custom adaptive distance - experimental
        Combines multiple metrics with adaptive weighting
        """
        euclidean = DistanceCalculator.euclidean(v1, v2)
        cosine = DistanceCalculator.cosine(v1, v2)
        manhattan = DistanceCalculator.manhattan(v1, v2)
        
        # Adaptive weighting based on vector magnitudes
        mag1, mag2 = np.linalg.norm(v1), np.linalg.norm(v2)
        mag_ratio = min(mag1, mag2) / max(mag1, mag2) if max(mag1, mag2) > 0 else 1.0
        
        # Blend metrics
        return 0.4 * euclidean + 0.3 * cosine + 0.2 * manhattan + 0.1 * (1 - mag_ratio)


class VectorDB:
    """
    Custom Vector Database implementation
    Laboratory for experimenting with distance metrics
    """
    
    def __init__(self, dimension: int, metric: DistanceMetric = DistanceMetric.EUCLIDEAN):
        """
        Initialize the vector database
        
        Args:
            dimension: Dimensionality of vectors
            metric: Default distance metric to use
        """
        self.dimension = dimension
        self.metric = metric
        self.vectors: List[VectorEntry] = []
        self.index_map: Dict[str, int] = {}  # id -> index mapping
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'total_vectors': 0,
            'total_queries': 0,
            'avg_query_time': 0.0,
            'metric_usage': {m.value: 0 for m in DistanceMetric}
        }
    
    def add_vector(self, vector_id: str, vector: np.ndarray, metadata: Optional[Dict] = None) -> bool:
        """
        Add a vector to the database
        
        Args:
            vector_id: Unique identifier for the vector
            vector: The vector data (must match dimension)
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False if vector already exists or dimension mismatch
        """
        if len(vector) != self.dimension:
            raise ValueError(f"Vector dimension {len(vector)} doesn't match DB dimension {self.dimension}")
        
        with self.lock:
            if vector_id in self.index_map:
                return False  # Vector already exists
            
            entry = VectorEntry(
                id=vector_id,
                vector=np.array(vector, dtype=np.float32),
                metadata=metadata or {},
                timestamp=datetime.now()
            )
            
            self.vectors.append(entry)
            self.index_map[vector_id] = len(self.vectors) - 1
            self.stats['total_vectors'] += 1
            
            return True
    
    def add_batch(self, vectors: List[Tuple[str, np.ndarray, Optional[Dict]]]) -> int:
        """
        Add multiple vectors at once
        
        Returns:
            Number of vectors successfully added
        """
        count = 0
        for vector_id, vector, metadata in vectors:
            if self.add_vector(vector_id, vector, metadata):
                count += 1
        return count
    
    def get_vector(self, vector_id: str) -> Optional[VectorEntry]:
        """Retrieve a vector by ID"""
        with self.lock:
            idx = self.index_map.get(vector_id)
            if idx is not None:
                return self.vectors[idx]
            return None
    
    def delete_vector(self, vector_id: str) -> bool:
        """Delete a vector by ID"""
        with self.lock:
            idx = self.index_map.get(vector_id)
            if idx is None:
                return False
            
            # Remove from list and rebuild index
            del self.vectors[idx]
            self.index_map = {v.id: i for i, v in enumerate(self.vectors)}
            self.stats['total_vectors'] -= 1
            
            return True
    
    def _calculate_distance(self, v1: np.ndarray, v2: np.ndarray, 
                          metric: Optional[DistanceMetric] = None,
                          **kwargs) -> float:
        """Internal method to calculate distance between two vectors"""
        metric = metric or self.metric
        calculator = DistanceCalculator()
        
        method_map = {
            DistanceMetric.EUCLIDEAN: calculator.euclidean,
            DistanceMetric.COSINE: calculator.cosine,
            DistanceMetric.MANHATTAN: calculator.manhattan,
            DistanceMetric.CHEBYSHEV: calculator.chebyshev,
            DistanceMetric.MINKOWSKI: calculator.minkowski,
            DistanceMetric.HAMMING: calculator.hamming,
            DistanceMetric.CANBERRA: calculator.canberra,
            DistanceMetric.BRAYCURTIS: calculator.braycurtis,
            DistanceMetric.CUSTOM_WEIGHTED: calculator.custom_weighted,
            DistanceMetric.CUSTOM_ADAPTIVE: calculator.custom_adaptive,
        }
        
        self.stats['metric_usage'][metric.value] += 1
        return method_map[metric](v1, v2, **kwargs)
    
    def query(self, query_vector: np.ndarray, k: int = 5, 
              metric: Optional[DistanceMetric] = None,
              filter_fn: Optional[Callable[[VectorEntry], bool]] = None,
              **metric_kwargs) -> List[Tuple[VectorEntry, float]]:
        """
        Query the database for k nearest neighbors
        
        Args:
            query_vector: The query vector
            k: Number of nearest neighbors to return
            metric: Distance metric to use (uses default if None)
            filter_fn: Optional function to filter results
            **metric_kwargs: Additional arguments for distance metric
            
        Returns:
            List of (VectorEntry, distance) tuples, sorted by distance
        """
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension {len(query_vector)} doesn't match DB dimension {self.dimension}")
        
        query_vector = np.array(query_vector, dtype=np.float32)
        
        with self.lock:
            # Calculate distances
            distances = []
            for entry in self.vectors:
                if filter_fn is None or filter_fn(entry):
                    dist = self._calculate_distance(query_vector, entry.vector, metric, **metric_kwargs)
                    distances.append((entry, dist))
            
            # Sort by distance and return top k
            distances.sort(key=lambda x: x[1])
            self.stats['total_queries'] += 1
            
            return distances[:k]
    
    def get_all_vectors(self) -> List[VectorEntry]:
        """Get all vectors in the database"""
        with self.lock:
            return self.vectors.copy()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        return self.stats.copy()
    
    def save(self, filepath: str):
        """Save the database to disk"""
        with self.lock:
            data = {
                'dimension': self.dimension,
                'metric': self.metric.value,
                'vectors': [v.to_dict() for v in self.vectors],
                'stats': self.stats
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
    
    @classmethod
    def load(cls, filepath: str) -> 'VectorDB':
        """Load a database from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        db = cls(data['dimension'], DistanceMetric(data['metric']))
        
        for v_dict in data['vectors']:
            db.add_vector(
                v_dict['id'],
                np.array(v_dict['vector']),
                v_dict['metadata']
            )
        
        db.stats = data['stats']
        return db
    
    def __len__(self) -> int:
        """Return number of vectors in database"""
        return len(self.vectors)
    
    def __repr__(self) -> str:
        return f"VectorDB(dimension={self.dimension}, vectors={len(self.vectors)}, metric={self.metric.value})"
