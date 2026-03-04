import numpy as np
import os
import csv

# -------------------------------
# Parameters
# -------------------------------
signal_folder = r"D:\coding\DRDO intern project\signal"
noise_folder  = r"D:\coding\DRDO intern project\noise"
os.makedirs(signal_folder, exist_ok=True)
os.makedirs(noise_folder, exist_ok=True)

Fs = 5000            # Sampling frequency (Hz)
duration = 30        # seconds
t = np.arange(0, duration, 1/Fs)

target_freq = 1028   # Hz

# -------------------------------
# Create signal CSV
# -------------------------------
signal = 0.05 * np.sin(2 * np.pi * target_freq * t) + 0.01 * np.random.randn(len(t))
signal_file = os.path.join(signal_folder, "signal.csv")
with open(signal_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Time", "Voltage"])
    for time_val, val in zip(t, signal):
        writer.writerow([time_val, val])
print(f"Created {signal_file}")

# -------------------------------
# Create noise CSV
# -------------------------------
noise = 0.01 * np.random.randn(len(t))
noise_file = os.path.join(noise_folder, "noise.csv")
with open(noise_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Time", "Voltage"])
    for time_val, val in zip(t, noise):
        writer.writerow([time_val, val])
print(f"Created {noise_file}")

print("\nSample 30-second signal and noise CSVs created successfully!")
