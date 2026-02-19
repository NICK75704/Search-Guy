# app.py
from flask import Flask, render_template, request, jsonify
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

app = Flask(__name__)

# Global variable to store the vector database
vector_database = None
model = None

def load_vector_database(file_path='vectors.pkl'):
    """Load the vector database from pickle file."""
    global vector_database, model
    
    if not os.path.exists(file_path):
        print(f"Error: Vector database file '{file_path}' not found.")
        return False
    
    try:
        with open(file_path, 'rb') as f:
            vector_database = pickle.load(f)
        model = vector_database['model']
        print(f"Loaded vector database with {len(vector_database['embeddings'])} embeddings")
        return True
    except Exception as e:
        print(f"Error loading vector database: {e}")
        return False

def search_vectors(query, top_k=10):
    """Search for similar vectors to the query."""
    if vector_database is None:
        return []
    
    # Create embedding for the query
    query_embedding = model.encode([query])
    
    # Get all embeddings
    embeddings = vector_database['embeddings']
    
    if len(embeddings) == 0:
        return []
    
    # Calculate cosine similarities
    similarities = cosine_similarity(query_embedding, embeddings)[0]
    
    # Get top k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    # Get top k results with scores
    results = []
    for idx in top_indices:
        if similarities[idx] > 0:  # Only include results with some similarity
            results.append({
                'score': float(similarities[idx]),
                'metadata': vector_database['message_metadata'][idx],
                'content': vector_database['message_metadata'][idx]['original_message']['content']
            })
    
    return results

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Handle search requests."""
    data = request.get_json()
    query = data.get('query', '')
    top_k = int(data.get('top_k', 10))
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    results = search_vectors(query, top_k)
    
    # Format results for JSON response
    formatted_results = []
    for result in results:
        formatted_results.append({
            'score': result['score'],
            'content': result['content'],
            'username': result['metadata']['username'],
            'timestamp': result['metadata']['timestamp'],
            'source_file': result['metadata']['source_file'],
            'line_number': result['metadata']['line_number']
        })
    
    return jsonify({'results': formatted_results})

if __name__ == '__main__':
    # Load the vector database when the app starts
    if load_vector_database('vectors.pkl'):
        print("Vector database loaded successfully")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Failed to load vector database. Please ensure vectors.pkl exists.")