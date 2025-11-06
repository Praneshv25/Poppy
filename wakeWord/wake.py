from openwakeword.model import Model
import sounddevice as sd
import time
import os
import asyncio
import queue
import threading
from dotenv import load_dotenv
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV2SocketClientResponse
import humanCentering

load_dotenv()

SR = 16000
FRAME_MS = 80
SAMPLES = int(SR * FRAME_MS / 100)

def my_function_to_get_audio_frame():
    audio = sd.rec(SAMPLES, samplerate=SR, channels=1, dtype='int16', blocking=True)
    return audio.flatten()

# One-time download of all pre-trained models (or only select models)
# openwakeword.utils.download_models()

# Instantiate the model(s)
model = Model(
    wakeword_models=["wakeWord/heimdell/Heimdell Model.onnx"],  # can also leave this argument empty to load all of the included pre-trained models
)

THRESHOLD = 0.01
COOLDOWN_SEC = 1.5
last_triggered_ts = 0.0

def listen_for_wake_word():
    global last_triggered_ts
    start = time.time()

    try:
        while True:
            frame = my_function_to_get_audio_frame()
            scores = model.predict(frame)
            now = time.time()

            # Iterate over model scores; trigger when threshold exceeded and cooldown elapsed
            print(time.time() - start, scores)
            for name, score in scores.items():
                if score >= THRESHOLD and (now - last_triggered_ts) >= COOLDOWN_SEC:
                    humanCentering.run_face_detection(max_iterations=30)
                    print(f"[wake] {name}: {score:.2f}")
                    print("Waiting for motors to settle before recording...")
                    time.sleep(0.125)  # Wait for motors to settle and noise to dissipate
                    last_triggered_ts = now
                    return asyncio.run(transcribe_audio())
    except KeyboardInterrupt:
        raise


client = AsyncDeepgramClient()

# Transcription settings
TRANSCRIBE_DURATION = 5  # seconds to record after wake word
BLOCK_SIZE = 1600  # ~100ms at 16kHz

def audio_callback(audio_q: queue.Queue):
    """Returns a callback function that pushes audio to the given queue."""
    def callback(indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")
        audio_q.put(bytes(indata))
    return callback

async def transcribe_audio():
    """Stream microphone audio to Deepgram for transcription after wake word detected."""
    try:
        async with client.listen.v2.connect(
            model="flux-general-en",
            encoding="linear16",
            sample_rate=16000  # Integer, not string
        ) as connection:
            transcript = ""
            done = asyncio.Event()
            
            def on_message(message: ListenV2SocketClientResponse) -> None:
                nonlocal transcript
                # Check for Flux EndOfTurn events (final transcripts)
                if hasattr(message, 'type') and message.type == 'TurnInfo':
                    if hasattr(message, 'event') and message.event == 'EndOfTurn':
                        if hasattr(message, 'transcript') and message.transcript:
                            text = message.transcript.strip()
                            print(f"🎤 [FINAL] {text}")
                            # Append to transcript instead of overwriting
                            if transcript:
                                transcript += " " + text
                            else:
                                transcript = text
                elif hasattr(message, 'type') and message.type == 'Connected':
                    print("✅ Connected to Deepgram - listening...")

            connection.on(EventType.MESSAGE, on_message)

            # Start websocket listener as async task
            listener_task = asyncio.create_task(connection.start_listening())

            # Queue to bridge sync callback to async loop
            audio_q: queue.Queue[bytes] = queue.Queue()

            # Start microphone stream
            with sd.RawInputStream(
                samplerate=SR,
                channels=1,
                dtype='int16',
                blocksize=BLOCK_SIZE,
                callback=audio_callback(audio_q),
            ):
                print(f"Recording for {TRANSCRIBE_DURATION} seconds...")
                end_time = time.time() + TRANSCRIBE_DURATION

                while time.time() < end_time:
                    try:
                        chunk = audio_q.get(timeout=0.1)
                        # Send audio data to Deepgram
                        await connection._send(chunk)
                    except queue.Empty:
                        continue

                print("Recording complete.")
            
            # Wait a bit for final messages to arrive
            await asyncio.sleep(1.0)
            
            if not transcript:
                print("❌ No transcript received")
                return None
            
            return transcript

    except Exception as e:
        print(f"Transcription error: {e}")
        return None


# if __name__ == "__main__":
#     # Test transcription directly
#     print("Testing transcription (will record for 10 seconds)...")
#     result = asyncio.run(transcribe_audio())
#     print(f"\nFinal transcript: {result}")
    
#     Uncomment below to use wake word detection instead:
#     print("Listening for wake word...")
# while True:
#     listen_for_wake_word()
