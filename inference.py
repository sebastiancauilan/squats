import cv2
import mediapipe as mp
import pickle
import numpy as np

rep_count = 0
phase_sequence = []
# Load both models
with open(r'C:\Users\Sebastian\squats\model.pkl', 'rb') as f:
    phase_model = pickle.load(f)

with open(r'C:\Users\Sebastian\squats\form_model.pkl', 'rb') as f:
    form_model = pickle.load(f)

# Label maps
form_labels = {
    0: 'Correct',
    1: 'Shallow squat',
    2: 'Forward lean',
    3: 'Knees caving in',
    4: 'Heels off ground',
    5: 'Asymmetric squat'
}

# Setup MediaPipe
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

cap = cv2.VideoCapture(r'C:\Users\Sebastian\squats\squat\squat_15.mp4')

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark

        # Raw keypoints for phase model
        kp = []
        for lm in landmarks:
            kp.extend([lm.x, lm.y, lm.z])

        # Calculate angles for form model
        def angle(a, b, c):
            a, b, c = np.array(a), np.array(b), np.array(c)
            ba, bc = a - b, c - b
            cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

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
        symmetry       = abs(left_knee - right_knee)
        hip_depth      = landmarks[23].y

        form_features = [[
            left_knee, right_knee, left_hip, right_hip,
            left_ankle, right_ankle, spine, torso_lean,
            left_knee_lat, right_knee_lat, symmetry, hip_depth
        ]]

        # Predictions
        # Predictions
        # Predictions
        phase = phase_model.predict([kp])[0]

        # Rep counting
        if not phase_sequence or phase != phase_sequence[-1]:
            phase_sequence.append(phase)
            if len(phase_sequence) >= 4:
                last4 = phase_sequence[-4:]
                if last4 == ['descending', 'bottom', 'ascending', 'standing']:
                    rep_count += 1
                    phase_sequence = []

        if phase == 'bottom':
            proba = form_model.predict_proba(form_features)[0]
            confidence = proba.max()
            predicted = proba.argmax()
            if confidence >= 0.80:
                form = form_labels[predicted]
            else:
                form = 'Correct'
        else:
            form = None

        # Display
        cv2.putText(frame, f'Phase: {phase}', (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.putText(frame, f'Reps: {rep_count}', (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)

        if form:
            color = (0, 255, 0) if form == 'Correct' else (0, 0, 255)
            cv2.putText(frame, f'Form: {form}', (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    cv2.imshow('Squat Analysis', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()