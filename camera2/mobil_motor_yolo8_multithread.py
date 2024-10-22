import cv2
import numpy as np
import time
import threading
from queue import Queue
from ultralytics import YOLO
import multiprocessing

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

def process_frame(model, input_queue, output_queue):
    while True:
        item = input_queue.get()
        if item is None:
            break
        frame, frame_id = item
        results = model(frame)
        output_queue.put((frame, results, frame_id))

# Initialize YOLOv8
model = YOLO('yolov8n.pt')

# Open video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8', cv2.CAP_FFMPEG)
video.set(cv2.CAP_PROP_BUFFERSIZE, 100)

# Target frame size
target_size = (640, 640)  # YOLOv8 default input size

# Initialize variables for vehicle counting
vehicle_counts = {
    'car': {'up': 0, 'down': 0},
    'motorcycle': {'up': 0, 'down': 0},
    'truck': {'up': 0, 'down': 0},
    'bus': {'up': 0, 'down': 0}
}

prev_centroids = {}
tracking_id = 0
crossed_ids = set()

# Line position (can be adjusted)
horizontal_line_position = 0.5

start_time = time.time()

# Initialize queues
frame_queue = Queue(maxsize=1)
process_queue = Queue(maxsize=1)
results_queue = Queue()

# Determine number of worker threads based on CPU count
num_workers = multiprocessing.cpu_count()
print(f"Using {num_workers} worker threads")

# Start frame reading thread
threading.Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()

# Start worker threads
workers = []
for _ in range(num_workers):
    worker = threading.Thread(target=process_frame, args=(model, process_queue, results_queue), daemon=True)
    worker.start()
    workers.append(worker)

processed_frame_count = 0
frame_id = 0
processing_times = []

# Vehicle class mapping
vehicle_classes = {
    'car': 'car',
    'motorcycle': 'motorcycle',
    'truck': 'truck',
    'bus': 'bus'
}

while True:
    if frame_queue.empty() and results_queue.empty():
        if video.get(cv2.CAP_PROP_POS_FRAMES) == video.get(cv2.CAP_PROP_FRAME_COUNT):
            break
        continue

    # Read a frame and send it for processing
    if not frame_queue.empty():
        frame = frame_queue.get()
        if frame is None:
            break
        process_queue.put((frame, frame_id))
        frame_id += 1

    # Display the frame immediately
    frame_display = cv2.resize(frame, target_size)
    height, width = frame_display.shape[:2]
    horizontal_line_y = int(height * horizontal_line_position)

    # Draw counting line
    cv2.line(frame_display, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), 2)

    # Process results if available
    if not results_queue.empty():
        _, results, _ = results_queue.get()
        processed_frame_count += 1

        current_centroids = {}

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = model.names[cls]
                
                # Check if detected object is one of our target vehicles
                if conf > 0.3 and class_name in ['car', 'motorcycle', 'truck', 'bus']:
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    centroid_x = (x1 + x2) // 2
                    centroid_y = (y1 + y2) // 2

                    # Simple tracking
                    min_distance = float('inf')
                    matched_id = None
                    for id, (prev_x, prev_y, prev_class) in prev_centroids.items():
                        distance = np.sqrt((centroid_x - prev_x)**2 + (centroid_y - prev_y)**2)
                        if distance < min_distance:
                            min_distance = distance
                            matched_id = id

                    if matched_id is None or min_distance > 50:  # Threshold for new ID
                        matched_id = tracking_id
                        tracking_id += 1

                    current_centroids[matched_id] = (centroid_x, centroid_y, class_name)

                    # Check for line crossing
                    if matched_id in prev_centroids and matched_id not in crossed_ids:
                        prev_y = prev_centroids[matched_id][1]
                        crossing = check_crossing(centroid_y, prev_y, horizontal_line_y)
                        if crossing != 0:
                            crossed_ids.add(matched_id)
                            if crossing == -1:  # Moving up
                                vehicle_counts[class_name]['up'] += 1
                            else:  # Moving down
                                vehicle_counts[class_name]['down'] += 1

                    # Draw bounding box and label
                    # cv2.rectangle(frame_display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    # label = f"{class_name}: {conf:.2f}"
                    # cv2.putText(frame_display, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Remove IDs that are no longer tracked
        crossed_ids = {id for id in crossed_ids if id in current_centroids}
        prev_centroids = current_centroids

    # Display counts
    y_position = 30
    for vehicle_type in vehicle_counts:
        count_text = f"{vehicle_type.capitalize()}: Up {vehicle_counts[vehicle_type]['up']} Down {vehicle_counts[vehicle_type]['down']}"
        cv2.putText(frame_display, count_text, (10, y_position), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        y_position += 30

    # Calculate and display FPS
    current_time = time.time()
    elapsed_time = current_time - start_time
    fps = frame_id / elapsed_time
    cv2.putText(frame_display, f"FPS: {fps:.2f}", (width - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("Vehicle Detection and Counting", frame_display)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Signal worker threads to stop
for _ in range(num_workers):
    process_queue.put(None)

# Wait for all worker threads to finish
for worker in workers:
    worker.join()

video.release()
cv2.destroyAllWindows()

# Print final statistics
print("\nFinal Vehicle Counts:")
for vehicle_type, counts in vehicle_counts.items():
    print(f"{vehicle_type.capitalize()}: Up {counts['up']}, Down {counts['down']}")
print(f"\nAverage FPS: {frame_id / (time.time() - start_time):.2f}")
print(f"Processed Frames: {processed_frame_count}")