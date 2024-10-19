import cv2
import numpy as np
import time
import threading
from queue import Queue
from ultralytics import YOLO

def check_crossing(y, prev_y, line_y):
    if prev_y < line_y and y >= line_y:
        return 1  # Crossing downwards
    elif prev_y > line_y and y <= line_y:
        return -1  # Crossing upwards
    return 0  # No crossing

def read_frames(video, frame_queue):
    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_queue.put(frame)
    frame_queue.put(None)  # Signal end of video

# Initialize YOLOv8
model = YOLO('yolov8n.pt')  # or 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt' depending on your needs

# Open video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8', cv2.CAP_FFMPEG)
video.set(cv2.CAP_PROP_BUFFERSIZE, 10)

# Target FPS and frame size
target_fps = 30
frame_interval = 5
target_size = (320, 320)  # YOLOv8 default input size

# Initialize variables for car counting
cars_left = 0
cars_right = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()

# Line positions (can be adjusted)
horizontal_line_position = 0.5
vertical_line_position = 0.5

frame_count = 0
start_time = time.time()
processing_times = []

# Initialize frame queue
frame_queue = Queue(maxsize=5)
threading.Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()

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
    vertical_line_x = int(width * vertical_line_position)

    # Draw counting lines
    cv2.line(frame, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), 2)
    cv2.line(frame, (vertical_line_x, 0), (vertical_line_x, height), (255, 0, 0), 2)

    # Detect objects
    process_start = time.time()
    results = model(frame)
    process_end = time.time()
    processing_times.append(process_end - process_start)

    current_centroids = {}

    for r in results:
        boxes = r.boxes
        for box in boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if conf > 0.3 and model.names[cls] in ["car", "truck", "bus"]:
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                
                centroid_x = (x1 + x2) // 2
                centroid_y = (y1 + y2) // 2

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
                        if centroid_x < vertical_line_x:
                            cars_left += 1
                        else:
                            cars_right += 1

                # Draw bounding box and label
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{model.names[cls]}: {conf:.2f}"
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts and FPS every 5 frames
    if frame_count % 5 == 0:
        # Display counts
        cv2.putText(frame, f"Left: {cars_left} Right: {cars_right}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Calculate and display FPS
        elapsed_time = time.time() - start_time
        fps = frame_count / elapsed_time
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow("Car Detection and Counting", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Final count - Left: {cars_left}, Right: {cars_right}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")