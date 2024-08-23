import yt_dlp
from .Cropping import YOLOv5Model, VideoProcessor
from .VectorDB import Faiss

#-pass youtube url/video id
#-download the transcript
#-extract wisdom use groq by passing the transcript text

#-The prompt gather the Ideas and quotes from the markdown "ie the title or subtitles named Quotes and Ideas"

#use the gathered Ideas to make queries to the faiss db k=1, then pass the returned object to find neigbours.abs
#Then use a prompt like 

"""You extract surprising, insightful, and interesting information from text content. You are interested in insights related to the purpose and meaning of life, human flourishing, the role of technology in the future of humanity, artificial intelligence and its affect on humans, memes, learning, reading, books, continuous improvement, and similar topics.

{neigbours-dict}

##### look at the dict return the range of all the items which talk about the topic 

{topic} 

 return something like
Eg:Output: [2,8]. Which represents a range i.e start, finish. So only return 2 numbers, their difference should be not less than 5 ie. finish - start > 5

 DO NOT INCLUDE ANYTHING ELSE THE OUTPUT SHOULD ONLY BE THE SLICE, NO EXPLANATIONS. NO EXPLANATIONS. IT SHOULD BASICALLY BE A GOOD TIKTOK CLIP, SO PROVIDE ENOUGH CONTEXT AS WELL"""
#The dict is from the find_neighbours fx and the topic is a result from the extract wisdom ie quote or idea, so replace the dict witht the dict returned from the  find_neighbours fx and also the topic.

#-get the clip range from llm response
#-user should be able to select the clips
#-extract the clip
#-send clip to clip extractor
#-get the result



#download the video







