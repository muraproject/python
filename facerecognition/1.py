import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk
import pickle
from datetime import datetime
import time

class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Recognition System")
        self.root.geometry("1000x600")
        self.root.configure(bg="#f0f0f0")
        
        # Initialize variables
        self.video_capture = None
        self.is_capturing = False
        self.current_frame = None
        self.data_dir = "face_data"
        self.model_file = "face_recognizer.pkl"
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.face_recognizer = None
        self.last_recognition_time = 0
        self.recognition_interval = 0.5  # seconds
        
        self.people_dict = {}  # {label_id: name}
        self.next_id = 0
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Initialize face recognizer and load model if available
        self.initialize_recognizer()
        
        # Create main frames
        self.setup_ui()
        
    def initialize_recognizer(self):
        try:
            # Initialize the recognizer
            if 'cv2.face' in dir(cv2):
                # OpenCV contrib modules installed
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
            else:
                # Fallback to basic recognizer
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create() 
                # If this fails, we'll catch and handle in except block
            
            # Try to load existing model
            if os.path.exists(self.model_file):
                try:
                    with open(self.model_file, 'rb') as f:
                        data = pickle.load(f)
                        self.people_dict = data['people']
                        self.next_id = data['next_id']
                        model_data = data['model_data']
                        
                        # Deserialize model (OpenCV doesn't support direct pickling)
                        self.face_recognizer.read(model_data)
                        print(f"Loaded model with {len(self.people_dict)} people")
                except Exception as e:
                    print(f"Could not load model, starting fresh: {e}")
                    
        except Exception as e:
            print(f"Error initializing face recognizer: {e}")
            messagebox.showwarning("Initialization Warning", 
                                "Face recognition module couldn't be initialized properly.\n"
                                "This may affect face recognition capabilities.\n\n"
                                "Please ensure OpenCV is properly installed.")
            self.face_recognizer = None
            
    def setup_ui(self):
        # Top frame for title and buttons
        top_frame = tk.Frame(self.root, bg="#3498db", height=70)
        top_frame.pack(fill=tk.X)
        
        # Title
        title_label = tk.Label(
            top_frame, 
            text="Face Recognition System", 
            font=("Arial", 20, "bold"),
            bg="#3498db",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # Main content frame
        content_frame = tk.Frame(self.root, bg="#f0f0f0")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Video frame (left side)
        self.video_frame = tk.Frame(content_frame, bg="black", width=640, height=480)
        self.video_frame.pack(side=tk.LEFT, padx=10)
        
        # Camera placeholder
        self.camera_label = tk.Label(self.video_frame, bg="black")
        self.camera_label.pack(fill=tk.BOTH, expand=True)
        
        # Control panel (right side)
        control_panel = tk.Frame(content_frame, bg="#f0f0f0", width=300)
        control_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        # Status indicator
        self.status_frame = tk.Frame(control_panel, bg="#f0f0f0")
        self.status_frame.pack(fill=tk.X, pady=10)
        
        self.status_indicator = tk.Canvas(self.status_frame, width=20, height=20, bg="#f0f0f0", highlightthickness=0)
        self.status_indicator.grid(row=0, column=0, padx=5)
        self.status_indicator.create_oval(2, 2, 18, 18, fill="red", tags="indicator")
        
        self.status_label = tk.Label(self.status_frame, text="Camera Off", bg="#f0f0f0", font=("Arial", 12))
        self.status_label.grid(row=0, column=1, sticky="w")
        
        # Buttons
        button_style = {"font": ("Arial", 12), "width": 20, "cursor": "hand2"}
        
        self.start_button = tk.Button(
            control_panel, 
            text="Start Camera", 
            command=self.toggle_camera,
            bg="#2ecc71",
            fg="white",
            **button_style
        )
        self.start_button.pack(pady=10)
        
        self.add_face_button = tk.Button(
            control_panel, 
            text="Add New Person", 
            command=self.add_new_person,
            bg="#3498db",
            fg="white",
            state=tk.DISABLED,
            **button_style
        )
        self.add_face_button.pack(pady=10)
        
        # People list
        list_frame = tk.Frame(control_panel, bg="#f0f0f0")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        list_label = tk.Label(list_frame, text="Registered People:", font=("Arial", 14, "bold"), bg="#f0f0f0")
        list_label.pack(anchor="w", pady=5)
        
        list_container = tk.Frame(list_frame, bg="white", highlightbackground="#ddd", highlightthickness=1)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for the list
        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # People listbox
        self.people_listbox = tk.Listbox(
            list_container,
            font=("Arial", 12),
            selectbackground="#3498db",
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.people_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.people_listbox.yview)
        
        # Remove button
        self.remove_button = tk.Button(
            control_panel, 
            text="Remove Selected Person", 
            command=self.remove_person,
            bg="#e74c3c",
            fg="white",
            **button_style
        )
        self.remove_button.pack(pady=10)
        
        # Update the listbox with existing names
        self.update_people_list()
        
    def update_people_list(self):
        # Clear the current list
        self.people_listbox.delete(0, tk.END)
        
        # Add all known names to the list
        names = sorted(set(self.people_dict.values()))
        for name in names:
            self.people_listbox.insert(tk.END, name)
    
    def save_model(self):
        if self.face_recognizer is None:
            messagebox.showerror("Error", "Face recognizer is not initialized")
            return False
            
        try:
            # Save model parameters to a file
            model_data = "temp_model.xml"
            self.face_recognizer.write(model_data)
            
            # Prepare data for serialization
            data = {
                'people': self.people_dict,
                'next_id': self.next_id,
                'model_data': model_data
            }
            
            # Save to pickle file
            with open(self.model_file, 'wb') as f:
                pickle.dump(data, f)
                
            # Clean up temporary file
            if os.path.exists(model_data):
                os.remove(model_data)
                
            print(f"Saved model with {len(self.people_dict)} people")
            return True
            
        except Exception as e:
            print(f"Error saving model: {e}")
            messagebox.showerror("Error", f"Could not save model: {e}")
            return False
    
    def toggle_camera(self):
        if self.is_capturing:
            # Stop the camera
            self.is_capturing = False
            if self.video_capture:
                self.video_capture.release()
                self.video_capture = None
            
            # Update UI
            self.camera_label.config(image="")
            self.start_button.config(text="Start Camera", bg="#2ecc71")
            self.status_indicator.itemconfig("indicator", fill="red")
            self.status_label.config(text="Camera Off")
            self.add_face_button.config(state=tk.DISABLED)
            
        else:
            # Start the camera
            self.video_capture = cv2.VideoCapture(0)
            if self.video_capture.isOpened():
                self.is_capturing = True
                
                # Update UI
                self.start_button.config(text="Stop Camera", bg="#e74c3c")
                self.status_indicator.itemconfig("indicator", fill="green")
                self.status_label.config(text="Camera On")
                self.add_face_button.config(state=tk.NORMAL)
                
                # Start video loop
                self.update_video()
            else:
                messagebox.showerror("Error", "Could not access the camera. Please check your camera connection.")
    
    def update_video(self):
        if self.is_capturing and self.video_capture:
            ret, frame = self.video_capture.read()
            if ret:
                self.current_frame = frame.copy()
                
                # Convert to grayscale for face detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = self.face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=1.1, 
                    minNeighbors=5,
                    minSize=(30, 30)
                )
                
                # Only run recognition every few frames to improve performance
                current_time = time.time()
                should_recognize = (current_time - self.last_recognition_time) >= self.recognition_interval
                
                # Draw rectangles around faces and recognize if possible
                for (x, y, w, h) in faces:
                    # Draw rectangle around face
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Try to recognize the face if we have a trained model
                    if self.face_recognizer is not None and len(self.people_dict) > 0 and should_recognize:
                        try:
                            # Preprocess face for recognition
                            face_roi = gray[y:y+h, x:x+w]
                            face_roi = cv2.resize(face_roi, (100, 100))
                            
                            # Predict the face
                            label_id, confidence = self.face_recognizer.predict(face_roi)
                            
                            # Lower confidence is better for LBPH
                            name = "Unknown"
                            if confidence < 100 and label_id in self.people_dict:  # Adjust threshold as needed
                                name = self.people_dict[label_id]
                                confidence_text = f"{int(100 - confidence)}%"
                                display_text = f"{name} ({confidence_text})"
                            else:
                                display_text = "Unknown"
                                
                            # Draw name
                            cv2.rectangle(frame, (x, y-30), (x+w, y), (0, 255, 0), cv2.FILLED)
                            cv2.putText(frame, display_text, (x+5, y-5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                                      
                        except Exception as e:
                            print(f"Recognition error: {e}")
                
                if should_recognize and len(faces) > 0:
                    self.last_recognition_time = current_time
                
                # Convert to RGB for tkinter
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                img = ImageTk.PhotoImage(image=img)
                
                # Update the label
                self.camera_label.config(image=img)
                self.camera_label.image = img
                
                # Schedule the next update
                self.root.after(10, self.update_video)
            else:
                self.toggle_camera()  # Stop if we can't read from camera
    
    def get_name_id(self, name):
        """Get the ID for a name, or assign a new one"""
        # Check if name already exists
        for label_id, existing_name in self.people_dict.items():
            if existing_name == name:
                return label_id
                
        # Assign new ID
        new_id = self.next_id
        self.people_dict[new_id] = name
        self.next_id += 1
        return new_id
    
    def add_new_person(self):
        if not self.is_capturing or self.current_frame is None:
            messagebox.showerror("Error", "Camera must be on to add a new person")
            return
            
        if self.face_recognizer is None:
            # Try to initialize again
            self.initialize_recognizer()
            if self.face_recognizer is None:
                messagebox.showerror("Error", "Face recognizer could not be initialized")
                return
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        if len(faces) == 0:
            messagebox.showerror("Error", "No face detected. Please make sure your face is visible to the camera.")
            return
        
        # If multiple faces detected, ask user which one to add
        selected_face = faces[0]
        if len(faces) > 1:
            # Draw numbered rectangles on faces
            temp_frame = self.current_frame.copy()
            for i, (x, y, w, h) in enumerate(faces):
                cv2.rectangle(temp_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(temp_frame, str(i+1), (x+5, y+h-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            
            # Show the image with numbered faces
            cv2.imshow("Select a face", temp_frame)
            cv2.waitKey(1000)  # Show briefly
            
            # Ask which face to add
            face_num = simpledialog.askinteger("Select Face", 
                                              "Multiple faces detected. Enter the number of the face to add (1-{}):".format(len(faces)),
                                              minvalue=1, maxvalue=len(faces))
            cv2.destroyWindow("Select a face")
            
            if face_num is None:
                return  # User canceled
            
            selected_face = faces[face_num-1]
        
        # Ask for the person's name
        name = simpledialog.askstring("New Person", "Enter the name of the person:")
        if not name or name.strip() == "":
            return  # User canceled or provided empty name
        
        # Get or create ID for this person
        label_id = self.get_name_id(name)
        
        # Create person directory if it doesn't exist
        person_dir = os.path.join(self.data_dir, name)
        if not os.path.exists(person_dir):
            os.makedirs(person_dir)
        
        # Take multiple images for better training
        image_paths, face_samples = self.capture_multiple_faces(name, selected_face, label_id)
        
        if not image_paths or len(image_paths) == 0:
            messagebox.showerror("Error", "Failed to capture face images")
            return
            
        # Train the model with the new faces
        self.train_with_new_faces(face_samples, label_id)
        
        # Update the listbox
        self.update_people_list()
        
        messagebox.showinfo("Success", f"Added {name} to the database with {len(image_paths)} image(s)")
    
    def capture_multiple_faces(self, name, initial_face, label_id, num_images=5):
        """Capture multiple images of the same face for better training"""
        x, y, w, h = initial_face
        person_dir = os.path.join(self.data_dir, name)
        
        captured_count = 0
        frame_skip = 0
        image_paths = []
        face_samples = []
        
        messagebox.showinfo("Capturing", f"Will capture {num_images} images. Please move your head slightly between captures.")
        
        while captured_count < num_images and self.is_capturing:
            ret, frame = self.video_capture.read()
            if not ret:
                break
                
            frame_skip += 1
            if frame_skip % 10 != 0:  # Skip frames to give time to move
                continue
                
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Re-detect face in the general area to adjust for movement
            roi_y_start = max(0, y-20)
            roi_y_end = min(frame.shape[0], y+h+20)
            roi_x_start = max(0, x-20)
            roi_x_end = min(frame.shape[1], x+w+20)
            
            # Ensure ROI is valid
            if roi_y_end <= roi_y_start or roi_x_end <= roi_x_start:
                continue
                
            face_roi = gray[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
            
            # Detect faces in ROI
            try:
                faces = self.face_cascade.detectMultiScale(
                    face_roi,
                    scaleFactor=1.1, 
                    minNeighbors=5,
                    minSize=(30, 30)
                )
                
                if len(faces) == 1:
                    # Adjust coordinates back to full frame
                    fx, fy, fw, fh = faces[0]
                    fx += roi_x_start
                    fy += roi_y_start
                    
                    # Extract and normalize face
                    face_img = gray[fy:fy+fh, fx:fx+fw]
                    face_img = cv2.resize(face_img, (100, 100))
                    face_samples.append(face_img)
                    
                    # Save the face image with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = os.path.join(person_dir, f"{label_id}_{timestamp}.jpg")
                    cv2.imwrite(filename, face_img)
                    image_paths.append(filename)
                    
                    # Also save a copy of the full face for display
                    color_face = frame[fy:fy+fh, fx:fx+fw]
                    display_filename = os.path.join(person_dir, f"display_{timestamp}.jpg")
                    cv2.imwrite(display_filename, color_face)
                    
                    captured_count += 1
                    
                    # Show progress
                    progress_msg = f"Captured image {captured_count}/{num_images}"
                    print(progress_msg)
                    
                    # Highlight the captured face
                    display_frame = frame.copy()
                    cv2.rectangle(display_frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 3)
                    cv2.putText(display_frame, progress_msg, (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Show the captured frame
                    rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb_frame)
                    img = ImageTk.PhotoImage(image=img)
                    self.camera_label.config(image=img)
                    self.camera_label.image = img
                    
                    # Wait a bit between captures
                    self.root.update()
                    self.root.after(500)
            except Exception as e:
                print(f"Error during face capture: {e}")
                continue
                
        return image_paths, face_samples
    
    def train_with_new_faces(self, new_face_samples, label_id):
        """Train the model with newly captured face samples"""
        if self.face_recognizer is None or not new_face_samples:
            return False
            
        try:
            labels = [label_id] * len(new_face_samples)
            
            # If this is the first training
            if len(self.people_dict) == 1 and self.people_dict.get(label_id) is not None:
                self.face_recognizer.train(new_face_samples, np.array(labels))
            else:
                # Update the existing model 
                self.face_recognizer.update(new_face_samples, np.array(labels))
                
            # Save the updated model
            self.save_model()
            return True
            
        except Exception as e:
            print(f"Error training model: {e}")
            messagebox.showerror("Training Error", f"Could not train model: {e}")
            return False
    
    def remove_person(self):
        # Get selected person
        selected_idx = self.people_listbox.curselection()
        if not selected_idx:
            messagebox.showwarning("Warning", "Please select a person to remove")
            return
        
        selected_name = self.people_listbox.get(selected_idx[0])
        confirm = messagebox.askyesno("Confirm Deletion", 
                                   f"Are you sure you want to remove {selected_name} from the database? This will delete all images of this person.")
        
        if confirm:
            try:
                # Find all IDs for this name
                ids_to_remove = []
                for id, name in self.people_dict.items():
                    if name == selected_name:
                        ids_to_remove.append(id)
                
                # Remove from people dictionary
                for id in ids_to_remove:
                    if id in self.people_dict:
                        del self.people_dict[id]
                
                # Delete the person's directory
                person_dir = os.path.join(self.data_dir, selected_name)
                if os.path.exists(person_dir):
                    for file in os.listdir(person_dir):
                        os.remove(os.path.join(person_dir, file))
                    os.rmdir(person_dir)
                
                # Save the updated model
                self.save_model()
                
                # Update the listbox
                self.update_people_list()
                
                # Need to retrain model from scratch
                messagebox.showinfo("Retraining Required", 
                                 f"Removed {selected_name} from database. The model will need to be retrained.")
                
                # Offer to retrain now
                retrain = messagebox.askyesno("Retrain Model", 
                                          "Do you want to retrain the model now? This may take a moment.")
                if retrain:
                    self.retrain_full_model()
                
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while removing the person: {e}")
    
    def retrain_full_model(self):
        """Retrain the entire model from scratch using saved images"""
        try:
            # Reset recognizer
            if 'cv2.face' in dir(cv2):
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
            else:
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
                
            # Show loading message
            loading_window = tk.Toplevel(self.root)
            loading_window.title("Retraining")
            loading_window.geometry("300x100")
            loading_label = tk.Label(loading_window, text="Retraining model from saved images...\nThis may take a moment.", 
                                  font=("Arial", 12), pady=20)
            loading_label.pack()
            self.root.update()
            
            # Collect all training images
            faces = []
            labels = []
            
            for person_name in os.listdir(self.data_dir):
                person_dir = os.path.join(self.data_dir, person_name)
                if os.path.isdir(person_dir):
                    # Get person ID
                    person_id = None
                    for id, name in self.people_dict.items():
                        if name == person_name:
                            person_id = id
                            break
                            
                    if person_id is None:
                        # Assign new ID if needed
                        person_id = self.next_id
                        self.people_dict[person_id] = person_name
                        self.next_id += 1
                    
                    # Load all face images
                    for image_name in os.listdir(person_dir):
                        if image_name.startswith("display_"):
                            continue  # Skip display images
                            
                        if image_name.endswith(".jpg"):
                            try:
                                image_path = os.path.join(person_dir, image_name)
                                face_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                                
                                if face_img is not None:
                                    # Ensure consistent size
                                    face_img = cv2.resize(face_img, (100, 100))
                                    
                                    # Add to training data
                                    faces.append(face_img)
                                    labels.append(person_id)
                            except Exception as e:
                                print(f"Error loading image {image_name}: {e}")
            
            # Train if we have data
            if len(faces) > 0:
                self.face_recognizer.train(faces, np.array(labels))
                self.save_model()
                loading_window.destroy()
                messagebox.showinfo("Retraining Complete", 
                                 f"Model retrained successfully with {len(faces)} images.")
            else:
                loading_window.destroy()
                messagebox.showwarning("Retraining Failed", 
                                    "No valid face images found for training.")
                
        except Exception as e:
            try:
                loading_window.destroy()
            except:
                pass
            messagebox.showerror("Retraining Error", f"An error occurred during retraining: {e}")
            
    def on_closing(self):
        if self.is_capturing:
            self.toggle_camera()
        self.root.destroy()

def main():
    try:
        root = tk.Tk()
        app = FaceRecognitionApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"Application error: {e}")
        tk.messagebox.showerror("Application Error", 
                            f"An error occurred: {e}\n\nPlease ensure OpenCV is properly installed.")

if __name__ == "__main__":
    main()