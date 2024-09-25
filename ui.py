from faulthandler import disable
import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QLineEdit
from PyQt5.QtGui import QTextCursor
from threading import Thread
from sp import toggle_mic, enable_mic, disable_mic
from tts import google_tts, text_to_speech

class Window(QWidget):
	def __init__(self, conversation):
		super().__init__()
		self.cv = conversation
		self.init_ui()
		mic_thread = Thread(target=self.mic_tracker)
		mic_thread.start()

	def init_ui(self):
		# Create a vertical layout to hold the widgets
		vbox = QVBoxLayout()

		# Create a label for the output text
		output_label = QLabel('Output:')
		vbox.addWidget(output_label)

		# Create a text edit widget for the output text
		self.output_text = QTextEdit()
		self.output_text.setReadOnly(True)
		vbox.addWidget(self.output_text)

		# Create a label for the input text
		input_label = QLabel('Input:')
		vbox.addWidget(input_label)

		# Create a line edit widget for the input text
		self.input_text = QLineEdit()
		vbox.addWidget(self.input_text)

		# Create a horizontal layout to hold the buttons
		self.button_layout = QHBoxLayout()

		# Create a button to clear the output text
		clear_button = QPushButton('Clear Output')
		clear_button.clicked.connect(self.clear_output)
		self.button_layout.addWidget(clear_button)

		# Create a button to clear the input text
		button_clear_input = QPushButton('Clear Input')
		button_clear_input.clicked.connect(self.clear_input)
		self.button_layout.addWidget(button_clear_input)

		# Create a button to process the input text
		process_button = QPushButton('Process Input')
		process_button.clicked.connect(self.process_input)
		self.button_layout.addWidget(process_button)

		# Create a button to toggle the mic
		mic_button = QPushButton('🎤')
		mic_button.setObjectName('mic_button')
		mic_button.clicked.connect(toggle_mic)
		self.button_layout.addWidget(mic_button)

		# Add the button layout to the vertical layout
		vbox.addLayout(self.button_layout)

		# Set the main window layout to the vertical layout
		self.setLayout(vbox)

		# Set the window title and size
		self.setWindowTitle('AI Chat')
		self.setGeometry(100, 100, 600, 400)

		# Show the window
		self.show()

	def mic_tracker(self):
		while True:
			from sp import DISABLE_MIC #get and refresh tts status
			mic_button = self.findChild(QPushButton, 'mic_button')
			if mic_button:
				if DISABLE_MIC:
					mic_button.setStyleSheet("background-color: red;")
				else:
					mic_button.setStyleSheet("background-color: green;")
			time.sleep(1/10)

	def clear_output(self):
		# Clear the output text
		self.output_text.clear()
	
	def clear_input(self):
		# Clear the output text
		self.input_text.clear()

	def process_input(self, google=True):
		# Get the input text and process it
		input_text = self.input_text.text().strip()
		# Replace this with your own processing code
		display_input = f'User: {input_text}\n\n'
		# Clear input
		self.clear_input()
		# Display the input text
		self.output_text.append(display_input)

		disable_mic()
		ai_resp = self.cv.speak(input_text)
		
		google=True
		if google:
			tts_thread = Thread(target=google_tts, args=(ai_resp,))
		else:
			tts_thread = Thread(target=text_to_speech, args=(ai_resp,))
		tts_thread.start()
		#self.output_text.append(display_output)
		display_output = f"AI: {ai_resp}\n"
		type_thread = Thread(target=self.slow_type, args=(display_output,))
		type_thread.start()


	def add_button(self, function_name):
		# Create a button for the specified function
		button = QPushButton(function_name)
		# Get the function object from its name
		function = globals()[function_name]
		# When the button is clicked, run the specified function
		button.clicked.connect(lambda: self.run_function(function))
		# Add the button to the button layout
		self.button_layout.addWidget(button)

	def run_function(self, function):
		# Run the specified function and display the result in the output text
		output_text = function()
		self.output_text.append(output_text)

	def slow_type(self, text):
		from tts import TTS_RUNNING #get and refresh tts status
		while TTS_RUNNING:
			time.sleep(1/10)
			from tts import TTS_RUNNING
		for w in text:
			text_cursor = self.output_text.textCursor()
			text_cursor.movePosition(QTextCursor.End)
			self.output_text.setTextCursor(text_cursor)
			self.output_text.insertPlainText(w)
			time.sleep(1/18)
		enable_mic()


if __name__ == '__main__':
	# Create the application instance
	app = QApplication(sys.argv)

	# Create the main window
	main_window = Window()

	# Add a button for function one
	main_window.add_button('function_one')

	# Add a button for function two
	main_window.add_button('function_two')

	# Run the application loop
	sys.exit(app.exec_())
