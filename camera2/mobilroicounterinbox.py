import cv2
import numpy as np
import time
import threading
from queue import Queue

def get_output_layers(net):
    return [net.getLayerNames()[i - 1] for i in net.getUnconnectedOutLayers()]

def draw_prediction(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    label = f"{classes[class_id]}: {confidence:.2f}"
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), (0, 255, 0), 2)
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

def read_frames(video, frame_queue):
    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_queue.put(frame)
    frame_queue.put(None)  # Signal end of video

# Inisialisasi YOLO
net = cv2.dnn.readNet("yolov3-spp.weights", "yolov3-spp.cfg")
classes = open("coco.names").read().strip().split("\n")

# Coba aktifkan CUDA jika tersedia
try:
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    print("CUDA activated")
except:
    print("CUDA not available, using CPU")

# Buka video
video = cv2.VideoCapture('cctv.mp4')
video.set(cv2.CAP_PROP_BUFFERSIZE, 3)

# Target FPS dan ukuran frame
target_fps = 30
frame_interval = 5
target_size = (320, 320)

# Inisialisasi variabel untuk car counting
total_cars = 0
prev_centroids = {}
tracking_id = 0
counted_ids = set()

# Definisikan Region of Interest (ROI)
roi_top = 0.7
roi_bottom = 0.8
roi_left = 0.1
roi_right = 0.8

frame_count = 0
start_time = time.time()
processing_times = []

# Inisialisasi queue untuk frame
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
    
    # Definisikan ROI
    roi_y_start = int(height * roi_top)
    roi_y_end = int(height * roi_bottom)
    roi_x_start = int(width * roi_left)
    roi_x_end = int(width * roi_right)
    
    # Gambar ROI pada frame
    cv2.rectangle(frame, (roi_x_start, roi_y_start), (roi_x_end, roi_y_end), (255, 0, 0), 2)

    # Deteksi objek pada frame penuh
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, target_size, swapRB=True, crop=False)
    net.setInput(blob)
    
    process_start = time.time()
    outs = net.forward(get_output_layers(net))
    process_end = time.time()
    processing_times.append(process_end - process_start)

    # Inisialisasi list untuk hasil deteksi
    class_ids = []
    confidences = []
    boxes = []

    # Threshold untuk deteksi
    conf_threshold = 0.3
    nms_threshold = 0.4

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > conf_threshold and classes[class_id] in ["car", "truck", "bus"]:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = center_x - w // 2
                y = center_y - h // 2
                
                # Check if detection is within ROI
                if (roi_x_start <= x <= roi_x_end or roi_x_start <= x + w <= roi_x_end) and \
                   (roi_y_start <= y <= roi_y_end or roi_y_start <= y + h <= roi_y_end):
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([x, y, w, h])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

    current_centroids = {}
    for i in indices:
        i = i[0] if isinstance(i, (tuple, list)) else i
        box = boxes[i]
        x, y, w, h = box
        centroid_x = x + w // 2
        centroid_y = y + h // 2

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

        # Count car if it's not been counted before
        if matched_id not in counted_ids:
            total_cars += 1
            counted_ids.add(matched_id)

        draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(x+w), round(y+h))

    # Remove IDs that are no longer tracked
    counted_ids = {id for id in counted_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts and FPS every 5 frames
    if frame_count % 5 == 0:
        # Display total count
        cv2.putText(frame, f"Total Cars: {total_cars}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Hitung dan tampilkan FPS
        elapsed_time = time.time() - start_time
        fps = frame_count / elapsed_time
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow("Car Detection and Counting", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Final count - Total Cars: {total_cars}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")