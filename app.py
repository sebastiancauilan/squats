from fastapi import FastAPI, File, UploadFile
import pickle
import numpy as np
import os
from PIL import Image
import io
import mediapipe as mp
import anthropic
import requests
from fastapi.responses import Response

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

PERSONALITY_PROMPTS = {
    "tsundere": "You are a tsundere anime girl personal trainer. You secretly care but act annoyed and reluctant. Short sentences only, max 15 words. Be specific about the form error or rep count.",
    "yandere": "You are a yandere anime girl personal trainer. Obsessively devoted, slightly intense, wants them to be perfect for you. Short sentences only, max 15 words.",
}

@app.post('/coach-voice')
async def coach_voice(data: dict):
    form = data.get('form', 'Correct')
    reps = data.get('reps', 0)
    streak = data.get('streak', 0)
    personality = data.get('personality', 'tsundere')
    voice_id = data.get('voice_id', 'vGQNBgLaiM3EdZtxIiuY')

    if form != 'Correct' and form:
        situation = f"The user just made a form error: {form}. React to this specific error."
    elif streak >= 2:
        situation = f"The user just completed {reps} reps with {streak} clean reps in a row. Give encouragement."
    else:
        situation = f"The user just completed rep {reps}. Give a short reaction."

    anthropic_client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    message = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS['tsundere']),
        messages=[{"role": "user", "content": situation}]
    )
    line = message.content[0].text.strip()

    xi_key = os.environ['ELEVENLABS_API_KEY']
    tts_response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": xi_key, "Content-Type": "application/json"},
        json={
            "text": line,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.6}
        }
    )

    return Response(content=tts_response.content, media_type="audio/mpeg")
