import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import tensorflow as tf
from tensorflow.keras.models import Sequential, model_from_json
from tensorflow.keras.layers import Dense, Conv1D, Flatten, MaxPooling1D
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam
import matplotlib.pyplot as plt
import joblib
import json
import os

def load_and_preprocess_data(file_path):
    df = pd.read_csv(file_path)
    df['Tanggal'] = pd.to_datetime(df['Tanggal'], format='%d/%m/%Y')
    df.set_index('Tanggal', inplace=True)
    return df

def engineer_features(df):
    df['Month'] = df.index.month
    df['Day'] = df.index.day
    df['Season'] = (df.index.month % 12 + 3) // 3
    df['DayOfWeek'] = df.index.dayofweek
    
    for i in range(1, 8):
        df[f'RR_Lag_{i}'] = df['RR'].shift(i)
    
    df['RR_Rolling_Mean_7'] = df['RR'].rolling(window=7).mean()
    df['RR_Rolling_Std_7'] = df['RR'].rolling(window=7).std()
    df['RR_Rolling_Max_7'] = df['RR'].rolling(window=7).max()
    
    return df.dropna()

def split_data(df, target_col='RR', test_size=0.2):
    X = df.drop(target_col, axis=1)
    y = df[target_col]
    return train_test_split(X, y, test_size=test_size, random_state=42)

def scale_features(X_train, X_test):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    return X_train_scaled, X_test_scaled, scaler

def create_cnn_model(input_shape):
    model = Sequential([
        Conv1D(filters=64, kernel_size=3, activation='relu', input_shape=input_shape),
        MaxPooling1D(pool_size=2),
        Conv1D(filters=32, kernel_size=3, activation='relu'),
        MaxPooling1D(pool_size=2),
        Flatten(),
        Dense(50, activation='relu'),
        Dense(1)
    ])
    optimizer = Adam(learning_rate=0.001)
    model.compile(optimizer=optimizer, loss='mse')
    print("CNN Model Summary:")
    model.summary()
    return model

def train_cnn(X_train, y_train, epochs=50, batch_size=32, patience=10):
    early_stopping = EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.2, patience=5, min_lr=0.0001)
    
    X_train_reshaped = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
    
    model = create_cnn_model((X_train.shape[1], 1))
    
    history = model.fit(
        X_train_reshaped, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )
    
    return model, history

def evaluate_model(y_true, y_pred):
    mse = mean_squared_error(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return mse, mae, r2

def plot_history(history):
    plt.figure(figsize=(12, 6))
    plt.plot(history.history['loss'], label='Training Loss')
    plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.title('CNN Model Loss over Epochs')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.savefig('cnn_model_loss.png')
    plt.close()

def plot_predictions(y_true, y_pred):
    plt.figure(figsize=(12, 6))
    plt.scatter(y_true, y_pred, alpha=0.5)
    plt.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--', lw=2)
    plt.xlabel('Actual')
    plt.ylabel('Predicted')
    plt.title('Actual vs Predicted Rainfall (CNN)')
    plt.savefig('cnn_actual_vs_predicted.png')
    plt.close()

def save_models(cnn_model, scaler, cnn_path='cnn_model', scaler_path='cnn_scaler.joblib'):
    try:
        model_json = cnn_model.to_json()
        with open(f"{cnn_path}_architecture.json", "w") as json_file:
            json_file.write(model_json)
        cnn_model.save_weights(f"{cnn_path}.weights.h5")
        
        joblib.dump(scaler, scaler_path)
        print("Model CNN dan scaler berhasil disimpan.")
    except Exception as e:
        print(f"Terjadi kesalahan saat menyimpan model CNN: {str(e)}")

def load_models(cnn_path='cnn_model', scaler_path='cnn_scaler.joblib'):
    try:
        with open(f"{cnn_path}_architecture.json", "r") as json_file:
            loaded_model_json = json_file.read()
        cnn_model = model_from_json(loaded_model_json)
        cnn_model.load_weights(f"{cnn_path}.weights.h5")
        cnn_model.compile(optimizer='adam', loss='mse')
        
        scaler = joblib.load(scaler_path)
        print("Model CNN dan scaler berhasil dimuat.")
        return cnn_model, scaler
    except Exception as e:
        print(f"Terjadi kesalahan saat memuat model CNN: {str(e)}")
        return None, None

def apply_threshold(predictions, threshold=0.5):
    return np.where(predictions < threshold, 0, predictions)

def get_random_samples(X, y, n_samples=20):
    if len(X) > n_samples:
        indices = np.random.choice(len(X), n_samples, replace=False)
        return X.iloc[indices], y.iloc[indices]
    else:
        return X, y

def main():
    choice = input("Apakah Anda ingin melakukan training baru untuk model CNN? (y/n): ").lower()

    if choice == 'y':
        df = load_and_preprocess_data('data_2010_4.csv')
        df = engineer_features(df)
        
        X_train, X_test, y_train, y_test = split_data(df)
        X_train_scaled, X_test_scaled, scaler = scale_features(X_train, X_test)
        
        print(f"X_train_scaled shape: {X_train_scaled.shape}")
        print(f"y_train shape: {y_train.shape}")
        
        cnn_model, history = train_cnn(X_train_scaled, y_train)
        
        plot_history(history)

        save_models(cnn_model, scaler)
    else:
        cnn_model, scaler = load_models()
        if cnn_model is None or scaler is None:
            print("Gagal memuat model CNN. Keluar dari program.")
            return

        df = load_and_preprocess_data('data_2010_4.csv')
        df = engineer_features(df)
        X, y = df.drop('RR', axis=1), df['RR']
        X_scaled = scaler.transform(X)
        X_test, y_test = pd.DataFrame(X_scaled, index=X.index, columns=X.columns), y

    X_test_sample, y_test_sample = get_random_samples(X_test, y_test, n_samples=50)

    X_test_array = X_test_sample.values
    X_test_reshaped = X_test_array.reshape((X_test_array.shape[0], X_test_array.shape[1], 1))
    predictions = cnn_model.predict(X_test_reshaped).flatten()
    
    threshold = 0.8
    predictions_thresholded = apply_threshold(predictions, threshold)
    
    mse, mae, r2 = evaluate_model(y_test_sample, predictions_thresholded)
    print(f"\nEvaluasi Model CNN (dengan threshold {threshold} mm):")
    print(f"Mean Squared Error: {mse:.4f}")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"R-squared Score: {r2:.4f}")

    print("\nPrediksi vs nilai aktual (dengan threshold):")
    for i in range(len(predictions)):
        print(f"Tanggal: {y_test_sample.index[i].strftime('%Y-%m-%d')}, "
              f"Prediksi: {predictions_thresholded[i]:.2f}, "
              f"Prediksi (tanpa threshold): {predictions[i]:.2f}, "
              f"Aktual: {y_test_sample.iloc[i]:.2f}")

    print("\nStatistik Tambahan (dengan threshold):")
    print(f"Rata-rata prediksi: {np.mean(predictions_thresholded):.2f}")
    print(f"Rata-rata aktual: {np.mean(y_test_sample):.2f}")
    print(f"Median prediksi: {np.median(predictions_thresholded):.2f}")
    print(f"Median aktual: {np.median(y_test_sample):.2f}")
    print(f"Standar deviasi prediksi: {np.std(predictions_thresholded):.2f}")
    print(f"Standar deviasi aktual: {np.std(y_test_sample):.2f}")

    y_test_binary = (y_test_sample > threshold).astype(int)
    predictions_binary = (predictions_thresholded > threshold).astype(int)
    accuracy = (y_test_binary == predictions_binary).mean()
    print(f"\nAkurasi klasifikasi hujan/tidak hujan (CNN): {accuracy:.4f}")

    plot_predictions(y_test_sample, predictions_thresholded)

if __name__ == "__main__":
    main()
