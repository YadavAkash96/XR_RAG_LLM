import json
from apify_client import ApifyClient
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
from tqdm import tqdm
import whisper
import yt_dlp

load_dotenv()

API_KEY = os.getenv(r"Youtube_API_KEY")
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
                "id": f"yt_{video_id}",
                'url': video_url,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'author': item['snippet']['channelTitle'],
                "platform": "YouTube"
            }
            # print(video_info)
            # print()
            videos.append(video_info)
        return videos

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure your API key is correct and the YouTube Data API v3 is enabled in your Google Cloud project.")
        return []

def discover_tiktok_videos(apify_client, query, max_results):
    """Fetches TikTok videos using an Apify Actor."""
    print(f"  -> Discovering TikTok videos for '#{query}'...")
    try:
        simple_hashtag = [qry.replace(" ", "") for qry in query]
        # print(simple_hashtag)
        run_input = {
            "excludePinnedPosts": False,
            "hashtags": simple_hashtag,
            "resultsPerPage": max_results,
            "profileScrapeSections": ["videos"],
            "profileSorting": "latest",
            "excludePinnedPosts": False,
            "searchSection": "",
            "maxProfilesPerQuery": 10,
            "scrapeRelatedVideos": False,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadAvatars": False,
            "shouldDownloadMusicCovers": False,
            "proxyCountryCode": "None",
        }
        run = apify_client.actor("GdWCkxBtKWOsKjdch").call(run_input=run_input)
        
        videos = []
        for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
            # print(item.get('webVideoUrl'))
            videos.append({
                "id": f"tt_{item.get('id')}",
                "url": item.get('webVideoUrl'),
                "title": item.get('text', 'No Title'),
                "author": item.get('authorMeta', {}).get('nickName', item.get('authorMeta', {}).get('name')), # Prefer nickName
                "platform": "TikTok"
            })
        return videos
    except Exception as e:
        print(f"    [ERROR] TikTok search failed: {e}")
        return []


def discover_instagram_reels(apify_client, query, max_results):
    """Fetches Instagram Reels using an Apify Actor."""
    print(f"  -> Searching Instagram for '#{query.replace(' ', '')}'...")
    try:
        # Use a pre-built "Actor" for scraping Instagram hashtags
        simple_hashtag = query.split(' ')[0]
        if 'curl' in query: simple_hashtag = 'dumbbellcurls'
        if 'press' in query: simple_hashtag = 'legpress'
        run_input = {
            "hashtags": [simple_hashtag],
            "resultsLimit": max_results
        }
        run = apify_client.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)

        videos = []
        for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
            if item.get("type") == "Video":
                videos.append({
                    "id": f"ig_{item.get('id')}",
                    "url": item.get('url'),
                    "title": item.get('caption', 'No Title'),
                    "author": item.get('ownerUsername'),
                    "platform": "Instagram"
                })
        return videos
    except Exception as e:
        print(f"    [ERROR] Instagram search failed: {e}")
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


def get_video_transcript(video_url,whisper_model):
    # 1. Download audio using yt-dlp
    audio_filename = "temp_audio.m4a"
    try:
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=True)
            
        
        if not os.path.exists(audio_filename):
                raise FileNotFoundError("Audio file was not created.")
        
        # 2. Transcribe audio with Whisper
        result = whisper_model.transcribe(audio_filename, fp16=False)
        transcript = result.get("text", "").strip()
        return transcript
    except Exception as e:
        print(f"\n    [WARN] Transcription failed for {video_url}. Reason: {e}")
        return None
    finally:
        if audio_filename and os.path.exists(audio_filename):
            os.remove(audio_filename)
    

if __name__ == "__main__":
    
    OUTPUT_FILENAME = "all_fitness_videos_data.jsonl"
    PLATFORMS_TO_SEARCH = ["tiktok"] #"youtube", "tiktok",
    MAX_RESULTS_PER_TERM = 6
    apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
    
    whisper_model = whisper.load_model("small") 
    
    final_video_data = []
    search_queries = ["leg press","seated row","barbell squat", "lat pulldown", "dumbbell bench press",
    "dumbbell curls", "tricep pushdown", "plank exercise", "kettlebell swing"]

    final_video_data.extend(discover_tiktok_videos(apify_client, search_queries, MAX_RESULTS_PER_TERM))
    # for term in search_queries:
    #     print(f"\n--- Discovering videos for search term: '{term}' ---")
    #     if "youtube" in PLATFORMS_TO_SEARCH:
            # final_video_data.extend(find_filtered_youtube_shorts(term, max_results=1))
    #     if "tiktok" in PLATFORMS_TO_SEARCH:
    #         final_video_data.extend(discover_tiktok_videos(apify_client, term, MAX_RESULTS_PER_TERM))
    #     if "instagram" in PLATFORMS_TO_SEARCH:
    #         videos = discover_instagram_reels(apify_client, term, MAX_RESULTS_PER_TERM)
    #         print(videos)
    #         final_video_data.extend(videos)
    
    unique_videos = list({video['url']: video for video in final_video_data}.values())
    print(f"\n--- Discovered a total of {len(unique_videos)} unique videos. ---")

    if os.path.exists(OUTPUT_FILENAME):
        print(f"Clearing existing output file: {OUTPUT_FILENAME}")
        os.remove(OUTPUT_FILENAME)

    print(f"--- Starting transcription and processing for each video ---")
    for video_data in tqdm(unique_videos, desc="Transcribing Videos"):
        transcript = get_video_transcript(video_data['url'], whisper_model)

        if transcript:
            video_data['transcript'] = transcript
            try:
                with open(OUTPUT_FILENAME, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(video_data) + '\n')
            except Exception as e:
                print(f"    [ERROR] Could not write video data to file. Reason: {e}")

            
    print(f"\n--- Extraction Complete! ---")
    print(f"Processed data has been saved to '{OUTPUT_FILENAME}'.")


