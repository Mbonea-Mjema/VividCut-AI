#!/usr/bin/env python3
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
        # Load both models – one for person detection and one for face detection.
        self.person_model = YOLO("yolov8n.pt") # Person detector
        self.face_model = YOLO("https://github.com/akanametov/yolo-face/releases/download/v0.0.0/yolov8n-face.pt") # Face detector
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.person_model.to(self.device)
        self.face_model.to(self.device)
        self.overlap_threshold = 0
        self.person_class_id = 0
        print(f"Using device: {self.device}")


    def calculate_overlap(self, box1, box2):
        """Calculates Intersection over Union (IoU) between two boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection_area = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        iou = intersection_area / float(area1 + area2 - intersection_area)
        return iou

    def filter_overlapping_detections(self, boxes, confidences):
        """Filters overlapping detections based on IoU and confidence, keeping at most two."""
        if len(boxes) == 0:
            return []

        indices = np.argsort(confidences)[::-1]
        boxes = boxes[indices]
        confidences = confidences[indices]

        kept_detections = []
        for i in range(len(boxes)):
            keep = True
            for j in range(len(kept_detections)):
                if self.calculate_overlap(boxes[i], kept_detections[j][0]) > self.overlap_threshold:
                    keep = False
                    break
            if keep:
                kept_detections.append((boxes[i], confidences[i]))
                if len(kept_detections) >= 2:  # Keep a maximum of 2 detections.
                    break

        return kept_detections

    def detect_faces_in_person(self, frame, person_box):
        """Within a person detection, looks for a face within an expanded window."""
        x1, y1, x2, y2 = map(int, person_box)  # Convert to integers
        h, w = frame.shape[:2]

        # Expand the bounding box by 10% in each direction.
        expand_x = int((x2 - x1) * 0.1)
        expand_y = int((y2 - y1) * 0.1)
        x1 = max(0, x1 - expand_x)
        y1 = max(0, y1 - expand_y)
        x2 = min(w, x2 + expand_x)
        y2 = min(h, y2 + expand_y)

        person_crop = frame[y1:y2, x1:x2]
        if person_crop.size == 0:
            return False

        face_results = self.face_model(person_crop, verbose=False)
        if len(face_results[0].boxes) > 0:
            face_confidences = face_results[0].boxes.conf.cpu().numpy()
            if np.any(face_confidences > 0.3):  # Use a face confidence threshold.
                return True
        return False

    def get_face_box(self, frame, person_box):
        """
        Attempts to detect a face within an expanded person detection.
        Returns the face box (adjusted to coordinate system of the full frame) if found.
        """
        x1, y1, x2, y2 = map(int, person_box)
        h, w = frame.shape[:2]
        # Expand the person box by 10%
        expand_x = int((x2 - x1) * 0.1)
        expand_y = int((y2 - y1) * 0.1)
        crop_x1 = max(0, x1 - expand_x)
        crop_y1 = max(0, y1 - expand_y)
        crop_x2 = min(w, x2 + expand_x)
        crop_y2 = min(h, y2 + expand_y)
        person_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if person_crop.size == 0:
            return None
        face_results = self.face_model(person_crop, verbose=False)
        if len(face_results[0].boxes) > 0:
            # Get the best face (highest confidence)
            boxes = face_results[0].boxes.xyxy.cpu().numpy()
            confs = face_results[0].boxes.conf.cpu().numpy()
            best_idx = int(np.argmax(confs))
            face_box = boxes[best_idx]
            # Adjust face_box coordinates from the crop coordinate system to the original frame
            face_box_adjusted = np.array([
                face_box[0] + crop_x1,
                face_box[1] + crop_y1,
                face_box[2] + crop_x1,
                face_box[3] + crop_y1
            ])
            return True,face_box_adjusted
        return False,None




    def detect(self, frame):
        """Detect persons, check for faces (to boost confidence) and filter overlapping detections."""
        results = self.person_model(frame, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        class_ids = results[0].boxes.cls.cpu().numpy()

        person_mask = (class_ids == self.person_class_id) & (confidences > 0.3)
        person_boxes = boxes[person_mask]
        person_confidences = confidences[person_mask]

        if len(person_boxes) == 0:
            return []

        adjusted_confidences = []
        adjusted_boxes=[]
        
        
        for i, box in enumerate(person_boxes):
            has_face,box = self.get_face_box(frame, box)
            # Boost confidence if a face is detected.
            if has_face:
                adjusted_confidences.append(min(1.0, person_confidences[i] * 1.2))
                person_boxes[i]=box
            else:
                adjusted_confidences.append(person_confidences[i])

        filtered_detections = self.filter_overlapping_detections(
            person_boxes, np.array(adjusted_confidences)
        )
        return filtered_detections
class VideoProcessor:
    def __init__(self, model, temp_dir="temp_clips"):
        self.model = model
        self.temp_dir = temp_dir
        # Our target rendered video dimensions are fixed.
        self.target_height = 1920
        self.target_width = None # Will be computed from original dims.
        # These are the layout dimensions in the revideo code:
        self.layout_width = 1080
        self.layout_height = 1920
        os.makedirs(temp_dir, exist_ok=True)



    def detect_scenes(self, input_video, threshold=30.0):
        """Use scenedetect to return a list of scene segments."""
        video_manager = VideoManager([input_video])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))
        video_manager.start()
        scene_manager.detect_scenes(video_manager)
        scene_list = scene_manager.get_scene_list()
        segments = [{"start": start.get_seconds(), "end": end.get_seconds()}
                    for start, end in scene_list]
        video_manager.release()
        return segments
    def calculate_scaled_coordinates(self, box, original_height, original_width):
        """
        Convert a detection box:
        • Compute its center and dimensions.
        • Apply an upward offset (10% of the box height) so that the face (or person) is well centered.
        • Map the center from [0, original dims] to a coordinate system from -target_dim/2 to target_dim/2.
        • Clamp the result so that when applied in the renderer the video is not shifted too far.
        """
        x1, y1, x2, y2 = box
        orig_box_width = x2 - x1
        orig_box_height = y2 - y1
        # Skip very small detections.
        min_width = original_width * 0.05
        min_height = original_height * 0.05
        # if orig_box_width < min_width or orig_box_height < min_height:
        #     return None
        # Compute the center of the detection box.
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        # Shift the center upward by 10% of the box height.
        adjusted_center_y = center_y + (0.1 * orig_box_height)
        # Map the center to a coordinate system ranging from -target_dim/2 to target_dim/2.
        mapped_x = np.interp(center_x, [0, original_width], [-self.target_width/2, self.target_width/2])
        mapped_y = np.interp(adjusted_center_y, [0, original_height], [-self.target_height/2, self.target_height/2])
        # Clamp the mapped position so the video still covers the layout.
        allowed_x = (self.target_width - self.layout_width) / 2
        allowed_y = (self.target_height - self.layout_height) / 2
        mapped_x = float(np.clip(mapped_x, -allowed_x, allowed_x))
        mapped_y = float(np.clip(mapped_y, -allowed_y, allowed_y))
        # Also calculate the scaled width and height for reference.
        scaled_width = orig_box_width * (self.target_width / original_width)
        scaled_height = orig_box_height * (self.target_height / original_height)
        return {
            "position": [mapped_x, mapped_y],
            "size": [float(scaled_width), float(scaled_height)]
        }

    def generate_detection_groups(self, input_video):
        video = VideoFileClip(input_video)
        original_height = video.h
        original_width = video.w
        self.target_width = (original_width / original_height) * self.target_height

        segments = self.detect_scenes(input_video)
        print(f"Video dims: {original_width}x{original_height}")

        detection_groups = []

        def get_frame_detections(frame):
            detections_found = self.model.detect(frame)
            detection_list = []
            for det_idx, (box, conf) in enumerate(detections_found):
                scaled_coords = self.calculate_scaled_coordinates(box, original_height, original_width)
                if scaled_coords is not None:
                    detection_list.append({
                        "position": scaled_coords["position"],
                        "size": scaled_coords["size"],
                        "color": "red" if det_idx == 0 else "green"
                    })
            return detection_list

        def detections_differ(det1, det2):
            if len(det1) != len(det2):
                return True
            return False

        for seg_idx, segment in enumerate(tqdm(segments, desc="Generating Detection Groups")):
            clip = video.subclip(segment["start"], segment["end"])
            duration = segment["end"] - segment["start"]
            
            # Sample frames at start and end
            first_frame = clip.get_frame(0)
            last_frame = clip.get_frame(clip.duration - 0.1)
            
            first_detections = get_frame_detections(first_frame)
            last_detections = get_frame_detections(last_frame)

            # If detections differ, split the scene in half
            if detections_differ(first_detections, last_detections):
                mid_point = duration / 2
                
                detection_groups.append({
                    "detections": first_detections if first_detections else [{"position": [0, 0], "size": [self.target_width * 0.5, self.target_height * 0.5], "color": "red"}],
                    "duration": mid_point,
                    "start": segment["start"],
                    "end": segment["start"] + mid_point,
                    "key": seg_idx + 1
                })
                
                detection_groups.append({
                    "detections": last_detections if last_detections else [{"position": [0, 0], "size": [self.target_width * 0.5, self.target_height * 0.5], "color": "red"}],
                    "duration": duration - mid_point,
                    "start": segment["start"] + mid_point,
                    "end": segment["end"],
                    "key": seg_idx + 2
                })
            else:
                detection_groups.append({
                    "detections": first_detections if first_detections else [{"position": [0, 0], "size": [self.target_width * 0.5, self.target_height * 0.5], "color": "red"}],
                    "duration": duration,
                    "start": segment["start"],
                    "end": segment["end"],
                    "key": seg_idx + 1
                })

            del clip
            gc.collect()

        video.close()
        
        output = {
            "original_width": original_width,
            "original_height": original_height,
            "target_width": self.target_width,
            "target_height": self.target_height,
            "groups": detection_groups
        }
        return output
if __name__ == "__main__":
    input_video = "speed-2.mp4"


    model = YOLOModel()
    video_processor = VideoProcessor(model)
    detection_output = video_processor.generate_detection_groups(input_video)
    with open("./Captions/captions/src/detection.json", "w") as f:

        f.write(json.dumps(detection_output, indent=2))  ## I have updated it...make sure the fa   