import cv2
import gc
import torch
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip
from tqdm import tqdm
import os
import warnings
import logging

# Suppress warnings and notices
# warnings.filterwarnings("ignore", category=UserWarning, module="torch")
# logging.getLogger("moviepy").setLevel(logging.ERROR)


class YOLOv5Model:
    def __init__(self):
        # Load model and suppress unnecessary messages
        with torch.no_grad():
            self.model = torch.hub.load(
                "ultralytics/yolov5", "yolov5n", pretrained=True
            )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        print(f"Using device: {self.device}")

    def detect(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.model(frame_rgb)
        return results.xyxy[0].cpu().numpy()


class VideoProcessor:
    def __init__(self, model, temp_dir="temp_clips"):
        self.model = model
        self.boxes = []
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def process_video(self, input_video, output_video, sample_rate=1):
        video = VideoFileClip(input_video)
        target_ratio = 9 / 16
        new_height = int(video.w / target_ratio)

        # Process video in chunks and write intermediate clips to disk
        clips = []
        segment_index = 0
        chunks = []
        segments = list(self.segment_video(video, sample_rate))
        no_segments = len(segments)

        for segment in tqdm(segments, desc="Merging boxes"):
            self.boxes.extend(segment["person_detections"])
            # print(self.boxes)

        for segment in tqdm(segments, desc="Processing video"):
            clip = video.subclip(segment["start"], segment["end"])
            merged_boxes = self.merge_detections(segment)
            if len(merged_boxes) > 1:
                if self.are_boxes_overlapping(merged_boxes[0], merged_boxes[1]):
                    merged_boxes = [merged_boxes[0]]

            if len(merged_boxes) == 1:
                processed_clip = self._process_single_person(
                    clip, merged_boxes[0], new_height
                )
            elif len(merged_boxes) > 1:
                processed_clip = self._process_split_screen(
                    clip, merged_boxes, new_height
                )
            else:
                continue

            chunks.append(processed_clip)
            if len(chunks) % 20 == 0 or segments.index(segment) + 1 == no_segments:
                chunked_video = concatenate_videoclips(chunks)
                chunk_file = os.path.join(self.temp_dir, f"clip_{segment_index}.mp4")
                chunked_video.write_videofile(
                    chunk_file,
                    # codec="h264_nvenc",
                    audio_codec="aac",
                )
                chunked_video.close()
                segment_index += 1
                chunks = []
                clips.append(chunk_file)

            # Clean up memory
            del clip, processed_clip
            gc.collect()

        # Concatenate final video from intermediate clips
        collection = []
        for clip in clips:
            collection.append(VideoFileClip(clip))
        final_video = concatenate_videoclips(collection)
        final_video.write_videofile(output_video, audio_codec="aac")
        final_video.close()
        # Clean up temporary files

    def segment_video(self, video,  ):
        index = 0
        for t in np.arange(0, video.duration, sample_rate):
            frame = video.get_frame(t)
            detections = self.model.detect(frame)
            person_detections = [d[:4] for d in detections if int(d[5]) == 0]

            if person_detections:
                yield {
                    "index": index,
                    "start": t,
                    "end": min(t + sample_rate, video.duration),
                    "person_detections": person_detections,
                }
                index += 1

    def merge_detections(self, segment):
        person_detections = segment["person_detections"]
        return self.merge_boxes(person_detections, self.boxes)

    @staticmethod
    def merge_boxes(boxes, all_boxes):
        if not boxes:
            return []

        merged = []
        while boxes:
            box = boxes.pop()
            for i in range(len(all_boxes)):
                if VideoProcessor.are_boxes_overlapping(box, all_boxes[i]):
                    box = VideoProcessor.union_boxes(box, all_boxes[i])
            merged.append(box)
        return merged

    @staticmethod
    def union_boxes(box1, box2):
        x1 = min(box1[0], box2[0])
        y1 = min(box1[1], box2[1])
        x2 = max(box1[2], box2[2])
        y2 = max(box1[3], box2[3])
        return [x1, y1, x2, y2]

    @staticmethod
    def are_boxes_overlapping(box1, box2, threshold=0.5):
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        x1_inter = max(x1_1, x1_2)
        y1_inter = max(y1_1, y1_2)
        x2_inter = min(x2_1, x2_2)
        y2_inter = min(y2_1, y2_2)

        inter_width = max(0, x2_inter - x1_inter)
        inter_height = max(0, y2_inter - y1_inter)
        intersection_area = inter_width * inter_height

        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)

        union_area = box1_area + box2_area - intersection_area
        iou = intersection_area / union_area if union_area != 0 else 0

        return iou > threshold

    def _process_single_person(self, clip, body, new_height):
        x1, y1, x2, y2 = body
        body_width, body_height = x2 - x1, y2 - y1
        crop_factor = max(clip.w / body_width, new_height / body_height)
        new_w, new_h = int(body_width * crop_factor), int(body_height * crop_factor)
        x_center, y_center = (x1 + x2) / 2, (y1 + y2) / 2

        cropped_clip = clip.crop(
            x1=max(0, x_center - new_w / 2),
            y1=max(0, y_center - new_h / 2),
            x2=min(clip.w, x_center + new_w / 2),
            y2=min(clip.h, y_center + new_h / 2),
        ).resize(height=new_height)
        return CompositeVideoClip(
            [cropped_clip.set_position("center")], size=(clip.w, new_height)
        )

    def _process_split_screen(self, clip, bodies, new_height):
        split_clips = []
        for body in bodies:
            x1, y1, x2, y2 = body
            cropped_clip = clip.crop(x1=x1, y1=y1, x2=x2, y2=y2).resize(
                height=new_height // 2
            )
            split_clips.append(cropped_clip)

        return CompositeVideoClip(
            [
                split_clips[0].set_position(("center", "top")),
                split_clips[1].set_position(("center", "bottom")),
            ],
            size=(clip.w, new_height),
        )

    def cleanup_temp_files(self):
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)


# Main execution
if __name__ == "__main__":
    input_video = "output001.mp4"
    output_video = "sample.mp4"

    model = YOLOv5Model()
    video_processor = VideoProcessor(model)
    video_processor.process_video(input_video, output_video)
