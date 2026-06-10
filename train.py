import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle

dataset = pd.read_csv('dataset.csv')

X = dataset[[f'kp_{i}' for i in range(99)]]
y = dataset['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print(classification_report(y_test, model.predict(X_test)))

with open('model.pkl', 'wb') as f:
    pickle.dump(model, f)

print('Model saved!')