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
# Create dynamic signal CSV
# -------------------------------
# amplitude slowly varies over time + small random noise
amplitude_mod = 0.03 + 0.02 * np.sin(0.2 * t)  # slowly varying amplitude
signal = amplitude_mod * np.sin(2 * np.pi * target_freq * t) + 0.01 * np.random.randn(len(t))

signal_file = os.path.join(signal_folder, "signal.csv")
with open(signal_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Time", "Voltage"])
    for time_val, val in zip(t, signal):
        writer.writerow([time_val, val])
print(f"Created {signal_file}")

# -------------------------------
# Create dynamic noise CSV
# -------------------------------
# noise level varies slowly over time
noise_level = 0.01 + 0.01 * np.sin(0.1 * t)
noise = noise_level * np.random.randn(len(t))

noise_file = os.path.join(noise_folder, "noise.csv")
with open(noise_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Time", "Voltage"])
    for time_val, val in zip(t, noise):
        writer.writerow([time_val, val])
print(f"Created {noise_file}")

print("\nDynamic signal and noise CSVs created successfully!")
