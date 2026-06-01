from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import io
import traceback

app = Flask(__name__)
# Configured for standard development ports [3, 4]
CORS(app, origins=["http://localhost:8001", "http://127.0.0.1:5500", "http://localhost:5500", "*"])

@app.route('/embed', methods=['POST'])
def get_mood_embedding():
    try:
        file = request.files['file']
        # Load first 30s of audio [3]
        try:
            y, sr = librosa.load(io.BytesIO(file.read()), duration=30)
        except Exception:
            return jsonify({"error": "Unsupported audio format"}), 400

        # Feature Extraction: Intensity, Texture, and Brightness
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        float_tempo = float(np.mean(tempo))
        energy = float(np.mean(librosa.feature.rms(y=y)))
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        mfccs = np.mean(librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12), axis=1).tolist()

        # Build 16-parameter vector
        vector = [float_tempo/200, energy*5, flatness*10, centroid/5000] + mfccs

        # Heuristics for the 7 system categories [5, 6]
        if float_tempo > 130 and energy > 0.07: mood = "party"
        elif energy > 0.08: mood = "angry"
        elif float_tempo > 115 and energy > 0.05: mood = "happy"
        elif energy < 0.015: mood = "soothing"
        elif energy < 0.025: mood = "sad"
        elif float_tempo < 100: mood = "chill"
        else: mood = "romantic"

        return jsonify({"vector": vector, "mood": mood, "tempo": round(float_tempo, 1)})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
