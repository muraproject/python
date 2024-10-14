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

# Inisialisasi YOLO dengan CUDA
net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
classes = open("coco.names").read().strip().split("\n")

# Buka video
video = cv2.VideoCapture('jalan.mp4')

# Target FPS dan ukuran frame
target_fps = 30
frame_interval = 10
target_size = (320, 320)

# Inisialisasi variabel untuk people counting
people_in = 0
people_out = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()  # Set untuk menyimpan ID yang sudah melintasi garis

# Posisi garis (bisa disesuaikan)
line_position = 0.6  # 60% dari tinggi frame

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
    line_y = int(height * line_position)

    # Draw counting line
    cv2.line(frame, (0, line_y), (width, line_y), (0, 0, 255), 2)

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
    for i in indices:
        i = i[0] if isinstance(i, (tuple, list)) else i
        box = boxes[i]
        x, y, w, h = box
        centroid_y = y + h // 2

        # Simple tracking
        min_distance = float('inf')
        matched_id = None
        for id, prev_y in prev_centroids.items():
            distance = abs(centroid_y - prev_y)
            if distance < min_distance:
                min_distance = distance
                matched_id = id

        if matched_id is None or min_distance > 50:  # Threshold for new ID
            matched_id = tracking_id
            tracking_id += 1

        current_centroids[matched_id] = centroid_y

        # Check for line crossing
        if matched_id in prev_centroids and matched_id not in crossed_ids:
            crossing = check_crossing(centroid_y, prev_centroids[matched_id], line_y)
            if crossing == 1:
                people_in += 1
                crossed_ids.add(matched_id)
            elif crossing == -1:
                people_out += 1
                crossed_ids.add(matched_id)

        draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(x+w), round(y+h))

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts
    cv2.putText(frame, f"In: {people_in} Out: {people_out}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Hitung dan tampilkan FPS
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("Human Detection and Counting", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Final count - In: {people_in}, Out: {people_out}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")