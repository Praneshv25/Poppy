import mediapipe as mp
import cv2
import numpy as np

import ServoController as sc

# Initialize MediaPipe Face Detection (BlazeFace)
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

# Initialize face detection
face_detection = mp_face_detection.FaceDetection(
    model_selection=0,  # 0 for short-range (2m), 1 for full-range (5m)
    min_detection_confidence=0.9
)

def detect_faces(image):
    """
    Detect faces in an image using BlazeFace
    Returns: List of face detection results
    """
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Process the image
    results = face_detection.process(rgb_image)
    
    return results.detections if results.detections else []

def draw_face_detections(image, detections):
    """
    Draw bounding boxes around detected faces
    """
    if detections:
        for detection in detections:
            # Get bounding box
            bbox = detection.location_data.relative_bounding_box
            h, w, _ = image.shape
            
            # Convert relative coordinates to absolute
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)
            
            # Draw rectangle
            cv2.rectangle(image, (x, y), (x + width, y + height), (0, 255, 0), 2)
            
            # Draw confidence score
            confidence = detection.score[0]
            cv2.putText(image, f'Face: {confidence:.2f}', 
                       (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    return image

def get_face_center(detection, image_shape):
    """
    Get the center point of a detected face
    """
    bbox = detection.location_data.relative_bounding_box
    h, w = image_shape[:2]
    
    # Calculate center coordinates
    center_x = int((bbox.xmin + bbox.width/2) * w)
    center_y = int((bbox.ymin + bbox.height/2) * h)
    
    return (center_x, center_y)

def calculate_face_angle(face_center, image_shape, fov_degrees=60):
    """
    Calculate the angle of the face relative to the center of the frame
    Args:
        face_center: (x, y) coordinates of face center
        image_shape: (height, width, channels) of the image
        fov_degrees: Field of view in degrees (default 60 for typical webcam)
    Returns:
        Angle in degrees (negative = left, positive = right)
    """
    face_x, face_y = face_center
    h, w = image_shape[:2]
    
    # Calculate frame center
    frame_center_x = w // 2
    
    # Calculate offset from center (pixels)
    offset_x = face_x - frame_center_x
    
    # Calculate angle using field of view
    # Assuming the webcam has a 60-degree horizontal FOV
    angle_degrees = (offset_x / w) * fov_degrees
    
    return angle_degrees

def get_face_angle_from_frame(frame):
    """
    Get the angle of the first detected face in a frame
    Returns: Angle in degrees (negative = left, positive = right), or None if no face detected
    """
    detections = detect_faces(frame)
    if detections:
        center = get_face_center(detections[0], frame.shape)
        return calculate_face_angle(center, frame.shape)
    return None

def run_face_detection():
    """
    Run real-time face detection using webcam
    """
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    print("BlazeFace Face Detection Started!")
    print("Press 'q' to quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Flip frame horizontally for mirror effect
        # frame = cv2.flip(frame, 1) 
        
        # Detect faces
        detections = detect_faces(frame)
        
        # Draw detections
        frame = draw_face_detections(frame, detections)
        
        # Draw center line
        h, w = frame.shape[:2]
        center_x = w // 2
        cv2.line(frame, (center_x, 0), (center_x, h), (255, 0, 0), 2)  # Blue center line
        
        # Print face information and calculate angles
        if detections:
            print(f"Detected {len(detections)} face(s)")
            for i, detection in enumerate(detections):
                center = get_face_center(detection, frame.shape)
                confidence = detection.score[0]
                angle = calculate_face_angle(center, frame.shape)
                
                # Determine direction
                if angle < 0:
                    direction = f"{abs(angle):.1f}° left"
                elif angle > 0:
                    direction = f"{angle:.1f}° right"
                else:
                    direction = "center"
                
                print(f"Face {i+1}: Center={center}, Confidence={confidence:.3f}, Angle: {direction}")
                
                # Draw angle text on frame
                cv2.putText(frame, f"Angle: {direction}", 
                           (center[0] - 50, center[1] + 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            print("No faces detected")
        
        # Display frame
        cv2.imshow('BlazeFace Face Detection', frame)
        
        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    face_detection.close()


def center_face(angle):
    threshold = 10
    if angle < 0 and abs(angle) > threshold:
        sc.move_stepper("left", abs(angle))
    elif angle > 0 and abs(angle) > threshold:
        sc.move_stepper("right", abs(angle))
    else:
        print("Face is centered")


if __name__ == "__main__":
    run_face_detection()
