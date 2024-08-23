import os,time
from groq import Groq
from pydantic import BaseModel
from typing import List, Dict
from prompts import extract_wisdom, clip_range_prompt  # Importing the necessary prompts
from Transcript import get_or_create_transcript
from VectorDB import Faiss
import json
import copy,curses
import pprint

class AIEditor:
    def __init__(self, api_key: str='', model: str = "llama-3.1-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.faiss = Faiss()
        self.model = model

    def _generate_response(self, prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 5000) -> str:
        if model is None:
            model = self.model

        attempts = 5
        for attempt in range(attempts):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if attempt < attempts - 1:
                    time.sleep(5)
                else:
                    raise e

    def extract_wisdom(self, transcript_text: str) -> str:
        prompt = extract_wisdom.replace("{transcript_text}", transcript_text)
        return self._generate_response(prompt)

    def gather_ideas_and_quotes(self, markdown_text: str) -> Dict[str, List[str]]:
        lines = markdown_text.split("\n")
        organized_content = {}
        current_section = None

        for line in lines:
            if (line.startswith("**") and line.endswith("**")) or (line.startswith("# ")):
                current_section = line.strip("*# ").strip()
                organized_content[current_section] = []
            elif current_section:
                line_content = line.strip("* ").strip()
                if line_content:
                    organized_content[current_section].append(line_content)

        return organized_content

    def generate_clip_range(self, neighbors_dict: Dict, topic: str, video_id: str) -> Dict[str, any]:
        prompt = clip_range_prompt.replace("{neigbours-dict}", str(neighbors_dict)).replace("{topic}", topic)
        clip_range_text = self._generate_response(prompt, model="llama-3.1-70b-versatile", temperature=0)
        clip_range = eval(clip_range_text)

        start = neighbors_dict[clip_range[0]]['start']
        end = neighbors_dict[clip_range[1]]['start'] + neighbors_dict[clip_range[1]]['duration']

        youtube_link = f"https://www.youtube.com/watch?v={video_id}&t={int(start)}s"

        return {
            "start_time": start,
            "end_time": end,
            "clip_range": clip_range,
            "youtube_link": youtube_link
        }

    def process_transcript(self, video_id: str) -> Dict[str, List[str]]:
        transcripts, transcript_text = get_or_create_transcript(video_id=video_id)
        self.faiss.add_transcripts(json.loads(transcripts), video_id)
        wisdom_markdown = self.extract_wisdom(transcript_text)
        return self.gather_ideas_and_quotes(wisdom_markdown)

    def search_and_process(self, query: str, k: int = 1) -> Dict[int, Dict]:
        if not isinstance(query, str):
            raise ValueError("The query must be a string.")

        results = self.faiss.search(query, k=k)
        all_items = []
        filtered = []
        for item in results:
            all_items.append(item['metadata'])
            temp_item = copy.deepcopy(item)
            del temp_item['metadata']['original_transcripts']
            filtered.append(temp_item['metadata'])

        items_dict = {i + 1: item for i, item in enumerate(all_items)}
        temp = {i + 1: item for i, item in enumerate(filtered)}

        print("\nItems Dictionary:")
        for i, item in temp.items():
            print(f"{i}: {item['text']}")

        return items_dict

    def find_neighbors_for_selected_items(self, items_dict: Dict[int, Dict]) -> Dict[int, Dict]:
        print("\nSelect an item number to find neighbors (or 'q' to quit):")
        selection = input().strip()

        if selection.lower() == 'q':
            return None

        try:
            item_number = int(selection)
            if item_number not in items_dict:
                print("Invalid selection. Please choose a valid item number.")
                return None

            selected_item = items_dict[item_number]
            neighbors = self.faiss.find_neighbors(selected_item)

            combined_transcripts = selected_item['original_transcripts']
            for neighbor in neighbors:
                combined_transcripts.extend(neighbor['original_transcripts'])

            seen_starts = set()
            unique_transcripts = []
            for transcript in combined_transcripts:
                if transcript['start'] not in seen_starts:
                    unique_transcripts.append(transcript)
                    seen_starts.add(transcript['start'])

            sorted_transcripts = sorted(unique_transcripts, key=lambda x: x['start'])
            numbered_transcripts = {i + 1: transcript for i, transcript in enumerate(sorted_transcripts)}

            print("\nCombined and Sorted Transcripts:")
            for i, transcript in numbered_transcripts.items():
                print(f"{i}: {transcript['text']}")

            return numbered_transcripts

        except ValueError:
            print("Please enter a valid number or 'q' to quit.")
            return None

