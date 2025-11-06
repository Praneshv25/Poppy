import mediapipe as mp
import cv2
import numpy as np
import time

from ServoController import ServoController

sc = ServoController()

# Initialize MediaPipe Face Detection (BlazeFace)
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

def get_face_detection():
    """Get a fresh face detection instance"""
    return mp_face_detection.FaceDetection(
        model_selection=0,  # 0 for short-range (2m), 1 for full-range (5m)
        min_detection_confidence=0.9
    )

def detect_faces(image, face_detection_instance):
    """
    Detect faces in an image using BlazeFace
    Returns: List of face detection results
    """
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Process the image
    results = face_detection_instance.process(rgb_image)
    
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
    Calculate the horizontal angle of the face relative to the center of the frame
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

def calculate_face_vertical_offset(face_center, image_shape, fov_degrees=60):
    """
    Calculate the vertical offset of the face relative to the center of the frame
    Args:
        face_center: (x, y) coordinates of face center
        image_shape: (height, width, channels) of the image
        fov_degrees: Field of view in degrees (default 60 for typical webcam)
    Returns:
        Vertical offset in degrees (negative = above center, positive = below center)
    """
    face_x, face_y = face_center
    h, w = image_shape[:2]
    
    # Calculate frame center
    frame_center_y = h // 2
    
    # Calculate offset from center (pixels)
    offset_y = face_y - frame_center_y
    
    # Calculate angle using field of view
    # Using vertical FOV (assuming similar to horizontal)
    angle_degrees = (offset_y / h) * fov_degrees
    
    return angle_degrees

def get_face_angle_from_frame(frame, face_detection_instance):
    """
    Get the angle of the first detected face in a frame
    Returns: Angle in degrees (negative = left, positive = right), or None if no face detected
    """
    detections = detect_faces(frame, face_detection_instance)
    if detections:
        center = get_face_center(detections[0], frame.shape)
        return calculate_face_angle(center, frame.shape)
    return None

def look_around():
    """
    Make the robot look around to search for faces
    Performs a sweep pattern: left -> right -> up -> down -> center
    """
    print("👀 Looking around for faces...")
    
    # Save current position
    initial_rotation = sc.rotation_stepper_deg
    initial_elevation = sc.elevation_servo_pos
    
    # Look left
    print("Looking left...")
    sc.move_left(30)
    time.sleep(0.5)
    
    # Look right (from left)
    print("Looking right...")
    sc.move_right(60)  # 60 degrees to go past center to the right
    time.sleep(0.5)
    
    # Return to center horizontally
    print("Returning to center...")
    sc.move_left(30)
    time.sleep(0.5)
    
    # Look up
    if sc.elevation_servo_pos < 90:
        print("Looking up...")
        target_up = min(sc.elevation_servo_pos + 15, 90)
        sc.set_elevation(target_up)
        time.sleep(0.5)
    
    # Look down
    if sc.elevation_servo_pos > 10:
        print("Looking down...")
        target_down = max(sc.elevation_servo_pos - 20, 10)
        sc.set_elevation(target_down)
        time.sleep(0.5)
    
    # Return to initial position
    print("Returning to initial position...")
    sc.set_elevation(initial_elevation)
    time.sleep(0.3)
    
    print("Look around complete!")


def run_face_detection(max_iterations=50, center_threshold=5):
    """
    Run real-time face detection and center on face
    Args:
        max_iterations: Maximum number of iterations before giving up
        center_threshold: Angular threshold in degrees to consider face "centered"
    """
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    print("BlazeFace Face Detection Started!")
    
    # Create a fresh face detection instance
    face_detection = get_face_detection()
    
    iterations = 0
    consecutive_centered = 0
    consecutive_no_face = 0
    required_consecutive = 3  # Need face centered for 3 consecutive frames
    no_face_threshold = 5  # Number of consecutive frames with no face before looking around
    face_centered_successfully = False
    
    try:
        while iterations < max_iterations and not face_centered_successfully:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break
            
            # Detect faces
            detections = detect_faces(frame, face_detection)
            
            # Draw detections
            frame = draw_face_detections(frame, detections)
            
            # Draw center line
            h, w = frame.shape[:2]
            center_x = w // 2
            cv2.line(frame, (center_x, 0), (center_x, h), (255, 0, 0), 2)  # Blue center line
            
            # Print face information and calculate angles
            if detections:
                consecutive_no_face = 0  # Reset no-face counter
                print(f"Detected {len(detections)} face(s)")
                for i, detection in enumerate(detections):
                    center = get_face_center(detection, frame.shape)
                    confidence = detection.score[0]
                    horizontal_angle = calculate_face_angle(center, frame.shape)
                    vertical_angle = calculate_face_vertical_offset(center, frame.shape)
                    
                    # Determine horizontal direction
                    if horizontal_angle < 0:
                        h_direction = f"{abs(horizontal_angle):.1f}° left"
                    elif horizontal_angle > 0:
                        h_direction = f"{horizontal_angle:.1f}° right"
                    else:
                        h_direction = "center"
                    
                    # Determine vertical direction
                    if vertical_angle < 0:
                        v_direction = f"{abs(vertical_angle):.1f}° up"
                    elif vertical_angle > 0:
                        v_direction = f"{vertical_angle:.1f}° down"
                    else:
                        v_direction = "center"
                    
                    print(f"Face {i+1}: Center={center}, Confidence={confidence:.3f}, H: {h_direction}, V: {v_direction}")
                    
                    # Draw angle text on frame
                    cv2.putText(frame, f"H: {h_direction}, V: {v_direction}", 
                               (center[0] - 80, center[1] + 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                    
                    # Check if face is centered (both horizontal and vertical)
                    h_centered = abs(horizontal_angle) <= center_threshold
                    v_centered = abs(vertical_angle) <= center_threshold
                    
                    if h_centered and v_centered:
                        consecutive_centered += 1
                        print("Face is centered")
                        if consecutive_centered >= required_consecutive:
                            print("✅ Face centered successfully! Exiting centering protocol.")
                            face_centered_successfully = True
                            break
                    else:
                        consecutive_centered = 0
                        moved = center_face(horizontal_angle, vertical_angle)
                        # If we couldn't move (hit limits), give up after a few tries
                        if not moved:
                            print("⚠️ Cannot center - hit movement limits. Proceeding anyway.")
                            break
                        else:
                            # Wait for motors to complete movement before next check
                            time.sleep(1.5)
            else:
                print("No faces detected")
                consecutive_centered = 0
                consecutive_no_face += 1
                
                # If no face detected for several consecutive frames, look around
                if consecutive_no_face >= no_face_threshold:
                    print(f"No face detected for {consecutive_no_face} frames. Looking around...")
                    look_around()
                    consecutive_no_face = 0  # Reset counter after looking around
                    # Continue searching after looking around
                    time.sleep(0.5)
            
            # Display frame
            # cv2.imshow('BlazeFace Face Detection', frame)
            
            # Check for 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            iterations += 1
    finally:
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        face_detection.close()
        print("Face detection completed")


def center_face(horizontal_angle, vertical_angle):
    """
    Center the face by moving the robot horizontally and vertically
    Args:
        horizontal_angle: Angle in degrees (negative = left, positive = right)
        vertical_angle: Angle in degrees (negative = above center, positive = below center)
    Returns:
        bool: True if any movement was made, False if hit limits
    """
    threshold = 2
    moved = False
    
    # Horizontal movement (left/right) - uses degrees directly, max 20 degrees
    # Stepper motor - RELATIVE movement (unchanged)
    horizontal_move_degrees = min(abs(horizontal_angle), 20)  # Clamp to max 20 degrees
    
    if horizontal_angle < 0 and abs(horizontal_angle) > threshold:
        success = sc.move_left(horizontal_move_degrees)
        print(f"Moving left by {abs(horizontal_angle):.1f}° (clamped to {horizontal_move_degrees:.1f}°)")
        moved = moved or success
    elif horizontal_angle > 0 and abs(horizontal_angle) > threshold:
        success = sc.move_right(horizontal_move_degrees)
        print(f"Moving right by {abs(horizontal_angle):.1f}° (clamped to {horizontal_move_degrees:.1f}°)")
        moved = moved or success
    
    # Vertical movement (up/down) - ABSOLUTE servo positioning
    # Convert angle to servo position change (1 degree = 1 servo unit, max 20 servo units)
    vertical_servo_delta = min(abs(vertical_angle), 5)  # Clamp to max 20 servo units
    
    if abs(vertical_angle) > threshold:
        # Get current elevation position
        current_elevation = sc.elevation_servo_pos
        
        if vertical_angle < 0:
            # Face is above center, move elevation up (higher value)
            target_elevation = min(current_elevation + vertical_servo_delta, 100)
            success = sc.set_elevation(target_elevation)
            print(f"Moving up: {current_elevation} → {target_elevation}")
            moved = moved or success
        elif vertical_angle > 0:
            # Face is below center, move elevation down (lower value)
            target_elevation = max(current_elevation - vertical_servo_delta, 0)
            success = sc.set_elevation(target_elevation)
            print(f"Moving down: {current_elevation} → {target_elevation}")
            moved = moved or success
    
    return moved


# if __name__ == "__main__":
#     run_face_detection()
