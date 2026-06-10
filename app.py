from fastapi import FastAPI
from pydantic import BaseModel
import pickle
import numpy as np
import os

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

form_labels = {
    0: 'Correct',
    1: 'Shallow squat',
    2: 'Forward lean',
    3: 'Knees caving in',
    4: 'Heels off ground',
    5: 'Asymmetric squat'
}

class KeypointsInput(BaseModel):
    keypoints: list[float]
    form_features: list[float]

@app.post('/predict')
def predict(data: KeypointsInput):
    kp = np.array(data.keypoints).reshape(1, -1)
    phase = phase_model.predict(kp)[0]

    form = None
    if phase == 'bottom':
        ff = np.array(data.form_features).reshape(1, -1)
        proba = form_model.predict_proba(ff)[0]
        if proba.max() >= 0.80:
            form = form_labels[proba.argmax()]
        else:
            form = 'Correct'

    return {'phase': phase, 'form': form}