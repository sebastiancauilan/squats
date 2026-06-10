import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle


dataset = pd.read_csv('squat_features_augmented.csv')

features = [
     'left_knee_angle', 'right_knee_angle',
    'left_hip_angle', 'right_hip_angle',
    'left_ankle_angle', 'right_ankle_angle',
    'spine_angle', 'torso_lean',
    'left_knee_lateral', 'right_knee_lateral',
    'symmetry_score', 'hip_depth'
]

X = dataset[features]
y = dataset['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state = 42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print(classification_report(y_test, model.predict(X_test)))

with open('form_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print('Form model saved!')
