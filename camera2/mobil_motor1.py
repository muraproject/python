import torch
import cv2
import numpy as np
import time
from pathlib import Path
from threading import Thread
from queue import Queue

# Load YOLOv5 model
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')  # or yolov5m, yolov5l, yolov5x
model.conf = 0.25  # NMS confidence threshold
model.iou = 0.45  # NMS IoU threshold
model.classes = [0, 2]  # Filter classes: 0 for person, 2 for car

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

# Open video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8')
video.set(cv2.CAP_PROP_BUFFERSIZE, 3)

# Target FPS and frame size
target_fps = 30
frame_interval = 10
target_size = (320, 320)  # YOLOv5 default input size

# Initialize variables for counting
car_count = 0
person_count = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()

# Line position (can be adjusted)
horizontal_line_position = 0.5

frame_count = 0
start_time = time.time()
processing_times = []

# Initialize queue for frames
frame_queue = Queue(maxsize=5)
Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()

while True:
    frame = frame_queue.get()
    if frame is None:
        break

    frame_count += 1
    if frame_count % frame_interval != 0:
        continue

    # Resize frame
    frame = cv2.resize(frame, target_size)
    height, width = frame.shape[:2]
    horizontal_line_y = int(height * horizontal_line_position)

    # Draw counting line with thickness 2
    cv2.line(frame, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), 2)

    # Object detection
    process_start = time.time()
    results = model(frame)
    process_end = time.time()
    processing_times.append(process_end - process_start)

    current_centroids = {}
    for *xyxy, conf, cls in results.xyxy[0]:  # xyxy are the bounding box coordinates
        x1, y1, x2, y2 = map(int, xyxy)
        centroid_x = (x1 + x2) // 2
        centroid_y = (y1 + y2) // 2
        class_id = int(cls)

        # Simple tracking
        min_distance = float('inf')
        matched_id = None
        for id, (prev_x, prev_y) in prev_centroids.items():
            distance = np.sqrt((centroid_x - prev_x)**2 + (centroid_y - prev_y)**2)
            if distance < min_distance:
                min_distance = distance
                matched_id = id

        if matched_id is None or min_distance > 50:  # Threshold for new ID
            matched_id = tracking_id
            tracking_id += 1

        current_centroids[matched_id] = (centroid_x, centroid_y)

        # Check for line crossing
        if matched_id in prev_centroids and matched_id not in crossed_ids:
            prev_y = prev_centroids[matched_id][1]
            crossing = check_crossing(centroid_y, prev_y, horizontal_line_y)
            if crossing != 0:
                crossed_ids.add(matched_id)
                if class_id == 2:  # Car
                    car_count += 1
                elif class_id == 0:  # Person
                    person_count += 1

        # Draw bounding box
        label = f"{model.names[class_id]} {conf:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts and FPS every 5 frames
    if frame_count % 5 == 0:
        # Display counts
        cv2.putText(frame, f"Cars: {car_count} People: {person_count}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Calculate and display FPS
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