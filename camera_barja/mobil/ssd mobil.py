import cv2
import numpy as np
import time

def get_centroid(box):
    return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)

def check_crossing(y, prev_y, line_y):
    if prev_y < line_y and y >= line_y:
        return 1  # Crossing downwards
    elif prev_y > line_y and y <= line_y:
        return -1  # Crossing upwards
    return 0  # No crossing

# Inisialisasi SSD
net = cv2.dnn.readNetFromCaffe('deploy.prototxt', 'mobilenet_iter_73000.caffemodel')

# Aktifkan CUDA jika tersedia
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

# Buka video
video = cv2.VideoCapture('cars.mp4')
# video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/atcs/ATCS_ukdw.stream/playlist.m3u8', cv2.CAP_FFMPEG)
# video.set(cv2.CAP_PROP_BUFFERSIZE, 3)

# Inisialisasi variabel
frame_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(video.get(cv2.CAP_PROP_FPS))

vehicles_in = 0
vehicles_out = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()

line_position = 0.6  # 60% dari tinggi frame
line_y = int(frame_height * line_position)

frame_count = 0
start_time = time.time()
processing_times = []

# Daftar ID kelas untuk kendaraan dalam model SSD
vehicle_classes = [3, 6, 8]  # 3: mobil, 6: bus, 8: truk

while True:
    ret, frame = video.read()
    if not ret:
        break

    frame_count += 1

    # Preprocess frame
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    
    # Deteksi objek
    process_start = time.time()
    net.setInput(blob)
    detections = net.forward()
    process_end = time.time()
    processing_times.append(process_end - process_start)

    current_centroids = {}

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:  # Threshold confidence
            class_id = int(detections[0, 0, i, 1])
            if class_id in vehicle_classes:
                box = detections[0, 0, i, 3:7] * np.array([frame_width, frame_height, frame_width, frame_height])
                (startX, startY, endX, endY) = box.astype("int")

                centroid = get_centroid((startX, startY, endX, endY))

                # Simple tracking
                min_distance = float('inf')
                matched_id = None
                for id, prev_centroid in prev_centroids.items():
                    distance = np.linalg.norm(np.array(centroid) - np.array(prev_centroid))
                    if distance < min_distance:
                        min_distance = distance
                        matched_id = id

                if matched_id is None or min_distance > 50:  # Threshold for new ID
                    matched_id = tracking_id
                    tracking_id += 1

                current_centroids[matched_id] = centroid

                # Check for line crossing
                if matched_id in prev_centroids and matched_id not in crossed_ids:
                    crossing = check_crossing(centroid[1], prev_centroids[matched_id][1], line_y)
                    if crossing == 1:
                        vehicles_in += 1
                        crossed_ids.add(matched_id)
                    elif crossing == -1:
                        vehicles_out += 1
                        crossed_ids.add(matched_id)

                # Draw bounding box
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
                cv2.putText(frame, f"ID: {matched_id}", (startX, startY - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Draw counting line
    cv2.line(frame, (0, line_y), (frame_width, line_y), (0, 0, 255), 2)

    # Display counts
    cv2.putText(frame, f"In: {vehicles_in} Out: {vehicles_out}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Calculate and display FPS
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("SSD Vehicle Detection and Counting", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Final count - In: {vehicles_in}, Out: {vehicles_out}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")