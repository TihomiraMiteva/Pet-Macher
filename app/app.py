"""
Flask API for Bulgarian Shelter Animals - Pet Matching System
"""
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Load data
df = pd.read_csv(Path(__file__).resolve().parent.parent / 'data/bulgarian_shelter_animals.csv')
df.columns = df.columns.str.strip().str.lower()

# Normalize yes/no-like columns
def norm_bool_col(s):
    mapping = {"y":"yes","yes":"yes","true":"yes","1":"yes",
               "n":"no","no":"no","false":"no","0":"no"}
    return s.astype(str).str.strip().str.lower().map(lambda v: mapping.get(v, v))

for c in ["good_with_kids","good_with_pets","sterilized","vaccinated"]:
    if c in df.columns:
        df[c] = norm_bool_col(df[c])

# Numeric age
if "age_years" in df.columns:
    df["age_years"] = pd.to_numeric(df["age_years"], errors="coerce")

# Static column weights (importance order)
WEIGHTS = {
    "species":        3.0,
    "breed":          3.0,
    "age_years":      2.5,
    "gender":         2.0,
    "temperament":    2.0,
    "size":           2.0,
    "activity_level": 2.0,
    "health_status":  1.0,
    "good_with_kids": 0.8,
    "good_with_pets": 0.8,
    "sterilized":     0.5,
    "vaccinated":     0.5,
}

TYPE_MAP = {
    "species": "cat",
    "breed": "cat",
    "age_years": "num",
    "gender": "cat",
    "temperament": "cat",
    "size": "cat",
    "activity_level": "cat",
    "health_status": "cat",
    "good_with_kids": "cat",
    "good_with_pets": "cat",
    "sterilized": "cat",
    "vaccinated": "cat",
}

def sim_cat(a, b):
    """Categorical similarity"""
    if pd.isna(a) or pd.isna(b): return 0.0
    return 1.0 if str(a).strip().lower() == str(b).strip().lower() else 0.0

def sim_num(a, b, tol=1.0, max_diff=10.0):
    """Numeric similarity with tolerance"""
    if b is None or pd.isna(b) or pd.isna(a): return 0.0
    try:
        a = float(a); b = float(b)
    except:
        return 0.0
    diff = abs(a - b)
    if diff <= tol: return 1.0
    if diff >= max_diff: return 0.0
    return 1.0 - (diff - tol) / (max_diff - tol)

def pet_match_top7_static(user_input, top_k=7):
    """
    Find top matching animals based on user preferences
    """
    keys = [k for k in WEIGHTS.keys() if k in df.columns and k in user_input]
    total_weight = sum(WEIGHTS[k] for k in keys if WEIGHTS[k] > 0)

    scores = np.zeros(len(df), dtype=float)
    for i, row in df.iterrows():
        s = 0.0
        for k in keys:
            w = WEIGHTS[k]
            if TYPE_MAP[k] == "num":
                s += w * sim_num(row.get(k, np.nan), user_input[k])
            else:
                s += w * sim_cat(row.get(k, np.nan), user_input[k])
        scores[i] = (s / total_weight) if total_weight > 0 else 0.0

    out = df.copy()
    out["match_%"] = (scores * 100).round(1)

    return_cols = [c for c in [
        "animal_id", "name", "species", "breed", "gender", "size", "color", "age_years",
        "temperament", "activity_level", "health_status", "good_with_kids", "good_with_pets",
        "sterilized", "vaccinated", "adoption_status", "arrival_date", "notes"
    ] if c in out.columns]

    result = (out.sort_values("match_%", ascending=False)
              [["match_%"] + return_cols]
              .head(top_k)
              .reset_index(drop=True))
    
    return result

@app.route('/')
def index():
    """Serve the HTML form"""
    return send_from_directory(str(Path(__file__).resolve().parent), 'animal_matching_form.html')

@app.route('/api/match', methods=['POST'])
def match_pets():
    """API endpoint to find matching pets"""
    try:
        user_input = request.json
        
        # Convert to expected format
        processed_input = {}
        for key, value in user_input.items():
            if key == 'age_years':
                processed_input[key] = float(value)
            elif key in ['good_with_kids', 'good_with_pets', 'sterilized', 'vaccinated']:
                processed_input[key] = value.lower()
            else:
                processed_input[key] = value
        
        # Get top matches
        matches = pet_match_top7_static(processed_input, top_k=7)
        
        # Convert to dict for JSON response
        result = matches.to_dict(orient='records')
        
        return jsonify({
            'success': True,
            'matches': result,
            'total_found': len(result)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        stats = {
            'total_animals': len(df),
            'available': len(df[df['adoption_status'].str.lower() == 'available']),
            'adopted': len(df[df['adoption_status'].str.lower() == 'adopted']),
            'reserved': len(df[df['adoption_status'].str.lower() == 'reserved']),
            'dogs': len(df[df['species'].str.lower() == 'dog']),
            'cats': len(df[df['species'].str.lower() == 'cat'])
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    print("🐾 Starting Bulgarian Shelter Animals Matching System...")
    print("📊 Database loaded:", len(df), "animals")
    print("🌐 Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    app.run(host='127.0.0.1', debug=False, port=5000)
