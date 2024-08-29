import cv2
import gc
import torch
import numpy as np
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    vfx,
)
from tqdm import tqdm
import os
from ultralytics import YOLO


class YOLOModel:
    def __init__(self):
        self.model = YOLO("yolov5nu.pt")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        print(f"Using device: {self.device}")

    def detect(self, frame):
        results = self.model(frame, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        return [(box, conf) for box, conf in zip(boxes, confidences) if conf > .7]


class VideoProcessor:
    def __init__(self, model, temp_dir="temp_clips"):
        self.model = model
        self.detections = []
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def process_video(self, input_video, output_video, sample_rate=0.1):
        video = VideoFileClip(input_video)
        total_frames = int(video.fps * video.duration)
        frame_sample_interval = int(1 / sample_rate)

        target_ratio = 9 / 16
        new_height = int(video.w / target_ratio)

        clips = []
        segment_index = 0
        chunks = []
        segments = list(self.segment_video(video, frame_sample_interval, total_frames))
        no_segments = len(segments)

        for segment in tqdm(segments, desc="Processing video"):
            clip = video.subclip(segment["start"], segment["end"])
            detections = segment["detections"]
            print(detections)

            if len(detections) == 1:
                processed_clip = self._process_single_face(
                    clip, detections[0][0], new_height
                )
            elif len(detections) >= 2:
                processed_clip = self._process_two_faces(
                    clip, [d[0] for d in detections[:2]], new_height
                )
            else:
                processed_clip = self._process_center_clip(clip, new_height)

            chunks.append(processed_clip)
            if len(chunks) % 20 == 0 or segments.index(segment) + 1 == no_segments:
                chunked_video = concatenate_videoclips(chunks)
                chunk_file = os.path.join(self.temp_dir, f"clip_{segment_index}.mp4")
                chunked_video.write_videofile(chunk_file, audio_codec="aac")
                chunked_video.close()
                segment_index += 1
                chunks = []
                clips.append(chunk_file)

            del clip, processed_clip
            gc.collect()

        collection = [VideoFileClip(clip) for clip in clips]
        final_video = concatenate_videoclips(collection)
        final_video.write_videofile(output_video, audio_codec="aac")
        final_video.close()

    def segment_video(self, video, frame_sample_interval, total_frames):
        segments = []
        for i in tqdm(
            range(0, total_frames, frame_sample_interval), desc="Generating segments"
        ):
            t = i / video.fps
            frame = video.get_frame(t)
            detections = self.model.detect(frame)
            segments.append(
                {
                    "start": t,
                    "end": min(t + frame_sample_interval / video.fps, video.duration),
                    "detections": detections,
                }
            )
        return segments

    def _process_single_face(self, clip, box, new_height):
        x1, y1, x2, y2 = box
        face_center_x = (x1 + x2) / 2

        crop_width = new_height * 9 / 16
        crop_x1 = max(0, face_center_x - crop_width / 2)
        crop_x2 = min(clip.w, crop_x1 + crop_width)

        if crop_x2 - crop_x1 < crop_width:
            crop_x1 = max(0, crop_x2 - crop_width)

        cropped_clip = clip.crop(x1=crop_x1, width=crop_width).resize(height=new_height)

        # Draw face box
        face_box_clip = cropped_clip

        return CompositeVideoClip(
            [face_box_clip.set_position("center")], size=(clip.w, new_height)
        )


    def _process_center_clip(self, clip, new_height):
        # Calculate center crop area
        crop_width = new_height * 9 / 16
        crop_x1 = (clip.w - crop_width) / 2
        crop_x2 = crop_x1 + crop_width

        cropped_clip = clip.crop(x1=crop_x1, width=crop_width).resize(height=new_height)
        return CompositeVideoClip(
            [cropped_clip.set_position("center")], size=(clip.w, new_height)
        )

    def _draw_face_box(self, get_frame, t, x1, y1, x2, y2):
        frame = get_frame(t).copy()
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        return frame

    def cleanup_temp_files(self):
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def _process_two_faces(self, clip, boxes, new_height):
        boxes = sorted(boxes, key=lambda x: x[0])  # Sort by x-coordinate

        half_height = new_height //2
        crop_width = half_height * 9 / 16

        clips = []
        for i, (x1, y1, x2, y2) in enumerate(boxes[:2]):
            face_center_x = (x1 + x2) / 2

            crop_x1 = max(0, face_center_x - crop_width / 2)
            crop_x2 = min(clip.w, crop_x1 + crop_width)

            if crop_x2 - crop_x1 < crop_width:
                crop_x1 = max(0, crop_x2 - crop_width)

            cropped_clip = clip.crop(x1=crop_x1, width=crop_width).resize(
                height=half_height
            )

            # Draw face box
            face_box_clip = cropped_clip
            clips.append(face_box_clip.set_position(("center", ["top", "bottom"][i])))

        return CompositeVideoClip(clips, size=(clip.w, new_height))






# Main execution
if __name__ == "__main__":
    input_video = "downloaded_video_segment_1.mp4"
    output_video = "sample_v5nu.mp4"

    model = YOLOModel()
    video_processor = VideoProcessor(model)
    video_processor.process_video(input_video, output_video, sample_rate=0.1)
    video_processor.cleanup_temp_files()
