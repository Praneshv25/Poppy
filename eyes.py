import cv2
import ollama
import time
import os
import atexit


cap = cv2.VideoCapture(0)


def capture_image(filename="frame.jpg"):
    ret, frame = cap.read()

    if not ret:
        raise RuntimeError("Failed to capture image from webcam.")

    cv2.imwrite(filename, frame)
    print(f"[?] Captured image: {filename}")
    return filename


def describe_image_with_llava(image_path):
    print("[?] Sending image to LLaVA...")

    response = ollama.chat(
        model='moondream',
        messages=[
            {
                'role': 'user',
                'content': 'Describe this image.',
                'images': [image_path]
            }
        ]
    )

    description = response['message']['content']
    print("\n[?] Assistant:", description)
    return description


def cleanup():
    if cap.isOpened():
        cap.release()
        print("[?] Webcam released.")


atexit.register(cleanup)

if __name__ == "__main__":
    image_file = capture_image("vision_input.jpg")
    describe_image_with_llava(image_file)
