import curses
import os
import json
import re
import sys
from typing import Dict, List
from AIEditor import AIEditor  # Assuming AIEditor is defined in a separate module
from _utils import download_video_segments  # Importing the download function
from Cropping import VideoProcessor, YOLOModel  # Importing the video processing classes

class CLI:
    def __init__(self, ai_editor: AIEditor, cache_file: str = "llm_cache.json"):
        self.ai_editor = ai_editor
        self.cache_file = cache_file
        self.llm_cache = self.load_cache()
        self.model = YOLOModel()  # Initialize the YOLO model
        self.video_processor = VideoProcessor(self.model)  # Initialize video processor

    def load_cache(self) -> Dict[str, str]:
        """Loads the cached LLM responses from a JSON file."""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                return json.load(f)
        return {}

    def save_cache(self) -> None:
        """Saves the current LLM cache to a JSON file."""
        with open(self.cache_file, "w") as f:
            json.dump(self.llm_cache, f)

    def cache_llm_response(self, prompt: str, response: str) -> None:
        """Caches the LLM response with the prompt as the key."""
        self.llm_cache[prompt] = response
        self.save_cache()

    def get_cached_response(self, prompt: str) -> str:
        """Retrieves a cached LLM response for a given prompt, if it exists."""
        return self.llm_cache.get(prompt, None)

    def curses_menu(self, stdscr, items, title="Select an option", allow_custom=False, allow_back=False):
        curses.curs_set(0)
        current_row = 0

        menu_items = items.copy()
        if allow_back:
            menu_items.insert(0, "Go back")
        if allow_custom:
            menu_items.append("Enter a custom topic...")

        def print_menu(stdscr, selected_row_idx):
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            stdscr.addstr(0, 0, title, curses.A_BOLD)

            for idx, row in enumerate(menu_items):
                if len(row) > w - 4:
                    row = row[:w - 7] + "..."

                x = 2
                y = idx + 2

                if y >= h:
                    break

                if idx == selected_row_idx:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(y, x, row)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(y, x, row)

            stdscr.refresh()

        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        print_menu(stdscr, current_row)

        while True:
            key = stdscr.getch()

            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(menu_items) - 1:
                current_row += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                selected_option = menu_items[current_row]
                if allow_back and selected_option == "Go back":
                    return "back"
                elif allow_custom and selected_option == "Enter a custom topic...":
                    stdscr.clear()
                    stdscr.addstr(0, 0, "Enter your custom topic: ")
                    curses.echo()
                    custom_topic = stdscr.getstr(1, 0).decode("utf-8").strip()
                    curses.noecho()
                    return custom_topic if custom_topic else None
                else:
                    return selected_option
            print_menu(stdscr, current_row)

    def select_topic_from_wisdom(self, wisdom_json: Dict[str, List[str]]) -> str:
        while True:
            sections = list(wisdom_json.keys())
            sections.append("Custom Search")
            selected_section = curses.wrapper(
                self.curses_menu,
                sections,
                title="Select a section",
                allow_custom=False,
                allow_back=False
            )
            if not selected_section:
                print("No section selected. Exiting selection.")
                return None

            if selected_section == "Custom Search":
                custom_query = input("Enter your custom search query: ").strip()
                return custom_query

            while True:
                topics = wisdom_json.get(selected_section, [])
                selected_topic = curses.wrapper(
                    self.curses_menu,
                    topics,
                    title=f"Select a topic from '{selected_section}'",
                    allow_custom=True,
                    allow_back=True
                )
                if selected_topic == "back":
                    break
                elif selected_topic:
                    return selected_topic
                else:
                    print("No topic selected. Returning to section selection.")
                    break

    def download_and_clip_video(self, video_url, segments):
        """Handles downloading and clipping the video based on selected segments."""
        # Step 1: Download the video
        video_filename = "downloaded_video"
        print(f"\nDownloading segments video from {video_url}...")
        files=download_video_segments(video_url, segments,video_filename)

        for file in files:
            # Optionally, combine the clips into a final video
            output_video = f"{files.index(file)}_final_video.mp4"
            self.video_processor.process_video(file, output_video)

        print(f"\nVideo processing complete. Final video saved as {output_video}.")

    def extract_video_id(self, url: str) -> str:
        """Extract the video ID from a full YouTube URL."""
        video_id = None
        match = re.match(r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
        if match:
            video_id = match.group(1)
        return video_id

    def run(self):
        print("Welcome to the AI Editor CLI!")

        if len(sys.argv) > 1:
            video_link = sys.argv[1].strip()
        else:
            video_link = input("Enter the YouTube video link: ").strip()

        video_id = self.extract_video_id(video_link)
        if not video_id:
            print("Invalid YouTube link. Exiting.")
            return

        print("\nProcessing transcript...")
        wisdom_json = self.ai_editor.process_transcript(video_id)
        if not wisdom_json:
            print("Failed to process transcript.")
            return

        while True:
            selected_topic = self.select_topic_from_wisdom(wisdom_json)
            if not selected_topic:
                print("No topic selected. Exiting.")
                break

            # Check cache for existing response
            cached_response = self.get_cached_response(selected_topic)
            if cached_response:
                print(f"\nUsing cached response for topic: '{selected_topic}'")
                response = cached_response
            else:
                print(f"\nSearching for relevant content for topic: '{selected_topic}'")
                response = self.ai_editor.search_and_process(selected_topic, k=1)
                if response:
                    self.cache_llm_response(selected_topic, response)
                else:
                    print("No relevant content found.")
                    continue

            items_dict = response
            neighbors_dict = self.ai_editor.find_neighbors_for_selected_items(items_dict)

            if neighbors_dict:
                clip_info = self.ai_editor.generate_clip_range(neighbors_dict, selected_topic, video_id)
                if clip_info:
                    print("\nGenerated Clip Information:")
                    print(f"Start Time: {clip_info['start_time']} seconds")
                    print(f"End Time: {clip_info['end_time']} seconds")
                    print(f"YouTube Link: {clip_info['youtube_link']}")

                    # Ask user if they want to download and clip the video
                    download_choice = input("Do you want to download and clip this video? (y/n): ").strip().lower()
                    if download_choice == 'y':
                        segments = [{
                            "start_time": clip_info['start_time'],
                            "end_time": clip_info['end_time'],
                            "duration": clip_info['end_time'] - clip_info['start_time']
                        }]
                        self.download_and_clip_video(clip_info['youtube_link'], segments)
                else:
                    print("Failed to generate clip information.")
            else:
                print("No neighbors found for the selected item.")

            another = input("\nDo you want to select another topic? (y/n): ").strip().lower()
            if another != 'y':
                print("Exiting the AI Editor CLI. Goodbye!")
                break

if __name__ == "__main__":
    # Initialize AIEditor with your API key
    api_key = "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"  # Replace with your actual API key
    ai_editor = AIEditor(api_key=api_key)

    # Initialize and run the CLI
    cli = CLI(ai_editor)
    cli.run()
