import numpy as np
import os
import pickle
from transformers import AutoTokenizer, AutoModel
import torch, copy
from Transcript import get_or_create_transcript
import faiss

class Faiss:
    def __init__(self, model_name='Alibaba-NLP/gte-large-en-v1.5', chunk_duration=120, overlap_duration=40):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)

        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.index = None
        self.metadata = []
        self.embeddings = None
        self.video_id = None

        # Ensure the embeddings directory exists
        self.base_dir = 'embeddings'
        os.makedirs(self.base_dir, exist_ok=True)

    def _create_embeddings(self, texts):
        inputs = self.tokenizer(texts,return_tensors='pt')
        with torch.no_grad():
            embeddings = self.model(**inputs).last_hidden_state.mean(dim=1).cpu().numpy()
        return embeddings

    def _chunk_transcript(self, transcripts):
        chunks = []
        current_chunk = {
            'text': '',
            'start': transcripts[0]['start'],
            'end': None,
            'duration': 0,
            'original_transcripts': []
        }
        overlap_duration = 0
        overlap_buffer = []

        for transcript in transcripts:
            current_chunk['text'] += transcript['text'] + ' '
            current_chunk['duration'] += transcript['duration']
            current_chunk['end'] = transcript['start'] + transcript['duration']
            current_chunk['original_transcripts'].append(transcript)

            if current_chunk['duration'] >= self.chunk_duration:
                chunks.append(current_chunk.copy())

                # Prepare overlap buffer
                overlap_buffer = []
                overlap_duration = 0
                for buffer_item in reversed(current_chunk['original_transcripts']):
                    overlap_buffer.insert(0, buffer_item)
                    overlap_duration += buffer_item['duration']
                    if overlap_duration >= self.overlap_duration:
                        break

                current_chunk = {
                    'text': '',
                    'start': overlap_buffer[0]['start'],
                    'end': None,
                    'duration': 0,
                    'original_transcripts': []
                }

                # Pre-fill current_chunk with overlap_buffer content
                for item in overlap_buffer:
                    current_chunk['text'] += item['text'] + ' '
                    current_chunk['duration'] += item['duration']
                    current_chunk['original_transcripts'].append(item)

        # Add remaining chunk if it exists
        if current_chunk['duration'] > 0:
            chunks.append(current_chunk.copy())

        return chunks

    def _save_data(self):
        if self.video_id:
            folder = os.path.join(self.base_dir, self.video_id)
            os.makedirs(folder, exist_ok=True)

            # Save metadata using pickle
            with open(os.path.join(folder, 'metadata.pkl'), 'wb') as f:
                pickle.dump(self.metadata, f)

            # Save embeddings using pickle
            with open(os.path.join(folder, 'embeddings.pkl'), 'wb') as f:
                pickle.dump(self.embeddings, f)

    def _load_data(self, video_id):
        folder = os.path.join(self.base_dir, video_id)
        if os.path.exists(folder):
            # Load metadata using pickle
            with open(os.path.join(folder, 'metadata.pkl'), 'rb') as f:
                self.metadata = pickle.load(f)

            # Load embeddings using pickle
            with open(os.path.join(folder, 'embeddings.pkl'), 'rb') as f:
                self.embeddings = pickle.load(f)

            self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
            self.index.add(self.embeddings)

            self.video_id = video_id
            return True
        return False

    def add_transcripts(self, transcripts, video_id):
        self.video_id = video_id
        
        if not self._load_data(video_id):
            chunks = self._chunk_transcript(transcripts)

            texts = [chunk['text'] for chunk in chunks]
            self.embeddings = self._create_embeddings(texts)

            if self.index is None:
                dim = self.embeddings.shape[1]
                self.index = faiss.IndexFlatL2(dim)

            self.index.add(self.embeddings)
            self.metadata.extend(chunks)
            self._save_data()

    def search(self, query, k=5):
        # Create query embedding
        query_embedding = self._create_embeddings([query])
        
        # Perform search
        distances, indices = self.index.search(query_embedding, k)
        
        # Retrieve metadata
        results = []
        for i in range(k):
            index = indices[0][i]
            results.append({
                'distance': distances[0][i],
                'metadata': self.metadata[index]
            })
        
        return results

    def find_neighbors(self, target_chunk):
        """
        Find neighboring chunks of a given chunk.

        :param target_chunk: The chunk object for which to find neighbors.
        :return: A list of neighboring chunks' metadata.
        """
        if target_chunk not in self.metadata:
            raise ValueError("Chunk not found in metadata.")
        
        chunk_index = self.metadata.index(target_chunk)
        neighbors = []

        for i, chunk in enumerate(self.metadata):
            if i == chunk_index:
                continue

            # Check if chunks overlap or are adjacent
            if (
                chunk['start'] < target_chunk['end'] and 
                chunk['end'] > target_chunk['start']
            ):
                neighbors.append(chunk)
        
        return neighbors
