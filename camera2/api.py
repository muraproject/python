import cv2
import numpy as np
import time
from ultralytics import YOLO

class GPUProcessor:
    def __init__(self):
        self.use_gpu = self._init_gpu()
        if self.use_gpu:
            cv2.ocl.setUseOpenCL(True)
            print("OpenCL status:", cv2.ocl.useOpenCL())
            print("OpenCL device:", cv2.ocl.Device.getDefault().name())

    def _init_gpu(self):
        try:
            test_mat = cv2.UMat(np.zeros((100, 100), dtype=np.uint8))
            cv2.blur(test_mat, (3, 3))
            print("GPU acceleration is available using OpenCV UMat")
            return True
        except Exception as e:
            print(f"GPU acceleration not available: {e}")
            return False

    def to_gpu(self, frame):
        if not isinstance(frame, cv2.UMat) and self.use_gpu:
            return cv2.UMat(frame)
        return frame

    def to_cpu(self, frame):
        if isinstance(frame, cv2.UMat):
            return frame.get()
        return frame

def create_red_overlay(frame):
    """Create a semi-transparent red overlay"""
    overlay = frame.copy()
    red_mask = np.zeros_like(frame)
    red_mask[:,:] = (0, 0, 255)  # BGR format - pure red
    cv2.addWeighted(red_mask, 0.3, overlay, 0.7, 0, overlay)  # 30% red overlay
    return overlay

def process_video_stream(video_source='api.mp4', skip_frames=2):
    # Initialize YOLO model
    # model = YOLO('fireModel.pt')
    model = YOLO('api3.pt')
    gpu_processor = GPUProcessor()
    
    # Initialize video capture
    video = cv2.VideoCapture(video_source)
    if not video.isOpened():
        print(f"Error: Could not open video file {video_source}")
        return
    
    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps = 0
    process_this_frame = 0
    
    # Get video properties for output
    frame_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Initialize output video writer
    output_path = 'output_detection.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 30.0, (frame_width, frame_height))
    
    while True:
        # Skip frames if needed
        for _ in range(skip_frames):
            ret = video.grab()
            if not ret:
                break

        ret, frame = video.read()
        if not ret:
            print("End of video file. Restarting...")
            video.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to beginning of video
            continue
            
        frame_count += 1
        current_time = time.time()

        # Calculate FPS
        if current_time - last_fps_time >= 1.0:
            fps = frame_count / (current_time - start_time)
            last_fps_time = current_time

        if process_this_frame == 0:
            # Process frame with GPU if available
            gpu_frame = gpu_processor.to_gpu(frame)
            
            if gpu_processor.use_gpu:
                gpu_frame = cv2.GaussianBlur(gpu_frame, (3, 3), 0)
            
            cpu_frame = gpu_processor.to_cpu(gpu_frame)
            results = model(cpu_frame)
            
            # Flag to track if fire is detected in current frame
            fire_detected = False
            
            # Create base overlay
            display_frame = cpu_frame.copy()
            
            # Process detections
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = model.names[cls]
                    
                    # Filter for fire detection
                    if conf > 0.5 and class_name == 'Fire':
                        fire_detected = True
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        # Draw fire detection box and label
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        label = f"Fire: {conf:.2f}"
                        cv2.putText(display_frame, label, (x1, y1-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    # if conf > 0.5 and class_name == 'Smoke':
                    #     fire_detected = True
                    #     # Get bounding box coordinates
                    #     x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                    #     # Draw fire detection box and label
                    #     cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    #     label = f"Smoke: {conf:.2f}"
                    #     cv2.putText(display_frame, label, (x1, y1-10), 
                    #               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Apply red overlay if fire is detected
            if fire_detected:
                display_frame = create_red_overlay(display_frame)
                cv2.putText(display_frame, "FIRE DETECTED!", 
                           (frame_width // 4, frame_height // 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
            
            # Add FPS counter
            cv2.putText(display_frame, f"FPS: {fps:.2f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Write frame to output video
            out.write(display_frame)
            
            # Display the result
            cv2.imshow("Fire Detection", display_frame)

        process_this_frame = (process_this_frame + 1) % 1

        # Break loop with 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Clean up
    video.release()
    out.release()
    cv2.destroyAllWindows()

def main():
    video_source = 'https://cctvjss.jogjakota.go.id/rthp/rthp_segoro_amarto_tegalrejo_2.stream/playlist.m3u8'  # Your input video file
    skip_frames = 2
    process_video_stream(video_source, skip_frames)

if __name__ == "__main__":
    main()