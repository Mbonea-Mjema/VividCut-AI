import json
import os
import sys
from youtube_transcript_api import YouTubeTranscriptApi

def get_or_create_transcript(video_id):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create the main Video_Data folder
    main_folder = os.path.join(script_dir, "Video_Data")
    os.makedirs(main_folder, exist_ok=True)
    
    # Create a folder for the specific video_id inside Video_Data
    video_folder = os.path.join(main_folder, video_id)
    
    json_filename = os.path.join(video_folder, f"{video_id}_transcript.json")
    text_filename = os.path.join(video_folder, f"{video_id}_transcript.txt")
    
    # Check if the folder already exists
    if os.path.exists(video_folder):
        print(f"Transcript for video ID {video_id} already exists. Loading from files...")
        with open(json_filename, 'r', encoding='utf-8') as json_file:
            json_str = json_file.read()
        with open(text_filename, 'r', encoding='utf-8') as text_file:
            full_text = text_file.read()
        return json_str, full_text
    
    try:
        # Create the folder for the new video
        os.makedirs(video_folder)
        
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine all text from the transcript
        full_text = " ".join(i["text"] for i in transcript)
        
        # Write JSON file
        with open(json_filename, 'w', encoding='utf-8') as json_file:
            json.dump(transcript, json_file, ensure_ascii=False, indent=4)
        
        # Write text file
        with open(text_filename, 'w', encoding='utf-8') as text_file:
            text_file.write(full_text)
        
        print(f"Transcript saved in folder: {video_folder}")
        print(f"JSON file: {os.path.basename(json_filename)}")
        print(f"Text file: {os.path.basename(text_filename)}")
        
        return json.dumps(transcript), full_text
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None, None