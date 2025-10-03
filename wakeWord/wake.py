from openwakeword.model import Model
import sounddevice as sd

SR = 16000
FRAME_MS = 80
SAMPLES = int(SR * FRAME_MS / 1000)

def my_function_to_get_audio_frame():
    audio = sd.rec(SAMPLES, samplerate=SR, channels=1, dtype='int16', blocking=True)
    return audio.flatten()

# One-time download of all pre-trained models (or only select models)
# openwakeword.utils.download_models()

# Instantiate the model(s)
model = Model(
    wakeword_models=["carson/Mister Carson Model.tflite"],  # can also leave this argument empty to load all of the included pre-trained models
)

# Get audio data containing 16-bit 16khz PCM audio data from a file, microphone, network stream, etc.
# For the best efficiency and latency, audio frames should be multiples of 80 ms, with longer frames
# increasing overall efficiency at the cost of detection latency
frame = my_function_to_get_audio_frame()

# Get predictions for the frame
prediction = model.predict(frame)