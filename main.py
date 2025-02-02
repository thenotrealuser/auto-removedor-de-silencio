import sys
import os
import shutil
import warnings
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QProgressBar, QTextEdit)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont
from pydub import AudioSegment, silence
import ffmpeg

# Verificação do módulo ffmpeg
if not hasattr(ffmpeg, 'input'):
    raise ImportError("O módulo 'ffmpeg' não possui o atributo 'input'. "
                      "Certifique-se de instalar 'ffmpeg-python' com 'pip install ffmpeg-python' "
                      "e desinstale qualquer outro pacote chamado 'ffmpeg'.")

# Configuração de avisos
warnings.filterwarnings("ignore", category=DeprecationWarning)

class VideoProcessor(QThread):
    update_progress = pyqtSignal(int)
    update_log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, input_path, output_path, threshold, min_silence_len):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.threshold = threshold
        self.min_silence_len = min_silence_len
        self.running = True

    def run(self):
        audio_path = 'temp_audio.wav'
        try:
            self.update_log.emit("Extraindo áudio do vídeo...")
            (
                ffmpeg
                .input(self.input_path)
                .output(audio_path, acodec='pcm_s16le', ar='44100', ac=1)
                .overwrite_output()
                .run(quiet=True)
            )

            self.update_log.emit("Analisando silêncios...")
            audio = AudioSegment.from_wav(audio_path)
            silence_ranges = silence.detect_silence(
                audio,
                min_silence_len=self.min_silence_len,
                silence_thresh=self.threshold
            )

            self.process_video_segments(
                [(start/1000, end/1000) for (start, end) in silence_ranges],
                len(audio)/1000  # duração em segundos
            )

            self.update_log.emit("Processamento concluído!")
        except Exception as e:
            self.update_log.emit(f"Erro crítico: {str(e)}")
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            self.finished.emit()

    def process_video_segments(self, silence_ranges, total_duration):
        segments = []
        last_end = 0

        for start, end in silence_ranges:
            if start > last_end:
                segments.append((last_end, start))
            last_end = end

        if last_end < total_duration:
            segments.append((last_end, total_duration))

        if not segments:
            self.update_log.emit("Nenhum silêncio detectado! Copiando vídeo original...")
            shutil.copyfile(self.input_path, self.output_path)
            return

        self.update_log.emit(f"Montando vídeo com {len(segments)} segmentos...")

        inputs = []
        for seg in segments:
            inputs.append(ffmpeg.input(self.input_path, ss=seg[0], t=seg[1]-seg[0]))

        streams = []
        for inp in inputs:
            streams.extend([inp.video, inp.audio])

        (
            ffmpeg
            .concat(*streams, v=1, a=1)
            .output(self.output_path, vcodec='libx264', acodec='aac')
            .overwrite_output()
            .run(quiet=True)
        )

from PyQt5.QtGui import QIcon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Vídeo Automático")

        # Definir o ícone da janela
        self.setWindowIcon(QIcon("icon.ico"))  # Substitua por seu arquivo de ícone

        self.setGeometry(100, 100, 600, 400)
        self.initUI()

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2E2E2E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #404040;
                color: #FFFFFF;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #505050;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #606060;
            }
            QTextEdit {
                background-color: #404040;
                color: #FFFFFF;
                border: 1px solid #606060;
                border-radius: 4px;
                font-family: Consolas;
            }
            QProgressBar {
                background-color: #404040;
                color: #FFFFFF;
                border: 1px solid #606060;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)

        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(9)
        self.setFont(font)

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Seção de arquivos
        file_section = self.create_file_section()
        main_layout.addLayout(file_section)

        # Configurações
        settings_section = self.create_settings_section()
        main_layout.addLayout(settings_section)

        # Progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        main_layout.addWidget(self.progress)

        # Log
        self.log = QTextEdit()
        self.log.setPlaceholderText("Log de processamento...")
        main_layout.addWidget(self.log)

        # Botões
        button_layout = QHBoxLayout()
        btn_process = QPushButton("Processar Vídeo")
        btn_process.clicked.connect(self.process_video)
        btn_process.setStyleSheet("background-color: #2196F3;")
        button_layout.addWidget(btn_process)
        main_layout.addLayout(button_layout)

    def create_file_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Selecione o vídeo de entrada...")
        btn_browse_input = QPushButton("Procurar")
        btn_browse_input.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(btn_browse_input)

        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Selecione o local de saída...")
        btn_browse_output = QPushButton("Procurar")
        btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(btn_browse_output)

        layout.addWidget(QLabel("Vídeo de Entrada:"))
        layout.addLayout(input_layout)
        layout.addWidget(QLabel("Local de Saída:"))
        layout.addLayout(output_layout)

        return layout

    def create_settings_section(self):
        layout = QHBoxLayout()
        layout.setSpacing(15)

        self.threshold = QLineEdit("-40")
        self.min_silence = QLineEdit("500")

        threshold_layout = QVBoxLayout()
        threshold_layout.addWidget(QLabel("Limite de Silêncio (dB):"))
        threshold_layout.addWidget(self.threshold)

        silence_layout = QVBoxLayout()
        silence_layout.addWidget(QLabel("Duração Mínima (ms):"))
        silence_layout.addWidget(self.min_silence)

        layout.addLayout(threshold_layout)
        layout.addLayout(silence_layout)

        return layout

    def browse_input(self):
        file, _ = QFileDialog.getOpenFileName(self, "Selecionar Vídeo", "", "Vídeos (*.mp4 *.avi *.mov)")
        if file:
            self.input_path.setText(file)

    def browse_output(self):
        file, _ = QFileDialog.getSaveFileName(self, "Salvar Vídeo", "", "MP4 (*.mp4)")
        if file:
            self.output_path.setText(file)

    def process_video(self):
        if not self.input_path.text() or not self.output_path.text():
            self.log.append("⚠️ Selecione os caminhos de entrada e saída!")
            return

        self.processor = VideoProcessor(
            input_path=self.input_path.text(),
            output_path=self.output_path.text(),
            threshold=int(self.threshold.text()),
            min_silence_len=int(self.min_silence.text())
        )

        self.processor.update_log.connect(lambda msg: self.log.append(f"► {msg}"))
        self.processor.finished.connect(lambda: self.log.append("✔️ Pronto!"))
        self.processor.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())