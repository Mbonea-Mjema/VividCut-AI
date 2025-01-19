import cv2
import gc
import torch
import numpy as np
from moviepy.editor import VideoFileClip
from tqdm import tqdm
import os
import json
from ultralytics import YOLO
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector

class YOLOModel:
    def __init__(self):
        # Load both models
        self.person_model = YOLO("yolov5nu.pt")  # For person detection
        self.face_model = YOLO("https://github.com/akanametov/yolo-face/releases/download/v0.0.0/yolov8n-face.pt")  # For face detection
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.person_model.to(self.device)
        self.face_model.to(self.device)
        self.overlap_threshold = 0.5
        self.person_class_id = 0
        print(f"Using device: {self.device}")

    def calculate_overlap(self, box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        overlap_1 = intersection / area1
        overlap_2 = intersection / area2
        
        return max(overlap_1, overlap_2)

    def filter_overlapping_detections(self, boxes, confidences):
        if len(boxes) <= 1:
            return [(boxes[0], confidences[0])] if len(boxes) == 1 else []

        indices = np.argsort(confidences)[::-1]
        boxes = boxes[indices]
        confidences = confidences[indices]

        kept_detections = []
        for i in range(len(boxes)):
            should_keep = True
            for kept_box, _ in kept_detections:
                overlap = self.calculate_overlap(boxes[i], kept_box)
                if overlap > self.overlap_threshold:
                    should_keep = False
                    break
            
            if should_keep:
                kept_detections.append((boxes[i], confidences[i]))
                if len(kept_detections) >= 2:
                    break

        return kept_detections

    def detect_faces_in_person(self, frame, person_box):
        # Expand person box slightly to ensure face is included
        x1, y1, x2, y2 = person_box
        h, w = frame.shape[:2]
        
        # Expand box by 10%
        expand_x = (x2 - x1) * 0.1
        expand_y = (y2 - y1) * 0.1
        
        x1 = max(0, x1 - expand_x)
        y1 = max(0, y1 - expand_y)
        x2 = min(w, x2 + expand_x)
        y2 = min(h, y2 + expand_y)
        
        # Crop image to person area
        person_crop = frame[int(y1):int(y2), int(x1):int(x2)]
        
        # Detect faces in the cropped area
        face_results = self.face_model(person_crop, verbose=False)
        
        if len(face_results[0].boxes) > 0:
            # Face found - increase confidence
            return True
        return False

    def detect(self, frame):
        # Detect persons
        results = self.person_model(frame, verbose=False)
        
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        class_ids = results[0].boxes.cls.cpu().numpy()

        # Filter for persons with high confidence
        person_mask = (class_ids == self.person_class_id) & (confidences > 0.7)
        person_boxes = boxes[person_mask]
        person_confidences = confidences[person_mask]

        if len(person_boxes) == 0:
            return []

        # Check for faces in each person detection and adjust confidence
        adjusted_confidences = []
        for i, box in enumerate(person_boxes):
            has_face = self.detect_faces_in_person(frame, box)
            if has_face:
                # Boost confidence if face is detected
                adjusted_confidences.append(min(1.0, person_confidences[i] * 1.2))
            else:
                adjusted_confidences.append(person_confidences[i])

        # Filter overlapping detections with adjusted confidences
        filtered_detections = self.filter_overlapping_detections(
            person_boxes, np.array(adjusted_confidences)
        )

        return filtered_detections
class VideoProcessor:
    def __init__(self, model, temp_dir="temp_clips"):
        self.model = model
        self.detections = []
        self.temp_dir = temp_dir
        self.target_height = 1920
        self.target_width = None
        os.makedirs(temp_dir, exist_ok=True)

    def detect_scenes(self, input_video):
        """Detect scene changes in the video"""
        video_manager = VideoManager([input_video])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=30.0))

        video_manager.start()
        scene_manager.detect_scenes(video_manager)

        scene_list = scene_manager.get_scene_list()
        segments = [{"start": start.get_seconds(), "end": end.get_seconds()} 
                   for start, end in scene_list]

        video_manager.release()
        return segments
    def calculate_scaled_coordinates(self, box, original_height, original_width):
        x1, y1, x2, y2 = box
        
        # Calculate original width and height of detection
        orig_width = x2 - x1
        orig_height = y2 - y1
        
        # Calculate minimum size thresholds (e.g., 10% of original dimensions)
        min_width = original_width * 0.1
        min_height = original_height * 0.1
        
        # Skip if detection is too small
        if orig_width < min_width or orig_height < min_height:
            return None
            
        # Original calculation logic remains the same
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        width = x2 - x1
        height = y2 - y1
        
        mapped_x = np.interp(center_x, [0, original_width], [-self.target_width/2, self.target_width/2])
        mapped_y = np.interp(center_y, [0, original_height], [-self.target_height/2, self.target_height/2])
        
        scaled_width = width * (self.target_width / original_width)
        scaled_height = height * (self.target_height / original_height)
        
        return {
            "position": [float(mapped_x), float(mapped_y)],
            "size": [float(scaled_width), float(scaled_height)]
        }

    def generate_detection_groups(self, input_video):
        video = VideoFileClip(input_video)
        original_height = video.h
        original_width = video.w
        self.target_width = (original_width/original_height) * self.target_height
        segments = self.detect_scenes(input_video)
        detection_groups = []
        
        print(f"\nProcessing video:")
        print(f"Original dimensions: {original_width}x{original_height}")
        print(f"Target dimensions: {self.target_width}x{self.target_height}")
        print(f"Coordinate system: Center (0,0) with bounds:")
        print(f"X: -{self.target_width/2} to {self.target_width/2}")
        print(f"Y: -{self.target_height/2} to {self.target_height/2}")
        
        for segment_idx, segment in enumerate(tqdm(segments, desc="Generating Detection Groups")):
            clip = video.subclip(segment["start"], segment["end"])
            frame = clip.get_frame(0)
            
            detections = self.model.detect(frame)
            
            detection_list = []
            for det_idx, (box, conf) in enumerate(detections):
                scaled_coords = self.calculate_scaled_coordinates(box, original_height, original_width)
                
                # Only add detection if it meets size requirements
                if scaled_coords is not None:
                    detection_list.append({
                        "position": scaled_coords["position"],
                        "size": scaled_coords["size"],
                        "color": "red" if det_idx == 0 else "green"
                    })
            
            # Only create detection group if there are valid detections
            if detection_list:
                detection_group = {
                    "detections": detection_list,
                    "duration": segment["end"] - segment["start"],
                    "key": segment_idx + 1
                }
                detection_groups.append(detection_group)
            
            del clip
            gc.collect()
        
        video.close()
        
        with open('detection_groups.json', 'w') as f:
            json.dump(detection_groups, f, indent=2)
        
        print("\nconst detections = ")
        print(json.dumps(detection_groups, indent=2).replace('"', ''))
        
        return detection_groups

if __name__ == "__main__":
    input_video = "output.mp4"
    model = YOLOModel()
    video_processor = VideoProcessor(model)
    detection_groups = video_processor.generate_detection_groups(input_video)