import cv2
import numpy as np
import time
import threading
from queue import Queue
from ultralytics import YOLO

def read_frames(video, frame_queue):
    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_queue.put(frame)
    frame_queue.put(None)  # Signal end of video

def process_frames(model, frame_queue, result_queue):
    while True:
        frame = frame_queue.get()
        if frame is None:
            result_queue.put(None)
            break
        results = model(frame, stream=True)
        result_queue.put((frame, next(results)))

def main():
    model = YOLO('yolov8n.pt')
    model.fuse()

    video = cv2.VideoCapture('https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8', cv2.CAP_FFMPEG)
    video.set(cv2.CAP_PROP_BUFFERSIZE, 60)

    target_size = (480, 320)  # Increased size for better visibility
    frame_interval = 1  # Process every frame for smoother display

    cars_left = cars_right = 0
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = set()

    horizontal_line_position = 0.5
    vertical_line_position = 0.5

    frame_count = 0
    start_time = time.time()
    fps_update_interval = 5  # Update FPS every 30 frames
    display_interval = 5  # Update display every frame

    frame_queue = Queue(maxsize=60)
    result_queue = Queue(maxsize=60)

    threading.Thread(target=read_frames, args=(video, frame_queue), daemon=True).start()
    for _ in range(3):
        threading.Thread(target=process_frames, args=(model, frame_queue, result_queue), daemon=True).start()

    # Prepare a static background
    background = np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
    cv2.line(background, (0, int(target_size[1] * horizontal_line_position)), 
             (target_size[0], int(target_size[1] * horizontal_line_position)), (0, 0, 255), 2)
    cv2.line(background, (int(target_size[0] * vertical_line_position), 0), 
             (int(target_size[0] * vertical_line_position), target_size[1]), (255, 0, 0), 2)

    while True:
        result = result_queue.get()
        if result is None:
            break

        frame, r = result
        frame_count += 1
        if frame_count % frame_interval != 0:
            continue

        frame = cv2.resize(frame, target_size)
        display_frame = background.copy()

        current_centroids = {}
        for box in r.boxes:
            cls = int(box.cls[0])
            if model.names[cls] in ["car", "truck", "bus"]:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                centroid_x, centroid_y = (x1 + x2) // 2, (y1 + y2) // 2

                matched_id = min(prev_centroids.items(), key=lambda x: np.hypot(centroid_x - x[1][0], centroid_y - x[1][1]), default=(tracking_id, None))[0]
                if matched_id == tracking_id:
                    tracking_id += 1

                current_centroids[matched_id] = (centroid_x, centroid_y)

                if matched_id in prev_centroids and matched_id not in crossed_ids:
                    prev_y = prev_centroids[matched_id][1]
                    if (prev_y < target_size[1] * horizontal_line_position <= centroid_y) or \
                       (prev_y > target_size[1] * horizontal_line_position >= centroid_y):
                        crossed_ids.add(matched_id)
                        if centroid_x < target_size[0] * vertical_line_position:
                            cars_left += 1
                        else:
                            cars_right += 1

                # Draw only the center point of each vehicle
                cv2.circle(display_frame, (centroid_x, centroid_y), 3, (0, 255, 0), -1)

        crossed_ids = crossed_ids.intersection(current_centroids.keys())
        prev_centroids = current_centroids

        if frame_count % display_interval == 0:
            # Overlay the original frame with reduced opacity
            cv2.addWeighted(frame, 0.3, display_frame, 0.7, 0, display_frame)

            # Display counts and FPS
            cv2.putText(display_frame, f"Left: {cars_left} Right: {cars_right}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if frame_count % fps_update_interval == 0:
                fps = frame_count / (time.time() - start_time)
                cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Vehicle Counting", display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video.release()
    cv2.destroyAllWindows()

    print(f"Final count - Left: {cars_left}, Right: {cars_right}")
    print(f"Average FPS: {frame_count / (time.time() - start_time):.2f}")

if __name__ == "__main__":
    main()