import os
import numpy as np
import speech_recognition as sr
import whisper
import torch

from datetime import datetime, timedelta
from queue import Queue
from time import sleep


def run_whisper_live_transcription(
        model_name="tiny",
        non_english=False,
        energy_threshold=1000,
        record_timeout=2.0,
        phrase_timeout=3.0,
        silence_timeout=5.0  # NEW: stop after this many seconds of silence
):
    from datetime import datetime, timedelta
    import os
    import numpy as np
    import speech_recognition as sr
    import whisper
    import torch
    from queue import Queue
    from time import sleep

    phrase_time = None
    data_queue = Queue()
    phrase_bytes = bytes()
    recorder = sr.Recognizer()
    recorder.energy_threshold = energy_threshold
    recorder.dynamic_energy_threshold = False

    source = sr.Microphone(sample_rate=16000)

    # Load Whisper model
    model = model_name
    if model != "large" and not non_english:
        model += ".en"
    audio_model = whisper.load_model(model)

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio: sr.AudioData) -> None:
        data = audio.get_raw_data()
        data_queue.put(data)

    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)
    print("Model loaded. Listening...\n")

    try:
        while True:
            now = datetime.utcnow()

            # If silence has lasted too long, break
            if phrase_time and now - phrase_time > timedelta(seconds=silence_timeout):
                print("\nSilence timeout reached.")
                return transcription

            if not data_queue.empty():
                phrase_complete = False
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    phrase_bytes = bytes()
                    phrase_complete = True
                phrase_time = now

                audio_data = b''.join(data_queue.queue)
                data_queue.queue.clear()
                phrase_bytes += audio_data

                audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                text = result['text'].strip()

                if phrase_complete:
                    transcription.append(text)
                else:
                    transcription[-1] = text

                os.system('cls' if os.name == 'nt' else 'clear')
                for line in transcription:
                    print(line)
                print('', end='', flush=True)
            else:
                sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopped by user.")

    return transcription
