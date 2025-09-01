import json
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
import whisper
import yt_dlp

load_dotenv()

API_KEY = os.getenv("Youtube_API_KEY")
# print("API_KEY:", API_KEY)
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def find_filtered_youtube_shorts(query, max_results=5, order="viewCount", lang="en", region_code="GB"):
    """
    Finds YouTube shorts with advanced filters for order, language, and region.

    Args:
        query (str): The search term (e.g., "how to use lat pulldown").
        max_results (int): The maximum number of results to return.
        order (str): The sorting method. Options: "viewCount", "date", "rating", "relevance".
        lang (str): The ISO 639-1 language code (e.g., "en" for English).
        region_code (str): The ISO 3166-1 alpha-2 country code (e.g., "US", "GB").
    """
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

        search_response = youtube.search().list(
            q=f"{query} #shorts",
            part='snippet',
            type='video',
            videoDuration='short',
            maxResults=max_results,
            order=order,                     
            relevanceLanguage=lang,          
            regionCode=region_code           

        ).execute()

        videos = []
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            video_url = f"https://www.youtube.com/shorts/{video_id}"
            
            video_info = {
                'id': video_id,
                'url': video_url,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'channel_id': item['snippet']['channelId'],
                'channel_title': item['snippet']['channelTitle']
            }
            # print(video_info)
            # print()
            videos.append(video_info)
        return videos

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure your API key is correct and the YouTube Data API v3 is enabled in your Google Cloud project.")
        return []


def is_likely_expert_youtube(channel_id, api_key):
    EXPERT_KEYWORDS = ["certified trainer", "cpt", "nasm", "cscs", "coach", "physiotherapist"]
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)

    channel_response = youtube.channels().list(
        id=channel_id,
        part='snippet'
    ).execute()

    description = channel_response['items'][0]['snippet']['description'].lower()

    for keyword in EXPERT_KEYWORDS:
        if keyword in description:
            return True
    return False


def get_video_transcript(video_url):
    # 1. Download audio using yt-dlp
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': '%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        audio_filename = f"{info['id']}.m4a"

    # 2. Transcribe audio with Whisper
    model = whisper.load_model("small") 
    result = model.transcribe(audio_filename, fp16=False)
    transcript = result["text"]

    # 3. Clean up the audio file
    os.remove(audio_filename)

    return transcript

if __name__ == "__main__":
    
    OUTPUT_FILENAME = "fitness_videos_data.jsonl"

    final_video_data = []
    search_queries = ["leg press tutorial", "seated row form", "dumbbell curl technique"]
    
    if os.path.exists(OUTPUT_FILENAME):
        print(f"Clearing existing output file: {OUTPUT_FILENAME}")
        os.remove(OUTPUT_FILENAME)

    for query in search_queries:
        print(f"--- Searching for videos with query: '{query}' ---")
        youtube_videos = find_filtered_youtube_shorts(query, max_results=15)
        
        if not youtube_videos:
            print("  -> No videos found for this query.")
            continue

        for video in youtube_videos:
            print(f"  [Expert Found] '{video['channel_title']}'. Processing video: '{video['title']}'")
            transcript = get_video_transcript(video['url'])
            
            if not transcript:
                    print(f"    -> Skipping video due to failed transcription.")
                    continue
            
            video['transcript'] = transcript
            video['platform'] = 'YouTube'
            final_video_data.append(video)
            try:
                with open(OUTPUT_FILENAME, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(video) + '\n')
                print(f"    -> Successfully processed and saved to {OUTPUT_FILENAME}")
            except Exception as e:
                print(f"    -> ERROR: Could not write to file. {e}")
            
    print("\nExtraction complete. Data saved to fitness_videos_data.json")


