import cv2
import numpy as np
import time

def get_output_layers(net):
    layer_names = net.getLayerNames()
    try:
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
    except:
        output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    return output_layers

def draw_bounding_box(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    label = f"{classes[class_id]}: {confidence:.2f}"
    color = COLORS[class_id]
    cv2.rectangle(img, (x,y), (x_plus_w,y_plus_h), color, 2)
    cv2.putText(img, label, (x-10,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

# Baca konfigurasi dan weights YOLO
net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")

# Baca nama-nama kelas
with open("coco.names", "r") as f:
    classes = [line.strip() for line in f.readlines()]

COLORS = np.random.uniform(0, 255, size=(len(classes), 3))

# Buka video
video = cv2.VideoCapture('2.mp4')

# Dapatkan FPS asli video
fps = video.get(cv2.CAP_PROP_FPS)
print(f"Original FPS: {fps}")

# Set target FPS (misalnya, 5 FPS)
target_fps = 5
frame_interval = int(fps / target_fps)

frame_count = 0
start_time = time.time()

while True:
    ret, image = video.read()
    if not ret:
        break
    
    frame_count += 1
    
    # Hanya proses setiap frame_interval frame
    if frame_count % frame_interval != 0:
        continue

    Height, Width = image.shape[:2]
    scale = 0.00392

    blob = cv2.dnn.blobFromImage(image, scale, (416,416), (0,0,0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(get_output_layers(net))

    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5
    nms_threshold = 0.4

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5 and classes[class_id] == "person":
                center_x = int(detection[0] * Width)
                center_y = int(detection[1] * Height)
                w = int(detection[2] * Width)
                h = int(detection[3] * Height)
                x = center_x - w // 2
                y = center_y - h // 2
                class_ids.append(class_id)
                confidences.append(float(confidence))
                boxes.append([x, y, w, h])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

    for i in indices:
        i = i[0] if isinstance(i, (tuple, list)) else i
        box = boxes[i]
        x, y, w, h = [int(v) for v in box]
        draw_bounding_box(image, class_ids[i], confidences[i], x, y, x+w, y+h)

    # Hitung dan tampilkan FPS
    elapsed_time = time.time() - start_time
    fps_current = frame_count / elapsed_time
    cv2.putText(image, f"FPS: {fps_current:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Human Detection", image)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

print(f"Average FPS: {frame_count / (time.time() - start_time):.2f}")