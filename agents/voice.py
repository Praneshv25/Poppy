from elevenlabs.client import ElevenLabs
from elevenlabs import stream
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

elevenlabs = ElevenLabs(
  api_key=os.getenv("ELEVENLABS_API_KEY"),
)


def stream_audio(text):
    audio_stream = elevenlabs.text_to_speech.stream(
        text=text,
        voice_id="LcfcDJNUP1GQjkzn1xUU", # Emily
        model_id="eleven_flash_v2",
        optimize_streaming_latency=2,
        voice_settings={"speed": 1.2, "stability": 0.3}
    )

    stream(audio_stream)

