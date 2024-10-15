import torch
import cv2
import numpy as np
import time
from pathlib import Path
from threading import Thread
from queue import Queue
from collections import deque

# Load YOLOv5 model
model = torch.hub.load('ultralytics/yolov5', 'yolov5n')
model.conf = 0.25
model.iou = 0.45
model.classes = [0, 2]  # 0 for person, 2 for car

# Set device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

def read_frames(video, frame_queue):
    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_queue.put(frame)
    frame_queue.put(None)  # Signal end of video

def check_crossing(y, prev_y, line_y):
    if prev_y < line_y and y >= line_y:
        return 1  # Crossing downwards
    elif prev_y > line_y and y <= line_y:
        return -1  # Crossing upwards
    return 0  # No crossing

# Generate unique colors
def generate_colors(n):
    return [(int(h), int(s), int(v)) for h, s, v in [
        (i * 137.508, 75, 75) for i in range(n)
    ]]

# Open video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8')
video.set(cv2.CAP_PROP_BUFFERSIZE, 3)

# Target FPS and frame size
target_fps = 30
frame_interval = 3
target_size = (320, 320)

# Initialize variables for counting
car_count = 0
person_count = 0
tracking_objects = {}
tracking_id = 0
crossed_ids = set()

# Line position
horizontal_line_position = 0.5

# Color assignment
color_list = generate_colors(100)  # Generate 100 unique colors
color_assignment = {}

frame_count = 0
start_time = time.time()
processing_times = []

# Initialize queue for frames
frame_queue = Queue(maxsize=5)
Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()

# Assume traffic direction is from top to bottom
traffic_direction = 1  # 1 for downward, -1 for upward

while True:
    frame = frame_queue.get()
    if frame is None:
        break

    frame_count += 1
    if frame_count % frame_interval != 0:
        continue

    frame = cv2.resize(frame, target_size)
    height, width = frame.shape[:2]
    horizontal_line_y = int(height * horizontal_line_position)

    cv2.line(frame, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), 2)

    process_start = time.time()
    results = model(frame)
    process_end = time.time()
    processing_times.append(process_end - process_start)

    current_objects = {}
    for *xyxy, conf, cls in results.xyxy[0]:
        x1, y1, x2, y2 = map(int, xyxy)
        centroid_x = (x1 + x2) // 2
        centroid_y = (y1 + y2) // 2
        class_id = int(cls)

        # Find the closest existing object in the direction of traffic
        min_distance = float('inf')
        matched_id = None
        for obj_id, obj in tracking_objects.items():
            if obj['class_id'] == class_id:
                distance = np.sqrt((centroid_x - obj['centroid'][0])**2 + (centroid_y - obj['centroid'][1])**2)
                # Check if the object is in the expected direction
                if (traffic_direction == 1 and centroid_y > obj['centroid'][1]) or \
                   (traffic_direction == -1 and centroid_y < obj['centroid'][1]):
                    if distance < min_distance and distance < 50:  # Distance threshold
                        min_distance = distance
                        matched_id = obj_id

        if matched_id is None:
            # New object detected
            matched_id = tracking_id
            tracking_id += 1
            color_assignment[matched_id] = color_list[matched_id % len(color_list)]

        # Update or create object
        current_objects[matched_id] = {
            'centroid': (centroid_x, centroid_y),
            'bbox': (x1, y1, x2, y2),
            'class_id': class_id,
            'last_seen': frame_count,
            'trajectory': deque(maxlen=20)  # Store last 20 positions
        }
        current_objects[matched_id]['trajectory'].append((centroid_x, centroid_y))

        # Check for line crossing
        if matched_id in tracking_objects:
            prev_y = tracking_objects[matched_id]['centroid'][1]
            crossing = check_crossing(centroid_y, prev_y, horizontal_line_y)
            if crossing != 0 and matched_id not in crossed_ids:
                crossed_ids.add(matched_id)
                if class_id == 2:  # Car
                    car_count += 1
                elif class_id == 0:  # Person
                    person_count += 1

        # Draw bounding box with consistent color
        color = color_assignment[matched_id]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{model.names[class_id]} {conf:.2f}"
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw trajectory
        if len(current_objects[matched_id]['trajectory']) > 1:
            for i in range(1, len(current_objects[matched_id]['trajectory'])):
                if i % 2 == 0:  # Draw every other point to reduce clutter
                    cv2.line(frame, current_objects[matched_id]['trajectory'][i - 1], 
                             current_objects[matched_id]['trajectory'][i], color, 2)

    # Update tracking_objects and remove old objects
    tracking_objects = current_objects
    for obj_id in list(tracking_objects.keys()):
        if frame_count - tracking_objects[obj_id]['last_seen'] > 30:  # Remove if not seen for 30 frames
            del tracking_objects[obj_id]

    # Display counts and FPS
    cv2.putText(frame, f"Cars: {car_count} People: {person_count}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    cv2.imshow("Car and Person Detection and Counting", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Final count - Cars: {car_count}, People: {person_count}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")