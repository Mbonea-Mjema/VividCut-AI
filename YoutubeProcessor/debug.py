from ultralytics import YOLO
import torch

class PersonDetector:
    def __init__(self):
        self.model = YOLO("yolov8s.pt")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
    def detect_people(self, input_path):
        # Run inference on video with visualization
        results = self.model.predict(
            source=input_path,
            classes=[0],  # Only detect people
            stream=True,            
            show=True,
            save=True,
            conf=0.7,
            max_det=2,  # Maximum 2 detections per frame
            # frames=30  # Process only 30 frames
        )
        
        # for r in results:
        #     pass  # Results are automatically visualized and saved

if __name__ == "__main__":
    input_video = "sample.webm"
    
    detector = PersonDetector()
    detector.detect_people(input_video)