import cv2
import numpy as np
import time
import requests

def get_output_layers(net):
    return [net.getLayerNames()[i - 1] for i in net.getUnconnectedOutLayers()]

def draw_prediction(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    label = f"{classes[class_id]}: {confidence:.2f}"
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), (0, 255, 0), 2)
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

def point_in_polygon(x, y, polygon):
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# Initialize YOLO
net = cv2.dnn.readNet("yolov3-spp.weights", "yolov3-spp.cfg")
classes = open("coco.names").read().strip().split("\n")

# Open video stream
stream_url = "https://cctvjss.jogjakota.go.id/rthp/rthp_klitren_2.stream/playlist.m3u8"
cap = cv2.VideoCapture(stream_url)

# Target FPS and frame size
target_fps = 30
frame_interval = 10
target_size = (640, 480)

# Initialize variables for people counting
people_count = 0
prev_centroids = {}
tracking_id = 0

# Define the counting area (polygon)
counting_area = [(100, 0), (640, 0), (640, 380), (100, 380)]

frame_count = 0
start_time = time.time()
processing_times = []

while True:
    for _ in range(frame_interval):
        ret, frame = cap.read()
        if not ret:
            break
    
    if not ret:
        print("Error reading frame. Attempting to reconnect...")
        cap.release()
        cap = cv2.VideoCapture(stream_url)
        continue

    frame_count += 1

    # Resize frame
    frame = cv2.resize(frame, target_size)
    height, width = frame.shape[:2]

    # Draw counting area
    cv2.polylines(frame, [np.array(counting_area)], True, (0, 0, 255), 2)

    # Detect objects
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    
    process_start = time.time()
    outs = net.forward(get_output_layers(net))
    process_end = time.time()
    processing_times.append(process_end - process_start)

    # Initialize lists for detection results
    class_ids = []
    confidences = []
    boxes = []

    # Thresholds for detection
    conf_threshold = 0.4
    nms_threshold = 0.4

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > conf_threshold and classes[class_id] == "person":
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = center_x - w // 2
                y = center_y - h // 2
                class_ids.append(class_id)
                confidences.append(float(confidence))
                boxes.append([x, y, w, h])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

    current_centroids = {}
    current_count = 0
    for i in indices:
        i = i[0] if isinstance(i, (tuple, list)) else i
        box = boxes[i]
        x, y, w, h = box
        centroid_x = x + w // 2
        centroid_y = y + h // 2

        if point_in_polygon(centroid_x, centroid_y, counting_area):
            current_count += 1
            draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(x+w), round(y+h))

    people_count = current_count

    # Display count
    cv2.putText(frame, f"People in area: {people_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Calculate and display FPS
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Area-based People Counter", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

print(f"Final count: {people_count}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")