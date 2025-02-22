import cv2
import os
import numpy as np
from tkinter import *
from tkinter import messagebox, simpledialog
import pickle
from PIL import Image, ImageTk
import time

class FaceRecognitionSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Recognition System")
        self.root.geometry("800x600")
        
        # Initialize OpenCV face detector
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Variables
        self.cap = None
        self.is_capturing = False
        self.current_frame = None
        self.faces_dir = 'faces'
        self.model_path = 'face_model.pkl'
        self.names_path = 'names.pkl'
        self.names = {}
        self.next_id = 0
        
        # Manual face recognition variables
        self.face_data = []  # Will store face images
        self.face_labels = []  # Will store face labels/ids
        
        # Create faces directory if it doesn't exist
        if not os.path.exists(self.faces_dir):
            os.makedirs(self.faces_dir)
        
        # GUI Components
        self.create_gui()
        
        # Load existing model and names if available
        self.load_model()
        
    def create_gui(self):
        # Frame for video feed
        self.video_frame = Frame(self.root, width=640, height=480, bg="black")
        self.video_frame.pack(pady=10)
        self.video_label = Label(self.video_frame)
        self.video_label.pack()
        
        # Control buttons frame
        self.control_frame = Frame(self.root)
        self.control_frame.pack(pady=10)
        
        # Buttons
        self.btn_start = Button(self.control_frame, text="Start Camera", command=self.start_camera, bg="#4CAF50", fg="white", width=15)
        self.btn_start.grid(row=0, column=0, padx=5)
        
        self.btn_stop = Button(self.control_frame, text="Stop Camera", command=self.stop_camera, bg="#F44336", fg="white", width=15)
        self.btn_stop.grid(row=0, column=1, padx=5)
        
        self.btn_add_face = Button(self.control_frame, text="Add New Face", command=self.add_new_face, bg="#2196F3", fg="white", width=15)
        self.btn_add_face.grid(row=0, column=2, padx=5)
        
        self.btn_train = Button(self.control_frame, text="Train Model", command=self.train_model, bg="#FF9800", fg="white", width=15)
        self.btn_train.grid(row=0, column=3, padx=5)
        
        # Status label
        self.status_label = Label(self.root, text="System Ready", bd=1, relief=SUNKEN, anchor=W)
        self.status_label.pack(side=BOTTOM, fill=X)
        
    def load_model(self):
        # Load names dictionary
        if os.path.exists(self.names_path):
            with open(self.names_path, 'rb') as f:
                self.names = pickle.load(f)
                # Find the next available ID
                if self.names:
                    self.next_id = max(int(id) for id in self.names.keys()) + 1
                else:
                    self.next_id = 0
        
        # Load face data and labels
        if os.path.exists(self.model_path):
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.face_data = data['faces']
                self.face_labels = data['labels']
            self.update_status(f"Model loaded with {len(self.names)} persons")
        else:
            self.update_status("No existing model found")
    
    def update_status(self, message):
        self.status_label.config(text=message)
        
    def start_camera(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Could not open camera")
                self.cap = None
                return
                
        self.is_capturing = True
        self.update_status("Camera started")
        self.update_frame()
        
    def stop_camera(self):
        self.is_capturing = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.update_status("Camera stopped")
        self.video_label.config(image="")
        
    def update_frame(self):
        if self.is_capturing:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                
                # Detect faces in the frame
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                for (x, y, w, h) in faces:
                    # Draw rectangle around face
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Predict if model is trained
                    if len(self.face_data) > 0:
                        roi_gray = gray[y:y+h, x:x+w]
                        roi_gray = cv2.resize(roi_gray, (100, 100))
                        
                        # Simple face recognition using normalized correlation
                        max_correlation = -1
                        predicted_id = -1
                        
                        for i, face in enumerate(self.face_data):
                            # Normalize both faces
                            face_norm = cv2.normalize(face, None, 0, 255, cv2.NORM_MINMAX)
                            roi_norm = cv2.normalize(roi_gray, None, 0, 255, cv2.NORM_MINMAX)
                            
                            # Calculate correlation
                            correlation = cv2.matchTemplate(face_norm, roi_norm, cv2.TM_CCOEFF_NORMED)[0][0]
                            
                            if correlation > max_correlation:
                                max_correlation = correlation
                                predicted_id = self.face_labels[i]
                        
                        if max_correlation > 0.5:  # Threshold for identification
                            confidence = max_correlation * 100
                            name = self.names.get(str(predicted_id), "Unknown")
                            confidence_text = f"{int(confidence)}%"
                            cv2.putText(frame, name, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            cv2.putText(frame, confidence_text, (x, y+h+30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        else:
                            cv2.putText(frame, "Unknown", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                
                # Convert to RGB for tkinter
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.config(image=imgtk)
            
            # Continue updating
            self.root.after(10, self.update_frame)
            
    def add_new_face(self):
        if not self.is_capturing or self.current_frame is None:
            messagebox.showwarning("Warning", "Camera must be on to add a face")
            return
            
        # Ask for person's name
        name = simpledialog.askstring("Input", "Enter person's name:")
        if not name:
            return
            
        # Get face samples
        self.update_status(f"Capturing face samples for {name}...")
        
        # Create directory for this person
        person_dir = os.path.join(self.faces_dir, str(self.next_id))
        if not os.path.exists(person_dir):
            os.makedirs(person_dir)
            
        # Store name in dictionary
        self.names[str(self.next_id)] = name
        
        # Save multiple samples
        count = 0
        max_samples = 30
        
        while count < max_samples:
            ret, frame = self.cap.read()
            if not ret:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) == 1:  # Only save if one face is detected
                (x, y, w, h) = faces[0]
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # Save the face
                roi_gray = gray[y:y+h, x:x+w]
                roi_gray = cv2.resize(roi_gray, (100, 100))  # Resize to standard size
                sample_path = os.path.join(person_dir, f"{count}.jpg")
                cv2.imwrite(sample_path, roi_gray)
                count += 1
                
                # Add to face data for real-time model
                self.face_data.append(roi_gray)
                self.face_labels.append(self.next_id)
                
                # Show progress
                self.update_status(f"Capturing samples: {count}/{max_samples}")
                
                # Convert to RGB for tkinter
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.config(image=imgtk)
                
                # Update the window and wait
                self.root.update()
                time.sleep(0.2)  # Brief delay between captures
        
        # Increment ID for next person
        self.next_id += 1
        
        # Save names dictionary
        with open(self.names_path, 'wb') as f:
            pickle.dump(self.names, f)
            
        # Save model
        model_data = {
            'faces': self.face_data,
            'labels': self.face_labels
        }
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
            
        self.update_status(f"Captured {count} samples for {name}")
        messagebox.showinfo("Success", f"Face samples for {name} captured successfully!")
        
    def train_model(self):
        if not os.listdir(self.faces_dir):
            messagebox.showwarning("Warning", "No face samples to train on")
            return
            
        self.update_status("Training model... Please wait")
        self.root.update()
        
        # Clear existing data
        self.face_data = []
        self.face_labels = []
        
        # Go through all subdirectories in faces_dir
        for person_id in os.listdir(self.faces_dir):
            person_dir = os.path.join(self.faces_dir, person_id)
            if os.path.isdir(person_dir):
                for img_file in os.listdir(person_dir):
                    if img_file.endswith('.jpg'):
                        img_path = os.path.join(person_dir, img_file)
                        face_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if face_img is not None:
                            # Make sure all images are same size
                            face_img = cv2.resize(face_img, (100, 100))
                            self.face_data.append(face_img)
                            self.face_labels.append(int(person_id))
        
        if not self.face_data:
            self.update_status("No valid face images found")
            return
        
        # Save the model
        model_data = {
            'faces': self.face_data,
            'labels': self.face_labels
        }
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        self.update_status(f"Model trained successfully with {len(self.face_data)} images of {len(set(self.face_labels))} people")
        messagebox.showinfo("Success", "Face recognition model trained successfully!")
        
    def run(self):
        self.root.mainloop()
        # Clean up
        if self.cap is not None:
            self.cap.release()

if __name__ == "__main__":
    root = Tk()
    app = FaceRecognitionSystem(root)
    app.run()