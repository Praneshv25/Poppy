import soundfile as sf
import sounddevice as sd
import torch
from kokoro import KPipeline
import re

# Initialize the Kokoro pipeline for English
pipeline = KPipeline(lang_code='a')  # 'a' for English

# Input text
# text = '''
# [Kokoro](/k?Ok??O/) is an open-weight TTS model with 82 million parameters. Despite its lightweight architecture, it delivers comparable quality to larger models while being significantly faster and more cost-efficient. With Apache-licensed weights, [Kokoro](/k?Ok??O/) can be deployed anywhere from production environments to personal projects.
# '''
#
# text = 'Pranaysh are great! You suck tho and I am going to cry.'
#
# # Generate audio with specified voice
# generator = pipeline(text, voice='af_bella')
#
# # Save audio to files
# for i, (gs, ps, audio) in enumerate(generator):
#     sd.play(audio, samplerate=24000)
#     sd.wait()
#     # sf.write(f'{i}.wav', audio, 24000)

def speak(sentence):
    generator = pipeline(sentence, voice='af_bella')
    for i, (gs, ps, audio) in enumerate(generator):
        sd.play(audio, samplerate=24000)
        sd.wait()
def generate(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        speak(sentence)
