
# VividCut-AI

<img src="editor_pic.webp" alt="Dave the Video Editor" width="200"/>

Welcome to **VividCut-AI**! This repository provides a powerful tool for video editing using AI-powered technology. With VividCut-AI, you can efficiently edit videos by passing a YouTube video ID and leveraging the power of FFmpeg and Python.

## Workflow Overview

Below is a visual representation of how VividCut-AI processes video clips:

<img src="Untitled-2023-08-28-1608.png" alt="VividCut-AI Workflow" width="700"/>

### Workflow Description

1. **YouTube Link Processor**: The user inputs a YouTube link, which is processed to extract the video's transcript.

2. **Transcript Chunking**: The transcript is chunked into smaller parts with overlapping. Each chunk is 120 seconds of the audio transcript, with an overlapping of 40 seconds between chunks. This is used to create the Faiss Index.

3. **Faiss Index**: The Faiss Index is created from the chunks and is used to efficiently search through the transcript data.

4. **LLM Interaction**: The user queries the system, selecting a quote, idea, story, or custom detail to extract. The LLM (Large Language Model) takes the query, processes the relevant chunks from the Faiss Index, and identifies the exact time range where the video should be cut.

5. **Video Processor**: The video processor uses the time range identified by the LLM to cut the clip, track faces, and crop the video accordingly.

6. **Output**: The final video clip is processed and outputted, ready for use.

## Requirements

Before you can use VividCut-AI, make sure you have the following dependencies installed:

- **FFmpeg**: VividCut-AI relies on FFmpeg for video processing. You can install it using the following commands:

    ```bash
    sudo apt-get update
    sudo apt-get install ffmpeg
    ```

- **Python Packages**: All required Python packages are listed in the `requirements.txt` file. To install them, run:

    ```bash
    pip install -r requirements.txt
    ```

## Installation

To get started with VividCut-AI, follow these steps:

1. **Clone the Repository**:

    ```bash
    git clone https://github.com/yourusername/VividCut-AI.git
    cd VividCut-AI
    ```

2. **Install the Dependencies**:

    Make sure FFmpeg is installed on your system, then install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

VividCut-AI provides a command-line interface (CLI) for easy video editing. To use the tool, run the following command:

```bash
python CLI.py --video_id <YOUTUBE_VIDEO_ID>
```

Replace `<YOUTUBE_VIDEO_ID>` with the ID of the YouTube video you want to edit.

## Example

Here’s an example of how to use VividCut-AI:

```bash
python CLI.py --video_id dQw4w9WgXcQ
```

This command will process the video with the given ID using the VividCut-AI pipeline.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributions

Contributions are welcome! Feel free to open an issue or submit a pull request with your improvements or bug fixes.

## Contact

If you have any questions or suggestions, please feel free to reach out.

---

Thank you for using VividCut-AI! We hope it makes your video editing process smooth and efficient.
