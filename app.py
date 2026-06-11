from fastapi import FastAPI, File, UploadFile
import pickle
import numpy as np
import os
from PIL import Image
import io
import mediapipe as mp

app = FastAPI()

# Train form model if missing
if not os.path.exists('form_model.pkl'):
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    features = [
        'left_knee_angle','right_knee_angle','left_hip_angle','right_hip_angle',
        'left_ankle_angle','right_ankle_angle','spine_angle','torso_lean',
        'left_knee_lateral','right_knee_lateral','symmetry_score','hip_depth'
    ]
    dataset = pd.read_csv('squat_features_augmented.csv')
    X = dataset[features]
    y = dataset['label']
    form_model = RandomForestClassifier(n_estimators=100, random_state=42)
    form_model.fit(X, y)
    with open('form_model.pkl', 'wb') as f:
        pickle.dump(form_model, f)

with open('model.pkl', 'rb') as f:
    phase_model = pickle.load(f)

with open('form_model.pkl', 'rb') as f:
    form_model = pickle.load(f)

mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

form_labels = {
    0: 'Correct',
    1: 'Shallow squat',
    2: 'Forward lean',
    3: 'Knees caving in',
    4: 'Heels off ground',
    5: 'Asymmetric squat'
}

def angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

@app.post('/predict')
async def predict(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert('RGB')
    rgb = np.array(image)
    results = pose.process(rgb)

    if not results.pose_landmarks:
        return {'phase': 'unknown', 'form': None, 'reps': None}

    landmarks = results.pose_landmarks.landmark

    kp = []
    for lm in landmarks:
        kp.extend([lm.x, lm.y, lm.z])

    def lm_coords(idx):
        return [landmarks[idx].x, landmarks[idx].y]

    left_knee   = angle(lm_coords(23), lm_coords(25), lm_coords(27))
    right_knee  = angle(lm_coords(24), lm_coords(26), lm_coords(28))
    left_hip    = angle(lm_coords(11), lm_coords(23), lm_coords(25))
    right_hip   = angle(lm_coords(12), lm_coords(24), lm_coords(26))
    left_ankle  = angle(lm_coords(25), lm_coords(27), lm_coords(31))
    right_ankle = angle(lm_coords(26), lm_coords(28), lm_coords(32))
    spine       = angle(lm_coords(11), lm_coords(23), lm_coords(25))
    torso_lean  = angle(lm_coords(11), lm_coords(23), lm_coords(27))
    left_knee_lat  = landmarks[25].x - landmarks[23].x
    right_knee_lat = landmarks[26].x - landmarks[24].x
    symmetry    = abs(left_knee - right_knee)
    hip_depth   = landmarks[23].y

    phase = phase_model.predict([kp])[0]

    form = None
    if phase == 'bottom':
        ff = [[left_knee, right_knee, left_hip, right_hip,
               left_ankle, right_ankle, spine, torso_lean,
               left_knee_lat, right_knee_lat, symmetry, hip_depth]]
        proba = form_model.predict_proba(ff)[0]
        if proba.max() >= 0.80:
            form = form_labels[proba.argmax()]
        else:
            form = 'Correct'

    return {'phase': phase, 'form': form}