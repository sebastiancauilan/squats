from fastapi import FastAPI
from pydantic import BaseModel
import pickle
import numpy as np

app = FastAPI()

# Load models
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