"""
Load Darija Words into VectorDB Visualizer
Visualize semantic relationships in Moroccan Arabic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from core.vector_db import VectorDB, DistanceMetric
from datasets.darija_embeddings import DarijaWordEmbeddings


def load_darija_to_vectordb():
    """Load Darija dataset into VectorDB"""
    print("=" * 70)
    print("  Loading Darija Words into VectorDB")
    print("=" * 70)
    
    # Create Darija embeddings
    print("\n📚 Creating Darija word embeddings...")
    darija = DarijaWordEmbeddings(dimension=128)
    darija.create_darija_dataset()
    
    # Export to 3D for visualization
    print("📊 Reducing to 3D for visualization...")
    export_data = darija.export_for_vectordb(dimension_3d=3)
    
    # Create VectorDB
    print("🗄️  Creating VectorDB...")
    db = VectorDB(dimension=3, metric=DistanceMetric.COSINE)
    
    # Add all words
    print(f"📥 Adding {len(export_data)} Darija words...")
    for word, vector, metadata in export_data:
        db.add_vector(word, vector, metadata)
    
    print(f"\n✅ Loaded {len(db)} Darija words successfully!")
    
    # Test some queries
    print("\n" + "="*70)
    print("  Testing Semantic Queries")
    print("="*70)
    
    test_words = ["baba", "khobz", "salam", "wahed", "7mer"]
    
    for word in test_words:
        if word in [w for w, _, _ in export_data]:
            vector = db.get_vector(word).vector
            results = db.query(vector, k=5)
            
            print(f"\n🔍 Words similar to '{word}':")
            for i, (entry, distance) in enumerate(results, 1):
                meta = entry.metadata
                translation = meta.get('translation', 'N/A')
                category = meta.get('category', 'N/A')
                similarity = 1 - distance  # Convert distance to similarity
                print(f"  {i}. {entry.id:15s} ({translation:15s}) - "
                      f"similarity: {similarity:.3f} - {category}")
    
    # Save database
    print("\n💾 Saving database...")
    db.save("darija_vectordb.pkl")
    print("✅ Saved to darija_vectordb.pkl")
    
    return db, export_data


def demo_darija_queries():
    """Interactive demo of Darija word queries"""
    db, export_data = load_darija_to_vectordb()
    
    print("\n" + "="*70)
    print("  Interactive Darija Word Explorer")
    print("="*70)
    
    word_list = [w for w, _, _ in export_data]
    
    print("\n📖 Available Darija words:")
    print("(Showing first 30)")
    for i, word in enumerate(word_list[:30], 1):
        if i % 6 == 0:
            print(word)
        else:
            print(word.ljust(12), end=" ")
    print("\n")
    
    while True:
        print("\n" + "-"*70)
        word = input("Enter a Darija word to find similar (or 'quit'): ").strip()
        
        if word.lower() == 'quit':
            break
        
        if word not in word_list:
            print(f"❌ '{word}' not in vocabulary. Try another word.")
            continue
        
        # Get metadata
        entry = db.get_vector(word)
        meta = entry.metadata
        
        print(f"\n🎯 WORD: {word}")
        print(f"   Translation: {meta.get('translation', 'N/A')}")
        print(f"   Category: {meta.get('category', 'N/A')} / {meta.get('arabic_category', 'N/A')}")
        print(f"   Position: ({entry.vector[0]:.2f}, {entry.vector[1]:.2f}, {entry.vector[2]:.2f})")
        
        # Find similar
        results = db.query(entry.vector, k=8)
        
        print(f"\n🔗 Most similar words:")
        for i, (similar_entry, distance) in enumerate(results, 1):
            similar_meta = similar_entry.metadata
            similarity = 1 - distance
            print(f"   {i}. {similar_entry.id:15s} → {similar_meta.get('translation', 'N/A'):15s} "
                  f"(similarity: {similarity:.3f}) [{similar_meta.get('category', 'N/A')}]")


if __name__ == "__main__":
    import sys
    
    # Check if sklearn is available
    try:
        import sklearn
    except ImportError:
        print("❌ sklearn not installed. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn"])
        print("✅ sklearn installed!")
    
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "Darija VectorDB Visualization" + " "*24 + "║")
    print("╚" + "="*68 + "╝")
    
    choice = input("\n1. Load data only\n2. Interactive explorer\n\nChoice (1 or 2): ").strip()
    
    if choice == "2":
        demo_darija_queries()
    else:
        load_darija_to_vectordb()
    
    print("\n" + "="*70)
    print("  Next: Launch visualizer to see 3D word relationships!")
    print("  Run: python gui/visualizer_app.py")
    print("  Then: Load the darija_vectordb.pkl file")
    print("="*70)
