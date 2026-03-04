import sys
import os
import time
import csv
import threading
import numpy as np

# IMPORTANT: set the matplotlib backend to Qt5Agg before importing pyplot
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLineEdit, QDoubleSpinBox, QSpinBox, QTextEdit, QSizePolicy,
    QGraphicsDropShadowEffect, QScrollArea, QMessageBox # Import QMessageBox for user-friendly messages
)
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# -------------------------------
# Defaults & output folder
# -------------------------------
DEFAULT_TARGET_FREQ = 1028.0
DEFAULT_BW = 2.0
DEFAULT_CURRENT = 1.0
DEFAULT_SCALING = 1000.0
DEFAULT_TOTAL_DURATION = 30
DEFAULT_INTERVAL = 1

OUTPUT_FOLDER = os.path.join(os.getcwd(), "output_segments_1sec")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -------------------------------
# Worker Signals (thread-safe)
# -------------------------------
class WorkerSignals(QObject):
    # match the parameters we emit in the worker
    update_display = pyqtSignal(str, str, float, float, list, list, list, object, object, object)
    finished = pyqtSignal(str, str) # Added a second argument for output_folder path

# -------------------------------
# Utility: load CSVs (Enhanced with more attempts and debugging prints)
# -------------------------------
def load_csv_files_from_folder(folder):
    data_list = []
    if not folder or not os.path.isdir(folder):
        print(f"load_csv_files_from_folder: Folder '{folder}' is invalid or does not exist.")
        return data_list
    
    print(f"load_csv_files_from_folder: Scanning folder: {folder}")
    found_csvs = False
    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith(".csv"):
            found_csvs = True
            file_path = os.path.join(folder, filename)
            data_loaded = False
            
            # Define common loadtxt parameters
            loadtxt_params = {'delimiter': ',', 'encoding': 'utf-8', 'unpack': False} # unpack=False to get 2D array if usecols=[0,1]
            
            # --- Try different combinations of skiprows and usecols ---
            attempts = [
                {'skiprows': 1, 'usecols': [1], 'desc': 'col 1, skiprows 1'},
                {'skiprows': 1, 'usecols': [0], 'desc': 'col 0, skiprows 1'},
                {'skiprows': 2, 'usecols': [1], 'desc': 'col 1, skiprows 2 (extra header)'},
                {'skiprows': 2, 'usecols': [0], 'desc': 'col 0, skiprows 2 (extra header)'},
                # Add more attempts if your CSVs are complex, e.g., trying to read both columns if necessary
                # {'skiprows': 1, 'usecols': [0, 1], 'desc': 'cols 0,1, skiprows 1'},
            ]

            for attempt in attempts:
                try:
                    # np.loadtxt requires usecols to be a scalar or sequence of scalars,
                    # so we ensure it's a list.
                    data = np.loadtxt(file_path, **loadtxt_params, 
                                      skiprows=attempt['skiprows'], 
                                      usecols=attempt['usecols'][0] if len(attempt['usecols']) == 1 else attempt['usecols'])
                    
                    # If reading multiple columns, you might need to decide which one to use,
                    # for this tool, it expects a 1D array, so we ensure it's a single column
                    if data.ndim > 1:
                        data = data[:, 0] # Take the first column if multiple were read
                        
                    data_list.append(data)
                    data_loaded = True
                    print(f"  SUCCESS: Loaded {filename} using {attempt['desc']}. Data length: {len(data)}")
                    break # Stop trying if successful
                except ValueError as e:
                    print(f"  FAILED: {filename} (Attempt: {attempt['desc']}) - ValueError: {e}")
                except Exception as e:
                    print(f"  FAILED: {filename} (Attempt: {attempt['desc']}) - General Error: {e}")
            
            if not data_loaded:
                print(f"  ERROR: Failed to load data from {filename} after all attempts.")
    
    if not found_csvs:
        print(f"load_csv_files_from_folder: No CSV files found in '{folder}'.")
    elif not data_list:
        print(f"load_csv_files_from_folder: No data successfully loaded from any CSV in '{folder}'.")

    return data_list

# -------------------------------
# Analysis worker (Enhanced with debugging prints)
# -------------------------------
def run_analysis(signals: WorkerSignals,
                 target_freq, BW, current, scaling,
                 total_duration_sec, interval_sec,
                 signal_folder, noise_folder, output_folder):

    print(f"\n--- Starting Analysis Worker ---")
    print(f"  Signal Folder: '{signal_folder}'")
    print(f"  Noise Folder: '{noise_folder}'")
    print(f"  Parameters: Target Freq={target_freq} Hz, BW={BW} Hz, Current={current} A, Scaling={scaling}")
    print(f"              Total Duration={total_duration_sec}s, Interval={interval_sec}s")
    print(f"  Output Folder: '{output_folder}'") # Log the output folder

    signal_waveforms = load_csv_files_from_folder(signal_folder)
    noise_waveforms = load_csv_files_from_folder(noise_folder)

    if not signal_waveforms: # Using 'not list' to check if empty
        signals.finished.emit("No valid SIGNAL CSV files found or loaded from selected folder.", "") # Pass empty string for folder
        print("ERROR: No signal waveforms loaded.")
        return
    if not noise_waveforms: # Using 'not list' to check if empty
        signals.finished.emit("No valid NOISE CSV files found or loaded from selected folder.", "") # Pass empty string for folder
        print("ERROR: No noise waveforms loaded.")
        return

    print(f"  Worker: Successfully loaded {len(signal_waveforms)} signal files and {len(noise_waveforms)} noise files.")

    try:
        signal_data = np.concatenate(signal_waveforms)
        noise_data = np.concatenate(noise_waveforms)
    except ValueError as e:
        signals.finished.emit(f"Error concatenating waveforms: {e}. Ensure all CSVs have consistent data types.", "")
        print(f"ERROR: Error concatenating waveforms: {e}")
        return

    print(f"  Worker: Combined signal data length: {len(signal_data)}")
    print(f"  Worker: Combined noise data length: {len(noise_data)}")

    min_len = min(len(signal_data), len(noise_data))
    
    print(f"  Worker: Minimum combined data length (min_len): {min_len}")

    signal_data = signal_data[:min_len]
    noise_data = noise_data[:min_len]

    if total_duration_sec <= 0:
        signals.finished.emit("Invalid total duration (must be > 0).", "")
        print("ERROR: Invalid total duration.")
        return

    if min_len == 0:
        signals.finished.emit("No data available after concatenation (min_len is 0). Cannot analyze.", "")
        print("ERROR: min_len is 0. Cannot proceed with analysis.")
        return
        
    # Guard against zero total_duration_sec to prevent division by zero for Fs
    if total_duration_sec <= 0: # Redundant check but harmless
        signals.finished.emit("Total duration must be greater than zero for Fs calculation.", "")
        print("ERROR: Total duration <= 0 for Fs calculation (should have been caught earlier).")
        return

    Fs = min_len / float(total_duration_sec) # Corrected Fs calculation
    print(f"  Worker: Calculated Fs (Sampling Frequency): {Fs:.2f} Hz")

    if Fs <= 0:
        signals.finished.emit("Calculated sampling rate invalid (Fs <= 0). Ensure sufficient data and total duration.", "")
        print("ERROR: Fs is invalid (<=0).")
        return

    samples_per_interval = max(1, int(round(Fs * interval_sec)))
    print(f"  Worker: Samples per per interval: {samples_per_interval}")

    num_intervals = int(min_len / samples_per_interval)
    print(f"  Worker: Number of analysis intervals: {num_intervals}")

    if num_intervals == 0:
        signals.finished.emit("Not enough data or interval too large to create any analysis intervals.", "")
        print("ERROR: num_intervals is 0. Check data length, Fs, and interval_sec.")
        return

    B_values = []
    sensitivity_values = []
    time_seconds = []

    for i in range(num_intervals):
        start_time_loop = time.time()
        start_idx = i * samples_per_interval
        end_idx = (i + 1) * samples_per_interval
        
        if end_idx > len(signal_data) or end_idx > len(noise_data): 
            print(f"  WARNING: Segment end index {end_idx} exceeds data length. Breaking analysis loop after {i} intervals.")
            break

        segment_signal = signal_data[start_idx:end_idx].astype(float)
        segment_noise = noise_data[start_idx:end_idx].astype(float)
        N = len(segment_signal)
        
        print(f"  Worker: Processing interval {i+1}/{num_intervals}. Segment length (N): {N}")

        if N < 2: # Need at least 2 points for FFT and meaningful analysis
            print(f"  Worker: Skipping interval {i+1} due to insufficient segment length (N={N}). Need N >= 2 for FFT.")
            continue 

        # detrend (simple mean remove)
        segment_signal = segment_signal - np.mean(segment_signal)
        segment_noise = segment_noise - np.mean(segment_noise)

        # FFT
        fft_signal = np.fft.fft(segment_signal)
        # Ensure N is not zero for division, though N < 2 check should handle it
        fft_signal = np.abs(fft_signal[:max(1, N // 2)]) * 2.0 / max(1, N) 
        fft_noise = np.fft.fft(segment_noise)
        fft_noise = np.abs(fft_noise[:max(1, N // 2)]) * 2.0 / max(1, N)
        
        if Fs > 0:
            freqs = np.fft.fftfreq(N, 1.0 / Fs)[:max(1, N // 2)]
        else:
            freqs = np.array([]) 
        
        print(f"    Freqs array size: {freqs.size}")
        if freqs.size > 0:
            print(f"    Max frequency in FFT: {freqs.max():.2f} Hz")
        else:
            print("    WARNING: Freqs array is empty. Cannot perform frequency-domain analysis for this segment.")

        if freqs.size == 0: # Guard against empty freqs for subsequent calculations
            df = 1.0
            i_signal = 0 
        else:
            df = freqs[1] - freqs[0] if freqs.size > 1 else (freqs[0] if freqs.size == 1 else 1.0)
            i_signal = int(np.argmin(np.abs(freqs - target_freq)))
            i_signal = max(0, min(i_signal, len(freqs)-1))
        
        print(f"    df: {df:.4f}, i_signal (index near target freq {target_freq} Hz): {i_signal}")

        low = max(0, i_signal - 1)
        high = min(len(fft_signal), i_signal + 2)
        signal_amp = 0.0
        if high > low:
            signal_amp = float(np.mean(fft_signal[low:high]))
        print(f"    Estimated signal amplitude: {signal_amp:.4e}")

        # noise estimate
        i_bw = max(1, int(round(BW / max(1e-12, df))))
        idx_left = np.arange(0, max(0, i_signal - i_bw))
        idx_right = np.arange(min(len(freqs), i_signal + i_bw), len(freqs))
        noise_indices = np.concatenate([idx_left, idx_right]) if (idx_left.size + idx_right.size) > 0 else np.array([], dtype=int)
        
        noise_rms = 1e-12 # Default to a small non-zero value
        if noise_indices.size > 0 and fft_noise.size > 0:
            try:
                noise_rms = float(np.mean(fft_noise[noise_indices]))
            except IndexError:
                print(f"    WARNING: noise_indices {noise_indices} out of bounds for fft_noise (len {fft_noise.size}). Using fallback noise_rms.")
            if noise_rms <= 0: # Fallback if calculated noise is zero
                if noise_indices.size > 0 and fft_signal.size > 0:
                    try:
                        noise_rms = float(np.mean(fft_signal[noise_indices]))
                    except IndexError:
                        print(f"    WARNING: noise_indices {noise_indices} out of bounds for fft_signal (len {fft_signal.size}). Using default 1e-12.")
                        noise_rms = 1e-12
                else:
                    noise_rms = 1e-12
        print(f"    Estimated noise RMS: {noise_rms:.4e}")

        SNR_linear = signal_amp / noise_rms if noise_rms != 0 else 0.0
        if SNR_linear <= 0:
            sensitivity_pT = 0.0
        else:
            sensitivity_pT = float(current / (SNR_linear * np.sqrt(max(BW, 1e-12))) * scaling)

        B_signal = sensitivity_pT * np.sqrt(max(BW, 1e-12)) * SNR_linear
        
        print(f"    Calculated SNR: {SNR_linear:.2f}, B_signal: {B_signal:.2f} pT, Sensitivity: {sensitivity_pT:.2f} pT/√Hz")

        B_values.append(B_signal)
        sensitivity_values.append(sensitivity_pT)
        time_seconds.append((i + 1) * interval_sec)

        # save per-second CSV
        csv_file = os.path.join(output_folder, f"result_sec_{i+1}.csv")
        try:
            with open(csv_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Time_sec", "B_signal_pT", "SNR_linear", "Sensitivity_pT_per_sqrtHz"])
                writer.writerow([i + 1, B_signal, SNR_linear, sensitivity_pT])
        except Exception as e:
            print(f"ERROR: Could not write CSV {csv_file}: {e}")

        # emit update (use plain python objects for arrays)
        print(f"  Worker: Emitting update signal for interval {i+1}...")
        signals.update_display.emit(
            f"Sensitivity: {sensitivity_pT:.2f} pT/√Hz",
            f"B-Field: {B_signal:.2f} pT",
            float(B_signal), float(sensitivity_pT),
            list(time_seconds), list(B_values), list(sensitivity_values),
            freqs.copy(), fft_signal.copy(), fft_noise.copy()
        )

        elapsed = time.time() - start_time_loop
        if elapsed < interval_sec:
            time.sleep(interval_sec - elapsed)

    signals.finished.emit(f"Analysis completed!\nResults saved in:", output_folder) # Pass output_folder separately
    print(f"--- Analysis Worker Finished ---")

# -------------------------------
# Main GUI (fixed and enhanced debugging)
# -------------------------------
class MagneticAnalyzerFixed(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ Magnetic Field Analyzer")
        self.setGeometry(120, 60, 1100, 880) # Original height seems sufficient with layout fixes
        self.setWindowIcon(QIcon())

        # stylesheet gradient for background (no QPalette usage)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0 y1:0, x2:1 y2:1,
                    stop:0 #f2f7fb, stop:1 #e8f0fb);
            }
        """)

        self.worker_signals = WorkerSignals()
        self.worker_signals.update_display.connect(self.update_gui_elements)
        self.worker_signals.finished.connect(self.analysis_finished) # Connect the new method

        self._build_ui()

    def _build_ui(self):
        title = QLabel("Magnetic Field Analyzer")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setAlignment(Qt.AlignHCenter)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(12)
        root_layout.addWidget(title)

        # top card: configuration (white content with colored header)
        card = QFrame()
        card.setStyleSheet("QFrame { background: transparent; }")
        card_layout = QVBoxLayout()
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card.setLayout(card_layout)

        # header (gradient)
        header = QLabel("Configuration")
        header.setFont(QFont("Segoe UI", 22, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(92)
        header.setStyleSheet("""
            QLabel {
                color: white;
                background: qlineargradient(x1:0 y1:0, x2:1 y2:0,
                    stop:0 #6a47d9, stop:0.5 #8a61e6, stop:1 #2ea0f2);
                border-top-left-radius:12px; border-top-right-radius:12px;
            }
        """)
        card_layout.addWidget(header)

        # content (white)
        content = QFrame()
        content.setStyleSheet("""
            QFrame { background: white; border-bottom-left-radius:12px; border-bottom-right-radius:12px; }
            QLabel.field-label { font-size: 16px; color: #444; font-weight: bold;} /* Increased font size and made bold */
            QDoubleSpinBox, QSpinBox {
                font-size: 14px; /* Slightly smaller than label for input values */
                font-weight: normal;
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                padding: 3px;
            }
        """)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(18, 16, 18, 18)
        content_layout.setSpacing(12)
        content.setLayout(content_layout)

        # grid for inputs
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        lbl_signal = QLabel("Upload Signal Folder:")
        lbl_signal.setProperty("class", "field-label") # Apply the style class
        self.input_signal = QLineEdit()
        self.input_signal.setReadOnly(True)
        self.input_signal.setPlaceholderText("//path-to_signal_data")
        btn_sig = QPushButton("Choose Folder")
        btn_sig.clicked.connect(self.select_signal_folder)

        lbl_noise = QLabel("Upload Noise Folder:")
        lbl_noise.setProperty("class", "field-label") # Apply the style class
        self.input_noise = QLineEdit()
        self.input_noise.setReadOnly(True)
        self.input_noise.setPlaceholderText("//path-to_noise_data")
        btn_noi = QPushButton("Choose Folder")
        btn_noi.clicked.connect(self.select_noise_folder)

        lbl_tf = QLabel("Target Freq (Hz):")
        lbl_tf.setProperty("class", "field-label")
        self.spin_tf = QDoubleSpinBox(); self.spin_tf.setMaximum(1e6); self.spin_tf.setValue(DEFAULT_TARGET_FREQ)
        lbl_bw = QLabel("Bandwidth (Hz):")
        lbl_bw.setProperty("class", "field-label")
        self.spin_bw = QDoubleSpinBox(); self.spin_bw.setMaximum(1e6); self.spin_bw.setValue(DEFAULT_BW)
        lbl_current = QLabel("Current (A):")
        lbl_current.setProperty("class", "field-label")
        self.spin_current = QDoubleSpinBox(); self.spin_current.setDecimals(3); self.spin_current.setMaximum(1e6); self.spin_current.setValue(DEFAULT_CURRENT)
        lbl_scaling = QLabel("Scaling Factor:")
        lbl_scaling.setProperty("class", "field-label")
        self.spin_scaling = QDoubleSpinBox(); self.spin_scaling.setMaximum(1e9); self.spin_scaling.setValue(DEFAULT_SCALING)
        lbl_total = QLabel("Total Duration (s):")
        lbl_total.setProperty("class", "field-label")
        self.spin_total = QSpinBox(); self.spin_total.setMaximum(86400); self.spin_total.setValue(DEFAULT_TOTAL_DURATION)
        lbl_interval = QLabel("Interval (s):")
        lbl_interval.setProperty("class", "field-label")
        self.spin_interval = QDoubleSpinBox(); self.spin_interval.setMaximum(3600); self.spin_interval.setValue(DEFAULT_INTERVAL)

        # place widgets
        grid.addWidget(lbl_signal, 0, 0)
        grid.addWidget(self.input_signal, 0, 1)
        grid.addWidget(btn_sig, 0, 2)
        grid.addWidget(lbl_noise, 1, 0)
        grid.addWidget(self.input_noise, 1, 1)
        grid.addWidget(btn_noi, 1, 2)

        grid.addWidget(lbl_tf, 2, 0)
        grid.addWidget(self.spin_tf, 2, 1)
        grid.addWidget(lbl_bw, 3, 0)
        grid.addWidget(self.spin_bw, 3, 1)
        grid.addWidget(lbl_current, 4, 0)
        grid.addWidget(self.spin_current, 4, 1)
        grid.addWidget(lbl_scaling, 5, 0)
        grid.addWidget(self.spin_scaling, 5, 1)
        grid.addWidget(lbl_total, 6, 0)
        grid.addWidget(self.spin_total, 6, 1)
        grid.addWidget(lbl_interval, 7, 0)
        grid.addWidget(self.spin_interval, 7, 1)

        content_layout.addLayout(grid)

        # analyze button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_analyze = QPushButton("Analyze Magnetic Field")
        self.btn_analyze.setFixedHeight(44)
        self.btn_analyze.setFixedWidth(360)
        self.btn_analyze.clicked.connect(self.on_analyze)
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                color: white;
                border-radius: 22px;
                background: qlineargradient(x1:0 y1:0, x2:1 y2:0,
                    stop:0 #a14de6, stop:1 #1ea0f2);
                font-weight: bold;
            }
        """)
        btn_box.addWidget(self.btn_analyze)
        btn_box.addStretch()
        content_layout.addLayout(btn_box)

        # drop shadow for content
        shadow = QGraphicsDropShadowEffect(blurRadius=22, xOffset=0, yOffset=8)
        shadow.setColor(QColor(0, 0, 0, 40))
        content.setGraphicsEffect(shadow)

        card_layout.addWidget(content)
        root_layout.addWidget(card)

        # lower section: readouts + log + plots
        readout_layout = QHBoxLayout()
        self.display_b = QLabel("B-Field: 0.00 pT")
        self.display_b.setFont(QFont("Consolas", 14, QFont.Bold))
        self.display_b.setStyleSheet("color: #6a0dad; background: white; padding:10px; border-radius:8px;")
        self.display_sens = QLabel("Sensitivity: N/A")
        self.display_sens.setFont(QFont("Consolas", 14, QFont.Bold))
        self.display_sens.setStyleSheet("color: #1e88e5; background: white; padding:10px; border-radius:8px;")
        readout_layout.addWidget(self.display_b)
        readout_layout.addStretch()
        readout_layout.addWidget(self.display_sens)
        root_layout.addLayout(readout_layout)

        mid_h = QHBoxLayout()
        mid_h.setSpacing(25) # Increased spacing between log and plots

        # log panel
        log_frame = QFrame()
        log_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding) # Fixed width, expanding height
        log_frame.setMinimumWidth(320)
        log_frame.setMaximumWidth(400) # Give it some bounds
        log_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                font-weight: bold;
                margin-bottom: 5px;
                color: #333;
                font-size: 14px;
            }
            QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 5px;
                background-color: #f8f8f8;
            }
        """)

        log_layout = QVBoxLayout(log_frame) # Use log_frame as parent for log_layout
        log_label = QLabel("Analysis Log:")
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setMinimumHeight(360)
        log_layout.addWidget(log_label)
        log_layout.addWidget(self.text_log)
        mid_h.addWidget(log_frame) # No stretch for the fixed-width frame

        # plots
        # Create figure and subplots once, disable tight_layout and use subplots_adjust
        self.fig, (self.ax_time, self.ax_fft) = plt.subplots(nrows=2, ncols=1, figsize=(8.5, 6.0))
        # IMPORTANT: Disable tight_layout and use subplots_adjust for stable spacing
        try:
            self.fig.set_tight_layout(False)
        except Exception:
            pass
        # Adjusted hspace for more gap between the two plots initially
        # Values will be further adjusted in _initialize_plots and update_gui_elements
        # Increased right margin for twinx labels
        self.fig.subplots_adjust(hspace=0.6, top=0.92, bottom=0.15, left=0.12, right=0.82) # Adjusted 'right'

        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 

        # Wrap canvas in a QScrollArea for the FFT plot if needed (for X-axis labels)
        self.plot_scroll_area = QScrollArea()
        self.plot_scroll_area.setWidgetResizable(True)
        self.plot_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.plot_scroll_area.setWidget(self.canvas)
        mid_h.addWidget(self.plot_scroll_area, stretch=1) # Canvas takes all remaining space

        root_layout.addLayout(mid_h)
        self.setLayout(root_layout)

        # initialize plots and twin axis
        self._initialize_plots()

    def _initialize_plots(self):
        print("\n--- Initializing Plots ---")
        # Time axis
        self.ax_time.clear()
        self.ax_time.set_title("Magnetic Field and Sensitivity vs Time", fontsize=14, fontweight='bold')
        self.ax_time.set_xlabel("Time (s)", fontsize=12)
        
        # Increase labelpad for left Y-axis
        self.ax_time.set_ylabel("Magnetic Field (pT)", color="#6a0dad", fontsize=12, labelpad=20) # Increased labelpad
        self.ax_time.tick_params(axis='y', labelcolor="#6a0dad", labelsize=10)
        self.ax_time.tick_params(axis='x', labelcolor='black', labelsize=10)
        self.ax_time.grid(True, linestyle='--', alpha=0.6, linewidth=1.2)
        
        if not hasattr(self, 'ax_sens'):
            self.ax_sens = self.ax_time.twinx()
            print("  Created new twinx axis (ax_sens).")
        else:
            self.ax_sens.clear()
            print("  Cleared existing twinx axis (ax_sens).")

        # Increase labelpad for right Y-axis
        self.ax_sens.set_ylabel("Sensitivity (pT/√Hz)", color="#1e88e5", fontsize=12, labelpad=20) # Increased labelpad
        self.ax_sens.tick_params(axis='y', labelcolor="#1e88e5", labelsize=10)
        self.ax_sens.spines['right'].set_color('#1e88e5')
        self.ax_sens.spines['left'].set_color('#6a0dad')

        # FFT axis
        self.ax_fft.clear()
        self.ax_fft.set_title("FFT of Signal and Noise (Latest Segment)", fontsize=14, fontweight='bold')
        self.ax_fft.set_xlabel("Frequency (Hz)", fontsize=12)
        self.ax_fft.set_ylabel("Amplitude", fontsize=12)
        self.ax_fft.tick_params(axis='x', labelcolor='black', labelsize=10)
        self.ax_fft.tick_params(axis='y', labelsize=10)
        self.ax_fft.grid(True, linestyle='--', alpha=0.6, linewidth=1.2)

        self.canvas.draw_idle()
        print("--- Plots Initialized ---")

    def select_signal_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Signal Folder")
        if folder:
            self.input_signal.setText(folder)
            print(f"GUI: Signal folder selected: {folder}")

    def select_noise_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Noise Folder")
        if folder:
            self.input_noise.setText(folder)
            print(f"GUI: Noise folder selected: {folder}")

    def on_analyze(self):
        signal_folder = self.input_signal.text().strip()
        noise_folder = self.input_noise.text().strip()
        if not signal_folder or not noise_folder:
            QMessageBox.warning(self, "Input Error", "Please select both signal and noise folders before analyzing.")
            self.text_log.append("Please select both signal and noise folders.")
            print("GUI: Analysis blocked - folders not selected.")
            return

        target_freq = float(self.spin_tf.value())
        BW = float(self.spin_bw.value())
        current = float(self.spin_current.value())
        scaling = float(self.spin_scaling.value())
        total_duration = int(self.spin_total.value())
        interval = float(self.spin_interval.value())

        self.btn_analyze.setEnabled(False)
        self.text_log.clear()
        self._initialize_plots() # Re-initialize plots for a fresh start
        self.text_log.append("Starting analysis...")
        print("GUI: Starting analysis thread...")

        thread = threading.Thread(
            target=run_analysis,
            args=(self.worker_signals,
                  target_freq, BW, current, scaling,
                  total_duration, interval,
                  signal_folder, noise_folder, OUTPUT_FOLDER),
            daemon=True
        )
        thread.start()

    def update_gui_elements(self, sens_text, b_field_text, B_signal, sensitivity_pT,
                            time_seconds, B_values, sensitivity_values,
                            freqs, fft_signal, fft_noise):
        print(f"\n--- GUI Slot: update_gui_elements received ---")
        print(f"  B-Field Text: '{b_field_text}', Sensitivity Text: '{sens_text}'")
        print(f"  Time seconds list length: {len(time_seconds)}")
        print(f"  B_values list length: {len(B_values)}")
        print(f"  Sensitivity_values list length: {len(sensitivity_values)}")
        print(f"  Freqs array size: {freqs.size if hasattr(freqs, 'size') else 'N/A'}")
        print(f"  FFT Signal array size: {fft_signal.size if hasattr(fft_signal, 'size') else 'N/A'}")
        print(f"  FFT Noise array size: {fft_noise.size if hasattr(fft_noise, 'size') else 'N/A'}")

        # update readouts and log
        self.display_b.setText(b_field_text)
        self.display_sens.setText(sens_text)
        idx = len(time_seconds)
        self.text_log.append(f"Sec {idx:>2}: B={B_signal:.2f} pT, Sens={sensitivity_pT:.2f} pT/√Hz")

        # Time plot (clear and redraw)
        self.ax_time.clear()
        self.ax_time.set_title("Magnetic Field and Sensitivity vs Time", fontsize=14, fontweight='bold')
        self.ax_time.set_xlabel("Time (s)", fontsize=12)
        # Apply the increased labelpad here as well
        self.ax_time.set_ylabel("Magnetic Field (pT)", color="#6a0dad", fontsize=12, labelpad=20)
        self.ax_time.tick_params(axis='y', labelcolor="#6a0dad", labelsize=10)
        self.ax_time.tick_params(axis='x', labelcolor='black', labelsize=10)
        self.ax_time.grid(True, linestyle='--', alpha=0.6, linewidth=1.2)
        
        if B_values: # Only plot if there's data
            self.ax_time.plot(time_seconds, B_values, marker='o', linewidth=2.2, label='B-Field (pT)', color='#6a0dad')
            print("  Plotting B-Field vs Time.")
        else:
            print("  WARNING: B_values is empty, not plotting time-domain B-Field.")

        # Sensitivity twin axis (reuse existing twin)
        self.ax_sens.clear() 
        # Apply the increased labelpad here as well
        self.ax_sens.set_ylabel("Sensitivity (pT/√Hz)", color="#1e88e5", fontsize=12, labelpad=20)
        self.ax_sens.tick_params(axis='y', labelcolor="#1e88e5", labelsize=10)
        self.ax_sens.spines['right'].set_color('#1e88e5')
        self.ax_sens.spines['left'].set_color('#6a0dad')
        
        if sensitivity_values: # Only plot if there's data
            self.ax_sens.plot(time_seconds, sensitivity_values, marker='x', linewidth=1.8, linestyle='--', label='Sensitivity (pT/√Hz)', color='#1e88e5')
            print("  Plotting Sensitivity vs Time.")
        else:
            print("  WARNING: sensitivity_values is empty, not plotting time-domain Sensitivity.")

        # Set specific y-axis limits to prevent overlapping if ranges are too different
        if B_values:
            min_b, max_b = np.min(B_values), np.max(B_values)
            padding_b = (max_b - min_b) * 0.1 if (max_b - min_b) > 0 else 1
            self.ax_time.set_ylim(min_b - padding_b, max_b + padding_b)
        if sensitivity_values:
            min_s, max_s = np.min(sensitivity_values), np.max(sensitivity_values)
            padding_s = (max_s - min_s) * 0.1 if (max_s - min_s) > 0 else 1
            self.ax_sens.set_ylim(min_s - padding_s, max_s + padding_s)

        h1, l1 = self.ax_time.get_legend_handles_labels()
        h2, l2 = self.ax_sens.get_legend_handles_labels()
        if h1 or h2:
            self.ax_time.legend(h1 + h2, l1 + l2, loc='upper left', bbox_to_anchor=(0.02, 0.95), framealpha=0.9, fontsize=10)
            print("  Added combined legend.")

        # FFT plot (guarded)
        self.ax_fft.clear()
        self.ax_fft.set_title("FFT of Signal and Noise (Latest Segment)", fontsize=14, fontweight='bold')
        self.ax_fft.set_xlabel("Frequency (Hz)", fontsize=12)
        self.ax_fft.set_ylabel("Amplitude", fontsize=12)
        self.ax_fft.tick_params(axis='x', labelsize=10, labelcolor='black')
        self.ax_fft.tick_params(axis='y', labelsize=10)
        self.ax_fft.grid(True, linestyle='--', alpha=0.6, linewidth=1.2)

        try:
            if hasattr(freqs, 'size') and freqs.size > 0:
                print("  FFT: Freqs array is valid for plotting.")
                if fft_signal.size > 0:
                    self.ax_fft.plot(freqs, fft_signal, label='Signal', linewidth=1.6)
                    print("  FFT: Plotted Signal.")
                else:
                    print("  WARNING: FFT Signal data is empty, not plotting Signal.")
                if fft_noise.size > 0:
                    self.ax_fft.plot(freqs, fft_noise, label='Noise', linewidth=1.2)
                    print("  FFT: Plotted Noise.")
                else:
                    print("  WARNING: FFT Noise data is empty, not plotting Noise.")
                
                self.ax_fft.axvline(float(self.spin_tf.value()), color='red', linestyle='--', linewidth=1.2, label='Target Freq')
                print(f"  FFT: Added vertical line at Target Freq: {self.spin_tf.value()} Hz.")
                
                max_freq = freqs.max() if freqs.size > 0 else 1.0
                self.ax_fft.set_xlim(0, max_freq * 1.05)
                self.ax_fft.legend(loc='upper right', framealpha=0.9, fontsize=10)
            else:
                self.ax_fft.text(0.5, 0.5, "No FFT data to display (empty or invalid 'freqs')",
                                 horizontalalignment='center', verticalalignment='center',
                                 transform=self.ax_fft.transAxes, fontsize=12, color='gray')
                print("  WARNING: Freqs array is empty or invalid for FFT plot. Displaying placeholder text.")

        except Exception as e:
            print(f"  ERROR plotting FFT: {e}")
            self.ax_fft.text(0.5, 0.5, f"Error plotting FFT: {e}",
                             horizontalalignment='center', verticalalignment='center',
                             transform=self.ax_fft.transAxes, fontsize=12, color='red')

        try:
            # Re-apply subplot adjustments with potentially updated margins
            self.fig.subplots_adjust(hspace=0.6, top=0.92, bottom=0.15, left=0.12, right=0.82) # Adjusted 'right'
            print("  Adjusted subplot spacing.")
        except Exception as e:
            print(f"  ERROR in subplots_adjust: {e}")

        self.canvas.draw_idle()
        print(f"--- GUI Slot: update_gui_elements finished drawing ---")

    def analysis_finished(self, message, output_path):
        """
        Handles the completion of the analysis thread.
        Re-enables the analyze button and displays a final message.
        """
        self.btn_analyze.setEnabled(True)
        self.text_log.append(message)
        if output_path:
            self.text_log.append(f"Output files can be found at: {output_path}")
            QMessageBox.information(self, "Analysis Complete", f"{message}\n\nResults saved in:\n{output_path}")
        else:
            QMessageBox.warning(self, "Analysis Halted", message)
        print(f"GUI: Analysis finished with message: {message}")
        print(f"GUI: Output path: {output_path}")


# -------------------------------
# Run
# -------------------------------
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MagneticAnalyzerFixed()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()