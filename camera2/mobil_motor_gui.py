import cv2
import numpy as np
import time
import threading
from queue import Queue
import json

# Initialize global variables
horizontal_line_position = 0.5
vertical_line_position = 0.5
contrast = 1.0
brightness = 0
hue = 0
saturation = 1.0
conf_threshold = 0.2
nms_threshold = 0.4
min_object_size = 0.01
max_object_size = 0.8
blur_amount = 0
sharpness = 0
gamma = 1.0
line_thickness = 2
frame_interval = 5

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

def read_frames(video, frame_queue):
    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_queue.put(frame)
    frame_queue.put(None)  # Signal end of video

# Calibration function
def update_calibration(x):
    global horizontal_line_position, vertical_line_position, contrast, brightness, hue, saturation, conf_threshold, nms_threshold, min_object_size, max_object_size, blur_amount, sharpness, gamma, line_thickness, frame_interval
    horizontal_line_position = cv2.getTrackbarPos('Horizontal Line', 'Calibration 1') / 100.0
    vertical_line_position = cv2.getTrackbarPos('Vertical Line', 'Calibration 1') / 100.0
    contrast = cv2.getTrackbarPos('Contrast', 'Calibration 1') / 100.0 + 1.0
    brightness = cv2.getTrackbarPos('Brightness', 'Calibration 1') - 100
    hue = cv2.getTrackbarPos('Hue', 'Calibration 1') - 180
    saturation = cv2.getTrackbarPos('Saturation', 'Calibration 1') / 100.0
    conf_threshold = cv2.getTrackbarPos('Confidence Threshold', 'Calibration 2') / 100.0
    nms_threshold = cv2.getTrackbarPos('NMS Threshold', 'Calibration 2') / 100.0
    min_object_size = cv2.getTrackbarPos('Min Object Size', 'Calibration 2') / 1000.0
    max_object_size = cv2.getTrackbarPos('Max Object Size', 'Calibration 2') / 100.0
    blur_amount = cv2.getTrackbarPos('Blur', 'Calibration 2')
    sharpness = cv2.getTrackbarPos('Sharpness', 'Calibration 2') / 10.0
    gamma = cv2.getTrackbarPos('Gamma', 'Calibration 2') / 50.0
    line_thickness = cv2.getTrackbarPos('Line Thickness', 'Calibration 2')
    frame_interval = cv2.getTrackbarPos('Frame Interval', 'Calibration 2')
    save_config()

def save_config():
    config = {
        'horizontal_line_position': horizontal_line_position,
        'vertical_line_position': vertical_line_position,
        'contrast': contrast,
        'brightness': brightness,
        'hue': hue,
        'saturation': saturation,
        'conf_threshold': conf_threshold,
        'nms_threshold': nms_threshold,
        'min_object_size': min_object_size,
        'max_object_size': max_object_size,
        'blur_amount': blur_amount,
        'sharpness': sharpness,
        'gamma': gamma,
        'line_thickness': line_thickness,
        'frame_interval': frame_interval
    }
    with open('config_kendaraan.json', 'w') as f:
        json.dump(config, f)

def load_config():
    global horizontal_line_position, vertical_line_position, contrast, brightness, hue, saturation, conf_threshold, nms_threshold, min_object_size, max_object_size, blur_amount, sharpness, gamma, line_thickness, frame_interval
    try:
        with open('config_kendaraan.json', 'r') as f:
            config = json.load(f)
        horizontal_line_position = config.get('horizontal_line_position', 0.5)
        vertical_line_position = config.get('vertical_line_position', 0.5)
        contrast = config.get('contrast', 1.0)
        brightness = config.get('brightness', 0)
        hue = config.get('hue', 0)
        saturation = config.get('saturation', 1.0)
        conf_threshold = config.get('conf_threshold', 0.2)
        nms_threshold = config.get('nms_threshold', 0.4)
        min_object_size = config.get('min_object_size', 0.01)
        max_object_size = config.get('max_object_size', 0.8)
        blur_amount = config.get('blur_amount', 0)
        sharpness = config.get('sharpness', 0)
        gamma = config.get('gamma', 1.0)
        line_thickness = config.get('line_thickness', 2)
        frame_interval = config.get('frame_interval', 5)
    except FileNotFoundError:
        print("Config file not found. Using default values.")
    except json.JSONDecodeError:
        print("Error reading config file. Using default values.")

# Load configuration
load_config()

# Initialize YOLO
net = cv2.dnn.readNet("yolov3-spp.weights", "yolov3-spp.cfg")
classes = open("coco.names").read().strip().split("\n")

# Try to activate CUDA if available
try:
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    print("CUDA activated")
except:
    print("CUDA not available, using CPU")

# Open video
video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8', cv2.CAP_FFMPEG)
video.set(cv2.CAP_PROP_BUFFERSIZE, 10)

# Target FPS and frame size
target_fps = 30
target_size = (320, 320)  # Reduced size for faster processing

# Initialize variables for vehicle counting
motorcycle_count = 0
car_count = 0
truck_count = 0
prev_centroids = {}
tracking_id = 0
crossed_ids = set()

# Create calibration windows
cv2.namedWindow('Calibration 1')
cv2.namedWindow('Calibration 2')

# Calibration 1 trackbars
cv2.createTrackbar('Horizontal Line', 'Calibration 1', int(horizontal_line_position * 100), 100, update_calibration)
cv2.createTrackbar('Vertical Line', 'Calibration 1', int(vertical_line_position * 100), 100, update_calibration)
cv2.createTrackbar('Contrast', 'Calibration 1', int((contrast - 1.0) * 100), 200, update_calibration)
cv2.createTrackbar('Brightness', 'Calibration 1', int(brightness + 100), 200, update_calibration)
cv2.createTrackbar('Hue', 'Calibration 1', int(hue + 180), 360, update_calibration)
cv2.createTrackbar('Saturation', 'Calibration 1', int(saturation * 100), 200, update_calibration)

# Calibration 2 trackbars
cv2.createTrackbar('Confidence Threshold', 'Calibration 2', int(conf_threshold * 100), 100, update_calibration)
cv2.createTrackbar('NMS Threshold', 'Calibration 2', int(nms_threshold * 100), 100, update_calibration)
cv2.createTrackbar('Min Object Size', 'Calibration 2', int(min_object_size * 1000), 500, update_calibration)
cv2.createTrackbar('Max Object Size', 'Calibration 2', int(max_object_size * 100), 100, update_calibration)
cv2.createTrackbar('Blur', 'Calibration 2', blur_amount, 10, update_calibration)
cv2.createTrackbar('Sharpness', 'Calibration 2', int(sharpness * 10), 20, update_calibration)
cv2.createTrackbar('Gamma', 'Calibration 2', int(gamma * 50), 200, update_calibration)
cv2.createTrackbar('Line Thickness', 'Calibration 2', line_thickness, 10, update_calibration)
cv2.createTrackbar('Frame Interval', 'Calibration 2', frame_interval, 30, update_calibration)

frame_count = 0
start_time = time.time()
processing_times = []

# Initialize queue for frames
frame_queue = Queue(maxsize=5)
threading.Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()

while True:
    frame = frame_queue.get()
    if frame is None:
        break

    frame_count += 1
    if frame_count % frame_interval != 0:
        continue

    # Apply calibration
    frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
    
    # Apply blur
    if blur_amount > 0:
        frame = cv2.GaussianBlur(frame, (2*blur_amount+1, 2*blur_amount+1), 0)
    
    # Apply sharpening
    if sharpness > 0:
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]) * sharpness
        frame = cv2.filter2D(frame, -1, kernel)
    
    # Apply gamma correction
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    frame = cv2.LUT(frame, table)
    
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hsv[:,:,0] = (hsv[:,:,0] + hue) % 180
    hsv[:,:,1] = np.clip(hsv[:,:,1] * saturation, 0, 255)
    frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    # Resize frame
    frame = cv2.resize(frame, target_size)
    height, width = frame.shape[:2]
    horizontal_line_y = int(height * horizontal_line_position)
    vertical_line_x = int(width * vertical_line_position)

    # Draw counting lines
    cv2.line(frame, (0, horizontal_line_y), (width, horizontal_line_y), (0, 0, 255), line_thickness)
    cv2.line(frame, (vertical_line_x, 0), (vertical_line_x, height), (255, 0, 0), line_thickness)

    # Object detection
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, target_size, swapRB=True, crop=False)
    net.setInput(blob)
    
    process_start = time.time()
    outs = net.forward(get_output_layers(net))
    process_end = time.time()
    processing_times.append(process_end - process_start)

    # Initialize lists for detection results
    class_ids = []
    confidences = []
    boxes = []

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > conf_threshold and classes[class_id] in ["person", "car", "truck", "bus"]:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                # Apply size filters
                object_size = (w * h) / (width * height)
                if min_object_size <= object_size <= max_object_size:
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
        class_name = classes[class_ids[i]]

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
        if matched_id in prev_centroids:
            prev_x, prev_y = prev_centroids[matched_id]
            
            # Check horizontal line crossing
            if check_crossing(centroid_y, prev_y, horizontal_line_y) != 0:
                if matched_id not in crossed_ids:
                    crossed_ids.add(matched_id)
                    if class_name == "person":
                        motorcycle_count += 1
                    elif class_name == "car":
                        car_count += 1
                    elif class_name in ["truck", "bus"]:
                        truck_count += 1
            
            # Check vertical line crossing
            if (prev_x < vertical_line_x and centroid_x >= vertical_line_x) or \
               (prev_x > vertical_line_x and centroid_x <= vertical_line_x):
                if matched_id not in crossed_ids:
                    crossed_ids.add(matched_id)
                    if class_name == "person":
                        motorcycle_count += 1
                    elif class_name == "car":
                        car_count += 1
                    elif class_name in ["truck", "bus"]:
                        truck_count += 1

        draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(x+w), round(y+h))

    # Remove IDs that are no longer tracked
    crossed_ids = {id for id in crossed_ids if id in current_centroids}

    prev_centroids = current_centroids

    # Display counts and FPS every 5 frames
    if frame_count % 5 == 0:
        # Display counts
        cv2.putText(frame, f"Motorcycles: {motorcycle_count} Cars: {car_count} Trucks: {truck_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Calculate and display FPS
        elapsed_time = time.time() - start_time
        fps = frame_count / elapsed_time
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow("Vehicle Detection and Counting", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

# Final output
print(f"Final count - Motorcycles: {motorcycle_count}, Cars: {car_count}, Trucks: {truck_count}")
print(f"Average FPS: {frame_count / elapsed_time:.2f}")
print(f"Average processing time per frame: {sum(processing_times) / len(processing_times):.4f} seconds")

# Save final configuration
save_config()