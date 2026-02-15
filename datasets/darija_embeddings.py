"""
Darija (Moroccan Arabic) Word Embeddings Generator
Creates semantic vector representations of common Darija words
"""

import numpy as np
from typing import List, Dict, Tuple
import json


class DarijaWordEmbeddings:
    """Generate and manage Darija word embeddings"""
    
    def __init__(self, dimension: int = 128):
        """
        Initialize Darija word embeddings
        
        Args:
            dimension: Embedding dimension (default 128 for good visualization)
        """
        self.dimension = dimension
        self.word_to_vector = {}
        self.word_metadata = {}
        
        # Seed for reproducibility
        np.random.seed(42)
        
    def create_darija_dataset(self) -> Dict[str, np.ndarray]:
        """Create a comprehensive Darija vocabulary with semantic embeddings"""
        
        # Define semantic categories with Darija words
        darija_categories = {
            # Family / العائلة
            "family": {
                "words": ["baba", "mama", "khouya", "khouti", "3ammi", "3ammti", 
                         "jedd", "jedda", "weld", "bent", "rajel", "mra"],
                "translations": ["father", "mother", "brother", "sister", "uncle", "aunt",
                               "grandfather", "grandmother", "son", "daughter", "man", "woman"],
                "base_vector": self._create_base_vector([0.8, 0.7, 0.6])
            },
            
            # Food / الماكلة
            "food": {
                "words": ["khobz", "l7lib", "lma", "atay", "tagine", "couscous",
                         "tfaya", "pastilla", "harira", "briouate", "msemen", "baghrir"],
                "translations": ["bread", "milk", "water", "tea", "tagine", "couscous",
                               "tfaya", "pastilla", "harira", "briouate", "msemen", "baghrir"],
                "base_vector": self._create_base_vector([0.6, 0.8, 0.3])
            },
            
            # Greetings / السلامات
            "greetings": {
                "words": ["salam", "labas", "bikhir", "shokran", "afak", "bslama",
                         "sbah_lkhir", "msa_lkhir", "layawdi", "bsahtek", "mabruk"],
                "translations": ["hello", "how are you", "fine", "thank you", "please", "goodbye",
                               "good morning", "good evening", "bon appetit", "bless you", "congratulations"],
                "base_vector": self._create_base_vector([0.9, 0.5, 0.8])
            },
            
            # Numbers / الأرقام
            "numbers": {
                "words": ["wahed", "jouj", "tlata", "rb3a", "khamsa", "setta",
                         "seb3a", "tmenya", "tes3od", "3ashra"],
                "translations": ["one", "two", "three", "four", "five", "six",
                               "seven", "eight", "nine", "ten"],
                "base_vector": self._create_base_vector([0.3, 0.9, 0.7])
            },
            
            # Colors / الألوان
            "colors": {
                "words": ["7mer", "khal", "sfar", "zreg", "byad", "khel",
                         "romani", "zher", "bni", "lemrani"],
                "translations": ["red", "black", "yellow", "blue", "white", "green",
                               "orange", "pink", "brown", "orange"],
                "base_vector": self._create_base_vector([0.7, 0.4, 0.9])
            },
            
            # Time / الوقت
            "time": {
                "words": ["lyoum", "gheda", "lbar7", "sbah", "3shiya", "lil",
                         "sa3a", "dqiqa", "jom3a", "simana", "shahar", "3am"],
                "translations": ["today", "tomorrow", "yesterday", "morning", "evening", "night",
                               "hour", "minute", "week", "week", "month", "year"],
                "base_vector": self._create_base_vector([0.5, 0.6, 0.8])
            },
            
            # Places / الأماكن
            "places": {
                "words": ["dar", "souk", "mdina", "shari3", "jami3", "mdrasa",
                         "sbitar", "7anut", "mqha", "7amma", "fran", "l7ayat"],
                "translations": ["house", "market", "city", "street", "mosque", "school",
                               "hospital", "shop", "cafe", "hammam", "bakery", "neighborhood"],
                "base_vector": self._create_base_vector([0.4, 0.7, 0.5])
            },
            
            # Actions / الأفعال
            "actions": {
                "words": ["msha", "ja", "kla", "shreb", "n3es", "faq",
                         "khdm", "9ra", "kteb", "sm3", "shaf", "hdar"],
                "translations": ["went", "came", "ate", "drank", "slept", "woke up",
                               "worked", "read/studied", "wrote", "heard", "saw", "spoke"],
                "base_vector": self._create_base_vector([0.6, 0.5, 0.9])
            },
            
            # Emotions / المشاعر
            "emotions": {
                "words": ["fer7an", "mskhin", "mkhalle3", "zhar",
                         "m9elle9", "merte7", "3yyan", "mskhot"],
                "translations": ["happy", "sad", "scared", "angry",
                               "worried", "comfortable", "tired", "upset"],
                "base_vector": self._create_base_vector([0.8, 0.3, 0.7])
            },
            
            # Weather / الطقس
            "weather": {
                "words": ["shta", "shems", "sejn", "berd", "ri7", "ghim",
                         "talj", "ber9", "skhoun", "r9i9"],
                "translations": ["rain", "sun", "hot", "cold", "wind", "clouds",
                               "snow", "lightning", "warm", "thin/light"],
                "base_vector": self._create_base_vector([0.5, 0.8, 0.4])
            },
            
            # Body Parts / أعضاء الجسم
            "body": {
                "words": ["ras", "3in", "fom", "yd", "rjel", "9elb",
                         "odn", "nif", "snan", "zhar", "karch", "3nek"],
                "translations": ["head", "eye", "mouth", "hand", "leg", "heart",
                               "ear", "nose", "teeth", "back", "belly", "neck"],
                "base_vector": self._create_base_vector([0.7, 0.6, 0.6])
            },
            
            # Transportation / النقل
            "transport": {
                "words": ["tomobil", "tran", "tobis", "darja", "7mar",
                         "taxi", "bateau", "tayara", "7obala"],
                "translations": ["car", "train", "bus", "bicycle", "donkey",
                               "taxi", "boat", "airplane", "cart"],
                "base_vector": self._create_base_vector([0.6, 0.7, 0.8])
            }
        }
        
        # Generate embeddings for each category
        for category, data in darija_categories.items():
            base = data["base_vector"]
            words = data["words"]
            translations = data["translations"]
            
            for i, (word, translation) in enumerate(zip(words, translations)):
                # Create semantic vector with slight variations within category
                variation = np.random.randn(self.dimension) * 0.15
                vector = base + variation
                
                # Normalize
                vector = vector / np.linalg.norm(vector)
                
                # Store
                self.word_to_vector[word] = vector
                self.word_metadata[word] = {
                    "category": category,
                    "translation": translation,
                    "arabic_category": self._get_arabic_category(category)
                }
        
        return self.word_to_vector
    
    def _create_base_vector(self, seed_values: List[float]) -> np.ndarray:
        """Create a base semantic vector from seed values"""
        vector = np.random.randn(self.dimension)
        
        # Inject semantic seed in first few dimensions
        for i, val in enumerate(seed_values):
            if i < self.dimension:
                vector[i] = val
        
        return vector
    
    def _get_arabic_category(self, category: str) -> str:
        """Get Arabic name for category"""
        arabic_names = {
            "family": "العائلة",
            "food": "الماكلة",
            "greetings": "السلامات",
            "numbers": "الأرقام",
            "colors": "الألوان",
            "time": "الوقت",
            "places": "الأماكن",
            "actions": "الأفعال",
            "emotions": "المشاعر",
            "weather": "الطقس",
            "body": "أعضاء الجسم",
            "transport": "النقل"
        }
        return arabic_names.get(category, category)
    
    def get_category_colors(self) -> Dict[str, Tuple[float, float, float]]:
        """Get distinct colors for each category"""
        colors = {
            "family": (0.9, 0.3, 0.3),      # Red
            "food": (0.3, 0.8, 0.3),        # Green
            "greetings": (0.3, 0.3, 0.9),   # Blue
            "numbers": (0.9, 0.7, 0.2),     # Gold
            "colors": (0.8, 0.3, 0.8),      # Purple
            "time": (0.3, 0.9, 0.9),        # Cyan
            "places": (0.9, 0.5, 0.2),      # Orange
            "actions": (0.5, 0.9, 0.5),     # Light Green
            "emotions": (0.9, 0.4, 0.6),    # Pink
            "weather": (0.4, 0.6, 0.9),     # Sky Blue
            "body": (0.8, 0.6, 0.4),        # Tan
            "transport": (0.5, 0.5, 0.5),   # Gray
        }
        return colors
    
    def export_for_vectordb(self, dimension_3d: int = 3) -> List[Tuple[str, np.ndarray, Dict]]:
        """
        Export data in format ready for VectorDB
        Reduces dimension to 3D for visualization
        
        Returns:
            List of (word_id, vector_3d, metadata) tuples
        """
        from sklearn.decomposition import PCA
        
        if not self.word_to_vector:
            self.create_darija_dataset()
        
        # Get all vectors
        words = list(self.word_to_vector.keys())
        vectors_high_dim = np.array([self.word_to_vector[w] for w in words])
        
        # Reduce to 3D using PCA
        pca = PCA(n_components=dimension_3d)
        vectors_3d = pca.fit_transform(vectors_high_dim)
        
        # Scale to nice range for visualization [-5, 5]
        vectors_3d = vectors_3d * 3
        
        # Prepare export data
        category_colors = self.get_category_colors()
        export_data = []
        
        for word, vec_3d in zip(words, vectors_3d):
            metadata = self.word_metadata[word].copy()
            category = metadata['category']
            metadata['color'] = category_colors.get(category, (0.5, 0.5, 0.5))
            metadata['darija'] = word
            
            export_data.append((word, vec_3d, metadata))
        
        return export_data
    
    def save_dataset(self, filepath: str = "darija_embeddings.json"):
        """Save dataset to JSON file"""
        if not self.word_to_vector:
            self.create_darija_dataset()
        
        data = {
            "dimension": self.dimension,
            "vocabulary_size": len(self.word_to_vector),
            "words": {}
        }
        
        for word, vector in self.word_to_vector.items():
            data["words"][word] = {
                "vector": vector.tolist(),
                "metadata": self.word_metadata[word]
            }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved {len(self.word_to_vector)} Darija words to {filepath}")
    
    def print_vocabulary(self):
        """Print the complete Darija vocabulary"""
        if not self.word_to_vector:
            self.create_darija_dataset()
        
        print("\n" + "="*70)
        print("  DARIJA WORD EMBEDDINGS VOCABULARY")
        print("="*70)
        
        # Group by category
        by_category = {}
        for word, meta in self.word_metadata.items():
            cat = meta['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((word, meta['translation'], meta['arabic_category']))
        
        for category, words in sorted(by_category.items()):
            arabic_cat = words[0][2]
            print(f"\n📚 {category.upper()} / {arabic_cat}")
            print("-" * 70)
            for word, translation, _ in words:
                print(f"  {word:20s} → {translation}")
        
        print("\n" + "="*70)
        print(f"Total: {len(self.word_to_vector)} words across {len(by_category)} categories")
        print("="*70)


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("  Darija (Moroccan Arabic) Word Embeddings Generator")
    print("=" * 70)
    
    # Create embeddings
    darija = DarijaWordEmbeddings(dimension=128)
    darija.create_darija_dataset()
    
    # Print vocabulary
    darija.print_vocabulary()
    
    # Save to file
    darija.save_dataset()
    
    print("\n✅ Darija embeddings created successfully!")
    print("\nNext steps:")
    print("  1. Run: python load_darija_to_vectordb.py")
    print("  2. Or use in visualizer directly")
