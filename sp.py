import time
from datetime import datetime
import threading, collections, queue, os, os.path
import deepspeech
import numpy as np
import pyaudio
import wave
import copy
import webrtcvad
import noisereduce as nr
from scipy import signal
from tts import text_to_speech, play_audio, google_tts
from ai import response, Conversation
from autocorrect import Speller


def print_status(message):
	global DISABLE_MIC
	while True:
		print(message, end="\r")
		time.sleep(0.5)
		if not DISABLE_MIC:
			break

class Audio(object):
	"""Streams raw audio from microphone. Data is received in a separate thread, and stored in a buffer, to be read from."""

	FORMAT = pyaudio.paInt16
	# Network/VAD rate-space
	RATE_PROCESS = 16000
	CHANNELS = 4
	BLOCKS_PER_SECOND = 50

	def __init__(self, callback=None, device=None, input_rate=RATE_PROCESS, file=None):
		def proxy_callback(in_data, frame_count, time_info, status):
			#pylint: disable=unused-argument
			if self.chunk is not None:
				in_data = self.wf.readframes(self.chunk)
			# bring 4ch audio down to 1ch
			audio_array = np.frombuffer(in_data, dtype=np.int16)
			audio_array = audio_array.reshape(-1, 4).T
			audio_array = np.mean(audio_array, axis=0)
			#audio_array = nr.reduce_noise(audio_array, sr=16000, prop_decrease=0.1) #reduce noise on all 4 channels
			audio_bytes = audio_array.astype(np.int16).tobytes()
			#
			callback(audio_bytes) #in_data
			return (None, pyaudio.paContinue)
		if callback is None: callback = lambda in_data: self.buffer_queue.put(in_data)
		self.buffer_queue = queue.Queue()
		self.device = device
		self.input_rate = input_rate
		self.sample_rate = self.RATE_PROCESS
		self.block_size = int(self.RATE_PROCESS / float(self.BLOCKS_PER_SECOND))
		self.block_size_input = int(self.input_rate / float(self.BLOCKS_PER_SECOND))
		self.pa = pyaudio.PyAudio()

		kwargs = {
			'format': self.FORMAT,
			'channels': self.CHANNELS,
			'rate': self.input_rate,
			'input': True,
			'frames_per_buffer': self.block_size_input,
			'stream_callback': proxy_callback,
		}

		self.chunk = None
		# if not default device
		if self.device:
			kwargs['input_device_index'] = self.device
		elif file is not None:
			self.chunk = 320
			self.wf = wave.open(file, 'rb')

		self.stream = self.pa.open(**kwargs)
		self.stream.start_stream()

	def resample(self, data, input_rate):
		"""
		Microphone may not support our native processing sampling rate, so
		resample from input_rate to RATE_PROCESS here for webrtcvad and
		deepspeech
		Args:
			data (binary): Input audio stream
			input_rate (int): Input audio rate to resample from
		"""
		data16 = np.frombuffer(buffer=data, dtype=np.int16)
		resample_size = int(len(data16) / self.input_rate * self.RATE_PROCESS)
		resample = signal.resample(data16, resample_size)
		resample16 = np.array(resample, dtype=np.int16)
		return resample16.tobytes()

	def read_resampled(self):
		"""Return a block of audio data resampled to 16000hz, blocking if necessary."""
		return self.resample(data=self.buffer_queue.get(),
							 input_rate=self.input_rate)

	def read(self):
		"""Return a block of audio data, blocking if necessary."""
		return self.buffer_queue.get()

	def destroy(self):
		self.stream.stop_stream()
		self.stream.close()
		self.pa.terminate()

	frame_duration_ms = property(lambda self: 1000 * self.block_size // self.sample_rate)


class VADAudio(Audio):
	"""Filter & segment audio with voice activity detection."""

	def __init__(self, aggressiveness=3, device=None, input_rate=None, file=None):
		super().__init__(device=device, input_rate=input_rate, file=file)
		self.vad = webrtcvad.Vad(aggressiveness)

	def frame_generator(self):
		"""Generator that yields all audio frames from microphone."""
		if self.input_rate == self.RATE_PROCESS:
			while True:
				yield self.read()
		else:
			while True:
				yield self.read_resampled()

	def vad_collector(self, padding_ms=300, ratio=0.75, frames=None):
		"""Generator that yields series of consecutive audio frames comprising each utterence, separated by yielding a single None.
			Determines voice activity by ratio of frames in padding_ms. Uses a buffer to include padding_ms prior to being triggered.
			Example: (frame, ..., frame, None, frame, ..., frame, None, ...)
					  |---utterence---|        |---utterence---|
		"""
		if frames is None: frames = self.frame_generator()
		num_padding_frames = padding_ms // self.frame_duration_ms
		ring_buffer = collections.deque(maxlen=num_padding_frames)
		triggered = False

		for frame in frames:
			if len(frame) < 640:
				return

			is_speech = self.vad.is_speech(frame, self.sample_rate)

			if not triggered:
				ring_buffer.append((frame, is_speech))
				num_voiced = len([f for f, speech in ring_buffer if speech])
				if num_voiced > ratio * ring_buffer.maxlen:
					triggered = True
					for f, s in ring_buffer:
						yield f
					ring_buffer.clear()

			else:
				yield frame
				ring_buffer.append((frame, is_speech))
				num_unvoiced = len([f for f, speech in ring_buffer if not speech])
				if num_unvoiced > ratio * ring_buffer.maxlen:
					triggered = False
					yield None
					ring_buffer.clear()

DISABLE_MIC = False #allows us to selectively disable the mic when necessary, like when the AI speaks

def toggle_mic():
	global DISABLE_MIC
	DISABLE_MIC = not(DISABLE_MIC)

def disable_mic():
	global DISABLE_MIC
	DISABLE_MIC = True

def enable_mic():
	global DISABLE_MIC
	DISABLE_MIC = False


def stt(vad=True, vad_agg=3, model='deepspeech-0.9.3-models.pbmm', file=None, device=None, rate=16000, padding=500, ratio=0.3): #300, 0.75
	"""Run speech-to-text on microphone stream,
	iterator yields text when parsed.
	Usage: for text in stt()"""
	# Load DeepSpeech model
	if os.path.isdir(model):
		model_dir = model
		model = os.path.join(model_dir, 'output_graph.pb')
	model = deepspeech.Model(model)

	# Start audio with VAD
	vad_audio = VADAudio(
		aggressiveness=vad_agg,
		device=device,
		input_rate=rate,
		file=file
	)

	if vad:
		frames = vad_audio.vad_collector(padding_ms=padding, ratio=ratio)
	else:
		frames = vad_audio.frame_generator()

	frame_count = 0
	frame_max = 1000 
	# defines the max number of frames, 
	# forces printing of text in case stream doesn't end

	stream_context = model.createStream()

	for frame in frames:
		if DISABLE_MIC:
			continue
		frame_count += 1
		if frame is not None: #if frame has audio
			stream_context.feedAudioContent(np.frombuffer(frame, np.int16))
			empty_count = 0
		# frame is None or   removed this block, now stream only ends on certain points
		if not frame or frame_count >= frame_max: #if frame does not have audio
			#check = stream_context.intermediateDecode() #if not check: #	continue
			text = stream_context.finishStream().strip()
			stream_context = model.createStream()
			stream_context.feedAudioContent( np.zeros( int(1 * 16000), dtype=np.int16 ) ) #add 1s of leading silence
			frame_count = 0
			words = text.split(" ")
			avg_w_len = sum([len(word) for word in words])/len(words)
			if avg_w_len > 2:
				yield text


def ai_speak(cv, text, google=False):
	toggle_mic()
	text = f"{a}."
	print(f"user: {text}")
	ai_resp = cv.speak(text)
	
	if google:
		google_tts(ai_resp)
	else:
		text_to_speech(ai_resp)

	print(f"response: {ai_resp}") #play resp after audio
	toggle_mic()


if __name__ == '__main__':
	running_text = ''
	cv = Conversation()
	spell = Speller()
	thread = None
	for a in stt(vad=False, vad_agg=2, rate=44000, padding=500, ratio=0.3):
		google = True
		#a = spell(a)
		user_input = input(f"Is this input acceptable (y)?\n{a}\n")
		if user_input == 'e':
			a = input("Enter your input manually:\n")
			user_input = 'y'
		if user_input == 'y':
			thread = threading.Thread(target=ai_speak, args=(cv,a,google))
			thread.start()
			input_string = ''
			user_input = None

