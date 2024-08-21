import sys
import os
import math
import io
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                             QWidget, QFileDialog, QListWidget, QProgressBar, QLabel, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import subprocess
import random
from PIL import Image
import cairosvg
import svgutils

MIN_SIZE = 0.5 * 1024 * 1024  # 0.5 MB in bytes
MAX_SIZE = 80 * 1024 * 1024   # 80 MB in bytes

def get_svg_dimensions(svg_path):
    svg = svgutils.transform.fromfile(svg_path)
    width = int(svg.width)
    height = int(svg.height)
    return width, height

def convert_to_eps(svg_file):
    base_name = os.path.splitext(svg_file)[0]
    eps_file = base_name + '.eps'
    
    # Convert SVG to EPS
    subprocess.run(['inkscape', '--export-filename=' + eps_file, 
                    '--export-type=eps', '--export-ps-level=2', svg_file],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Pad the EPS file to increase its size
    with open(eps_file, 'ab') as f:
        original_size = f.tell()
        target_size = max(MIN_SIZE, min(original_size * 2, MAX_SIZE))
        padding_size = target_size - original_size
        if padding_size > 0:
            padding = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=1000))
            padding = f"\n%% Padding to increase file size (ignore this): {padding}\n"
            while f.tell() < target_size:
                f.write(padding.encode())
    
    return eps_file

def convert_to_jpg(svg_file):
    base_name = os.path.splitext(svg_file)[0]
    jpg_file = base_name + '.jpg'
    
    try:
        width, height = get_svg_dimensions(svg_file)
        scale_factor = max(8000/width, 8000/height)
        scale_factor = math.ceil(scale_factor)
        scale_factor = scale_factor + 0.0

        png_data = cairosvg.svg2png(url=svg_file, scale=scale_factor)
        image = Image.open(io.BytesIO(png_data)).convert("RGB")
        image.save(jpg_file, format="JPEG", quality=95)
        print(f"Conversion to JPG successful: {svg_file} -> {jpg_file}")
    except Exception as e:
        print(f"JPG Conversion failed for {svg_file}: {str(e)}")
    
    return jpg_file

class ConversionThread(QThread):
    progress_update = pyqtSignal(int)
    conversion_complete = pyqtSignal()

    def __init__(self, svg_files, convert_function):
        super().__init__()
        self.svg_files = svg_files
        self.convert_function = convert_function

    def run(self):
        for i, svg_file in enumerate(self.svg_files, 1):
            self.convert_function(svg_file)
            self.progress_update.emit(int(i / len(self.svg_files) * 100))
        self.conversion_complete.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG to EPS and JPG Converter")
        self.setGeometry(100, 100, 600, 400)

        main_layout = QVBoxLayout()

        # File selection
        self.file_list = QListWidget()
        main_layout.addWidget(QLabel("Selected SVG Files:"))
        main_layout.addWidget(self.file_list)

        # Buttons
        button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select SVG Files")
        self.select_button.clicked.connect(self.select_files)
        self.convert_eps_button = QPushButton("Convert to EPS")
        self.convert_eps_button.clicked.connect(self.start_eps_conversion)
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.convert_eps_button)
        main_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.svg_files = []

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select SVG Files", "", "SVG Files (*.svg)")
        self.svg_files.extend(files)
        self.file_list.clear()
        self.file_list.addItems([os.path.basename(f) for f in self.svg_files])

    def start_eps_conversion(self):
        if not self.svg_files:
            self.status_label.setText("No files selected")
            return

        self.conversion_thread = ConversionThread(self.svg_files, convert_to_eps)
        self.conversion_thread.progress_update.connect(self.update_progress)
        self.conversion_thread.conversion_complete.connect(self.eps_conversion_finished)
        self.conversion_thread.start()

        self.select_button.setEnabled(False)
        self.convert_eps_button.setEnabled(False)
        self.status_label.setText("Converting to EPS...")

    def eps_conversion_finished(self):
        self.select_button.setEnabled(True)
        self.convert_eps_button.setEnabled(True)
        self.status_label.setText("EPS conversion complete")
        self.progress_bar.setValue(100)

        reply = QMessageBox.question(self, 'Convert to JPG', 
                                     'EPS conversion complete. Do you want to convert to JPG as well?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_jpg_conversion()

    def start_jpg_conversion(self):
        self.conversion_thread = ConversionThread(self.svg_files, convert_to_jpg)
        self.conversion_thread.progress_update.connect(self.update_progress)
        self.conversion_thread.conversion_complete.connect(self.jpg_conversion_finished)
        self.conversion_thread.start()

        self.select_button.setEnabled(False)
        self.convert_eps_button.setEnabled(False)
        self.status_label.setText("Converting to JPG...")
        self.progress_bar.setValue(0)

    def jpg_conversion_finished(self):
        self.select_button.setEnabled(True)
        self.convert_eps_button.setEnabled(True)
        self.status_label.setText("JPG conversion complete")
        self.progress_bar.setValue(100)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())