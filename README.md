# MagFTool

## ⚡ Magnetic Field Analyzer

![Alt Text](project_Img/homepg.png)

A desktop application for real-time analysis of magnetic field sensor data. It processes signal and noise waveforms from CSV files to calculate and visualize key metrics like B-field strength and sensor sensitivity.

 <!-- TODO: Replace with an actual screenshot of the application -->

## Key Features

-   **Real-time Visualization**: Live plots for B-field strength and sensitivity over time, with a dual-axis display.
-   **Frequency Domain Analysis**: Displays the Fast Fourier Transform (FFT) of the latest signal and noise segments, highlighting the target frequency.
-   **Configurable Parameters**: Easily adjust analysis settings like target frequency, bandwidth, current, and scaling factor through the UI.
-   **Robust Data Input**: Loads and concatenates data from multiple CSV files within specified signal and noise folders. The loader is designed to handle common variations in CSV formatting.
-   **Responsive UI**: The core analysis runs on a separate thread, ensuring the graphical interface remains smooth and responsive during processing.
-   **Detailed Logging**: An analysis log provides second-by-second updates on calculated values.
-   **Data Export**: Automatically saves detailed results (B-Field, SNR, Sensitivity) for each analysis interval into separate CSV files for further review.

## How It Works

The analyzer operates by processing data in discrete time intervals:

1.  **Data Loading**: The application loads all `.csv` files from the user-selected 'Signal' and 'Noise' folders. It intelligently attempts to parse the data, skipping headers and selecting the correct data column.
2.  **Concatenation**: Data from all files in each folder are concatenated into a single continuous signal waveform and noise waveform.
3.  **Segmentation**: The continuous waveforms are divided into segments based on the user-defined `Interval (s)`.
4.  **FFT Analysis**: For each segment, the application performs an FFT on both the signal and noise data.
5.  **Metric Calculation**:
    -   **Signal Amplitude**: Calculated from the FFT result at the specified `Target Freq (Hz)`.
    -   **Noise RMS**: Estimated from the FFT spectrum outside of the signal's `Bandwidth (Hz)`.
    -   **SNR**: The ratio of signal amplitude to noise RMS.
    -   **Sensitivity & B-Field**: These final metrics are calculated using the SNR and user-provided `Current (A)` and `Scaling Factor`.
6.  **GUI Update**: After each interval, the plots, numeric readouts, and log are updated with the new data.
7.  **File Output**: The results for the interval are written to a new CSV file in the `output_segments_1sec` directory.

## Installation

### Prerequisites

-   Python 3.7+
-   `git` (for cloning the repository)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd magnitool
    ```

2.  **Install the required packages:**
    A `requirements.txt` file is provided for easy setup.
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```

2.  **Configure the analysis:**
    -   **Upload Folders**: Click "Choose Folder" to select the directories containing your signal and noise data files.
    -   **Set Parameters**: Adjust the analysis parameters in the "Configuration" panel to match your experimental setup. See the Configuration Parameters section below for details.

3.  **Start the analysis:**
    -   Click the "Analyze Magnetic Field" button. The analysis will begin, and the UI will update in real-time.

### Input Data Format

The tool is designed to read standard CSV files.

-   **File Type**: Files must have a `.csv` extension.
-   **Structure**: The application expects the data to be in a single column. It automatically skips 1 or 2 header rows.
-   **Data Column**: It first tries to read the **second column** (index 1), assuming the first is a timestamp. If that fails, it tries the **first column** (index 0).
-   **Example**: The provided data generator scripts create CSVs with `Time` and `Voltage` columns. The tool will correctly use the `Voltage` column.

    ```csv
    Time,Voltage
    0.0,0.00123
    0.0002,-0.00456
    ...
    ```

### Generating Sample Data

If you don't have data, you can generate sample files using the included scripts. Note that you may need to adjust the output paths inside the scripts to match your system.

-   **Static Data**: `python csv_ganretor_script/s&n_creator.py`
-   **Dynamic Data**: `python csv_ganretor_script/dynamic_s&n_creator.py` (amplitude and noise level vary over time)

## Output

-   **Real-time Plots**: The GUI provides immediate visual feedback.
-   **Log Panel**: A running log of key metrics for each second of analysis.
-   **CSV Segments**: For each processed interval, a new file named `result_sec_N.csv` is created in the `output_segments_1sec` folder (located in the same directory as `main.py`). Each file contains:
    -   `Time_sec`
    -   `B_signal_pT`
    -   `SNR_linear`
    -   `Sensitivity_pT_per_sqrtHz`

## Configuration Parameters

| Parameter              | Description                                                                                             | Default Value |
| ---------------------- | ------------------------------------------------------------------------------------------------------- | ------------- |
| **Target Freq (Hz)**   | The specific frequency of the signal you want to analyze.                                               | `1028.0`      |
| **Bandwidth (Hz)**     | The bandwidth around the target frequency used to define the noise region for SNR calculation.          | `2.0`         |
| **Current (A)**        | The current applied to the sensor, used in the sensitivity calculation.                                 | `1.0`         |
| **Scaling Factor**     | A multiplier to convert the calculated result into the desired units (e.g., pT).                        | `1000.0`      |
| **Total Duration (s)** | The total time duration that the entire concatenated dataset represents. This is crucial for calculating the correct sampling rate (`Fs`). | `30`          |
| **Interval (s)**       | The duration of each analysis segment. The application processes the data in chunks of this size.       | `1.0`         |

<br>
<br>
<br>

---

<p align="center">Developed by sherry</p>