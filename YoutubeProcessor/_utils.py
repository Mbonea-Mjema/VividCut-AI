from moviepy.editor import VideoFileClip
from groq import Groq
import yt_dlp


def download_video(url, filename):
    ydl_opts = {
        "format": "worst[ext=mp4]",  # This selects the worst quality mp4
        "outtmpl": filename,
        "merge_output_format": "mp4",
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])



def segment_video(video_path, segments):
    video = VideoFileClip(video_path)
    clip = []
    for i, segment in enumerate(segments):
        file_name = f"output{str(i).zfill(3)}.mp4"
        start_time = segment["start_time"]
        end_time = segment["end_time"]
        duration = segment["duration"]
        if duration < 20:
            continue
        subclip = video.subclip(start_time, end_time)
        subclip.write_videofile(file_name, codec="libx264", audio_codec="aac")
        clip.append(file_name)
    return clip



    # Input selection from the user
    print("\nSelect an item number to find neighbors (or 'q' to quit):")
    selection = input().strip()

    if selection.lower() == 'q':
        return None  # Exit the function if 'q' is entered

    try:
        item_number = int(selection)
        if item_number not in items_dict:
            print("Invalid selection. Please choose a valid item number.")
            return None
        
        # Find neighbors for the selected item
        selected_item = items_dict[item_number]
        neighbors = faiss_instance.find_neighbors(selected_item)

        # Combine the original_transcripts from the selected item and its neighbors
        combined_transcripts = selected_item['original_transcripts']
        for neighbor in neighbors:
            combined_transcripts.extend(neighbor['original_transcripts'])

        # Remove duplicates based on 'start' time
        seen_starts = set()
        unique_transcripts = []
        for transcript in combined_transcripts:
            if transcript['start'] not in seen_starts:
                unique_transcripts.append(transcript)
                seen_starts.add(transcript['start'])

        # Sort unique_transcripts by start time
        sorted_transcripts = sorted(unique_transcripts, key=lambda x: x['start'])

        # Create a numbered dictionary of the sorted transcripts
        numbered_transcripts = {i + 1: transcript for i, transcript in enumerate(sorted_transcripts)}

        print("\nCombined and Sorted Transcripts:")
        pprint.pprint(numbered_transcripts)
        
        return numbered_transcripts
    
    except ValueError:
        print("Please enter a valid number or 'q' to quit.")
        return None