import torch
import open_clip
from PIL import Image
import torchvision.transforms as T

import cv2

cap = cv2.VideoCapture(0)  # 0 for default webcam


def getVision():
    ret, frame = cap.read()
    if not ret:
        return None


    cap.release()
    cv2.destroyAllWindows()

    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
    tokenizer = open_clip.get_tokenizer('ViT-B-32')

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    image_input = preprocess(image).unsqueeze(0)

    with torch.no_grad():
        image_features = model.encode_image(image_input)
        print(image_features)

getVision()
