from urllib import response

import requests
import os
import base64
import sys
import time
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("NM_API_KEY")


invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = False
query = "Describe in detail what you see in the image."

kApiKey = api_key

# ext: {mime, media_type}
kSupportedList = {
   "png": ["image/png", "image_url"],
   "jpg": ["image/jpeg", "image_url"],
   "jpeg": ["image/jpeg", "image_url"],
   "webp": ["image/webp", "image_url"],
   "mp4": ["video/mp4", "video_url"],
   "webm": ["video/webm", "video_url"],
   "mov": ["video/mov", "video_url"]
}

def get_extension(filename):
   _, ext = os.path.splitext(filename)
   ext = ext[1:].lower()
   return ext

def mime_type(ext):
   return kSupportedList[ext][0]

def media_type(ext):
   return kSupportedList[ext][1]

def encode_media_base64(media_file):
   """Encode media file to base64 string"""
   with open(media_file, "rb") as f:
       return base64.b64encode(f.read()).decode("utf-8")

def chat_with_media(infer_url, media_files, query: str, stream: bool = False, max_retries: int = 3, timeout: int = 60):
    """
    Send a request to the vision model with retry logic and timeout.
    
    Args:
        infer_url: API endpoint URL
        media_files: List of media file paths
        query: Text query/prompt
        stream: Whether to stream the response
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        
    Returns:
        Response object from the API
    """
    assert isinstance(media_files, list), f"{media_files}"
   
    has_video = False
   
    # Build content based on whether we have media files
    if len(media_files) == 0:
        # Text-only mode
        content = query
    else:
        # Build content array with text and media
        content = [{"type": "text", "text": query}]
       
        for media_file in media_files:
            ext = get_extension(media_file)
            assert ext in kSupportedList, f"{media_file} format is not supported"
           
            media_type_key = media_type(ext)
            if media_type_key == "video_url":
                has_video = True
           
            print(f"Encoding {media_file} as base64...")
            base64_data = encode_media_base64(media_file)
           
            # Add media to content array
            media_obj = {
                "type": media_type_key,
                media_type_key: {
                    "url": f"data:{mime_type(ext)};base64,{base64_data}"
                }
            }
            content.append(media_obj)
       
        if has_video:
            assert len(media_files) == 1, "Only single video supported."
   
    headers = {
        "Authorization": f"Bearer {kApiKey}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if stream:
        headers["Accept"] = "text/event-stream"

    # Add system message with appropriate prompt
    # Videos only support /no_think, images support both
   
    system_prompt = "/no_think" if has_video else "/think"
   
   
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": content,
        }
    ]
    payload = {
        "max_tokens": 4096,
        "temperature": 1,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "messages": messages,
        "stream": stream,
    #    "model": "nvidia/nemotron-nano-12b-v2-vl",
        "model": "nvidia/nemotron-nano-12b-v2-vl", #If Nemotron Nano is not working, can switch to this model which also supports vision inputs
    }

    # Retry logic with exponential backoff
    last_exception = None
    for attempt in range(max_retries):
        try:
            print(f"Attempting API request (attempt {attempt + 1}/{max_retries}) with timeout={timeout}s")
            response = requests.post(infer_url, headers=headers, json=payload, stream=stream, timeout=timeout)
            return response
        except requests.exceptions.Timeout as e:
            last_exception = e
            print(f"Request timeout (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached, giving up.")
        except requests.exceptions.RequestException as e:
            last_exception = e
            print(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached, giving up.")
    
    # If we got here, all retries failed
    if last_exception:
        raise last_exception
    else:
        raise Exception("Unknown error occurred during API request")

    

if __name__ == "__main__":
   """ Usage:
       python test.py                                    # Text-only
       python test.py sample.mp4                         # Single video
       python test.py sample1.png sample2.png            # Multiple images
   """

   media_samples = list(sys.argv[1:])
   chat_with_media(invoke_url, media_samples, query, stream)


def GetDescriptionFromLLM(image_path: str, max_retries: int = 3, timeout: int = 60) -> str:
    """
    Get a description of an image using the Nemotron vision model.
    
    Args:
        image_path: Path to the image file
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        
    Returns:
        str: Description of the image
    """
    query = "Describe in detail what you see in the image. Provide as much detail as possible about objects, colors, text, and any other visual elements."
    
    try:
        response = chat_with_media(invoke_url, [image_path], query, stream=False, max_retries=max_retries, timeout=timeout)
        
        # Log response details for debugging
        print(f"API Response Status: {response.status_code}")
        if response.text:
            print(f"API Response: {response.text[:500]}")
        
        if response.status_code == 200:
            result = response.json()
            # Extract the description from the response
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
        
        return f"Image analysis failed: {response.status_code} - {response.text[:200]}"
    except requests.exceptions.Timeout:
        return "Error: Image analysis timed out after {} seconds. The server is taking too long to respond. Please try again with a smaller image or try later.".format(timeout)
    except requests.exceptions.RequestException as e:
        return f"Error: Failed to connect to vision service: {str(e)}"
    except Exception as e:
        print(f"Exception in GetDescriptionFromLLM: {e}")
        return f"Error processing image: {str(e)}"