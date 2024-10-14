import cv2
import numpy as np
import time

def get_output_layers(net):
    return [net.getLayerNames()[i - 1] for i in net.getUnconnectedOutLayers()]

def draw_prediction(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    label = f"{classes[class_id]}: {confidence:.2f}"
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), (0, 255, 0), 2)
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

def check_crossing(y, prev_y, line_y):
    if prev_y < line_y and y >= line_y:
        return 1  # Crossing downwards
    elif prev_y > line_y and y <= line_y:
        return -1  # Crossing upwards
    return 0  # No crossing

# Inisialisasi YOLO
net = cv2.dnn.readNet("yolov3-spp.weights", "yolov3-spp.cfg")
classes = open("coco.names").read().strip().split("\n")

# Buka video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/atcs/ATCS_ukdw.stream/playlist.m3u8')  # Ganti dengan nama file video lalu lintas Anda

# Target FPS dan ukuran frame
target_fps = 30
frame_interval = 1
target_size = (800, 800)

# Inisialisasi variabel untuk car counting
cars_left = 0
cars_right = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()

# Posisi garis (bisa disesuaikan)
horizontal_line_position = 0.5  # 60% dari tinggi frame
vertical_line_position = 0.5  # 50% dari lebar frame

frame_count = 0
start_time = time.time()
processing_times = []

while True:
    for _ in range(frame_interval):
        ret, frame = video.read()
        if not ret:
            break
    
    if not ret:
        break

    frame_count += 1

    # Resize frame
    frame = cv2.resize(frame, target_size)
    height, width = frame.shape[:2]
    horizontal_line_y = int(height * horizontal_line_position)
    vertical_line_x = int(width * vertical_line_position)

    # Draw counting line (horizontal) and left-right boundary (vertical)
    cv2.line(frame, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), 2)
    cv2.line(frame, (vertical_line_x, 0), (vertical_line_x, height), (255, 0, 0), 2)

    # Deteksi objek
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
    conf_threshold = 0.5
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

        draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(x+w), round(y+h))

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts
    cv2.putText(frame, f"Left: {cars_left} Right: {cars_right}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Hitung dan tampilkan FPS
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