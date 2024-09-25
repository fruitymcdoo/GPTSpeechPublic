from autocorrect import Speller
from threading import Thread
from PyQt5.QtWidgets import QApplication

import sys

from ai import Conversation
from ui import Window
from sp import ai_speak, stt, toggle_mic


DISABLE_MIC = False #allows us to selectively disable the mic when necessary, like when the AI speaks
STATUS_THREAD = False

def mic_manager(window):
	mic_stt = stt()
	spell = Speller()
	for text in mic_stt:
		text = spell(text)
		window.input_text.setText(f"{window.input_text.text()} {text}")


def main():
	cv = Conversation()
	app = QApplication(sys.argv)
	win = Window(cv)

	mic_thread = Thread(target=mic_manager, args=(win,))
	mic_thread.start()
	
	sys.exit(app.exec_())


if __name__ == "__main__":
	main()
