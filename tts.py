from TTS.api import TTS
import io
from pydub import AudioSegment
from pydub.playback import play as pyplay
from pydub.effects import *
import numpy as np
import wave
import simpleaudio
import logging
import sys
import time
import sounddevice as sd

#NEW 
from google.cloud import texttospeech
import os
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.cloud import texttospeech

api_key = ''

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google.json'

TTS_RUNNING = False

def google_tts(text):
	global TTS_RUNNING 
	TTS_RUNNING = True
	start = time.time()
	client = texttospeech.TextToSpeechClient()
	synthesis_input = texttospeech.SynthesisInput(text=text)
	voice = texttospeech.VoiceSelectionParams(
		language_code="en-US", name="en-US-Wavenet-F" #en-US-Neural2-H (tiktok), n-GB-Neural2-F (peppy), en-US-Wavenet-F (mean), en-GB-Wavenet-A (influencer)
	)
	audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
	response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
	audio_data = io.BytesIO(response.audio_content)
	audio_segment = AudioSegment.from_file(audio_data, format="wav")
	print('google tts time:', time.time() - start)
	TTS_RUNNING = False
	pyplay(audio_segment)

#END NEW
# Running a multi-speaker and multi-lingual model

# List available 🐸TTS models and choose the first one
# for m in TTS.list_models():
# 	print(m)

# tts_models/en/ek1/tacotron2				# the best but super slow
# tts_models/en/ljspeech/tacotron2-DDC_ph 	# 8/10 and 2.9s
# tts_models/en/ljspeech/tacotron2-DCA		# 9/10 and 2.3s, 22050*1.07
# tts_models/en/sam/tacotron-DDC			# 9/10 and 4.0s monotone sadgirl, 16k*1.15
# tts_models/en/ljspeech/vits--neon			# 7/10 and 3.3s foreign professional
# tts_models/en/ljspeech/glow-tts			# 7/10 and 1.1s neutral and very fast 22050, ideal rate 27k
# tts_models/en/ljspeech/fast_pitch			# hilary, 22050*1.07
# tts_models/en/ljspeech/speedy-speech		# bad but fast

def play_audio(wav):
	sd.play(np.array(wav), int(22050*1.10))
	sd.wait()

def text_to_speech(text, play=True):
	global TTS_RUNNING 
	TTS_RUNNING = True
	start = time.time()

	# Define TTS model and vocoder
	model_name = 'tts_models/en/ljspeech/tacotron2-DCA' #TTS.list_models()[0]
	vocoder_path = 'vocoder_models/en/ek1/wavegrad' # vocoder_models/en/ek1/wavegrad, vocoder_models/universal/libri-tts/fullband-melgan, vocoder_models/en/sam/hifigan_v2, vocoder_models/en/blizzard2013/hifigan_v2, 'vocoder_models/en/ljspeech/hifigan_v2'
	
	# Init TTS
	tts = TTS(model_name, vocoder_path=vocoder_path, progress_bar=False)

	# Picking speakers and language if there are options
	speaker = tts.speakers
	lang = tts.languages
	if speaker:
		print(speaker)
		speaker = tts.speakers[0]
	if lang:
		lang = tts.languages[0]

	# Run TTS
	#text = "Sweet Goddamn Jesus Nutfucking Christ's Asshole Back From Hell for Revenge"
	wav = tts.tts(text, speaker=speaker, language=lang)
	print('tts time:', time.time() - start)
	TTS_RUNNING = False
	if play:
		play_audio(wav)
	return wav

#audio = buffer.getvalue() # wav.save_wav(wav=wav, path=buffer)
#audio = assemble_audio(wav)
#print(audio)
#audio_array = np.array(wav) #, dtype=np.float32
#audio_bytes = audio_array.astype(np.float_).tobytes()
#print(audio_bytes)
# Text to speech to a file
#tts.tts_to_file(text="Hello world!", speaker=speaker, language=lang, file_path="output.wav")

# Running a single speaker model

# Init TTS with the target model name
#tts = TTS(model_name="tts_models/de/thorsten/tacotron2-DDC", progress_bar=False, gpu=False)
#audio = AudioSegment.from_wav(audio)
#play(audio)
# Run TTS
#tts.tts_to_file(text="Ich bin eine Testnachricht.", file_path=OUTPUT_PATH)

# Example voice cloning with YourTTS in English, French and Portuguese:
#tts = TTS(model_name="tts_models/multilingual/multi-dataset/your_tts", progress_bar=False, gpu=True)
#tts.tts_to_file("This is voice cloning.", speaker_wav="my/cloning/audio.wav", language="en", file_path="output.wav")
#tts.tts_to_file("C'est le clonage de la voix.", speaker_wav="my/cloning/audio.wav", language="fr", file_path="output.wav")
#tts.tts_to_file("Isso é clonagem de voz.", speaker_wav="my/cloning/audio.wav", language="pt", file_path="output.wav")
