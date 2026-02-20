from flask import Flask, render_template, request, jsonify
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
import json
from datetime import datetime

app = Flask(__name__)

# Global variable to store the vector database
vector_database = None

def load_vector_database(file_path='vectors.pkl'):
    """
    Load the vector database from pickle file.
    
    Args:
        file_path (str): Path to the pickle file containing vectors
    
    Returns:
        dict: Vector database with embeddings, metadata, and model
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Vector database file '{file_path}' not found.")
    
    with open(file_path, 'rb') as f:
        vector_database = pickle.load(f)
    
    return vector_database

def search_vectors(query, vector_database, top_k=10):
    """
    Search for similar vectors to the query.
    
    Args:
        query (str): Search query
        vector_database (dict): Loaded vector database
        top_k (int): Number of top results to return
    
    Returns:
        list: Top k similar messages with scores
    """
    # Load the model used for vectorization
    model = vector_database['model']
    
    # Create embedding for the query
    query_embedding = model.encode([query])
    
    # Get all embeddings
    embeddings = vector_database['embeddings']
    
    if len(embeddings) == 0:
        raise ValueError("No embeddings found in database")
    
    # Calculate cosine similarities
    similarities = cosine_similarity(query_embedding, embeddings)[0]
    
    # Get top k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    # Get top k results with scores
    results = []
    for idx in top_indices:
        if similarities[idx] > 0:  # Only include results with some similarity
            results.append({
                'score': similarities[idx],
                'metadata': vector_database['message_metadata'][idx],
                'content': vector_database['message_metadata'][idx]['original_message']['content']
            })
    
    return results

def get_surrounding_context(source_file, line_number, context_lines=5):
    """
    Get surrounding lines from a source file.
    
    Args:
        source_file (str): Path to the source file
        line_number (int): Line number to get context for
        context_lines (int): Number of lines before and after
    
    Returns:
        str: Formatted context text
    """
    if not os.path.exists(source_file):
        return f"Error: Source file '{source_file}' not found."
    
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Calculate start and end line numbers
        start_line = max(0, line_number - context_lines - 1)
        end_line = min(len(lines), line_number + context_lines)
        
        # Build context text
        context_text = f"Surrounding context for line {line_number} in {source_file}:\n"
        context_text += "-" * 80 + "\n"
        
        # Print context lines
        for i in range(start_line, end_line):
            line_num = i + 1
            marker = ">>> " if line_num == line_number else "   "
            context_text += f"{line_num:4d}: {marker}{lines[i].rstrip()}\n"
            
        return context_text
        
    except Exception as e:
        return f"Error reading file: {e}"

# Load database at startup
try:
    vector_database = load_vector_database('vectors.pkl')
    print("Vector database loaded successfully")
except Exception as e:
    print(f"Failed to load vector database: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    if not vector_database:
        return jsonify({'error': 'Vector database not loaded'}), 500
    
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        results = search_vectors(query, vector_database, top_k=10)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/context', methods=['POST'])
def context():
    if not vector_database:
        return jsonify({'error': 'Vector database not loaded'}), 500
    
    data = request.get_json()
    source_file = data.get('source_file', '')
    line_number = data.get('line_number', 0)
    
    if not source_file or line_number == 0:
        return jsonify({'error': 'Source file and line number are required'}), 400
    
    context_text = get_surrounding_context(source_file, line_number)
    return jsonify({'context': context_text})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)