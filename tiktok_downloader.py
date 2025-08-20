import requests
import re
import json

class TikTokDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_tiktok_video(self, url):
        """Get TikTok video without watermark using API."""
        try:
            # Use ssstik.io API
            api_url = "https://www.tiktok.com/@yeuphimzz/video/7237370304337628442"
            
            data = {
                'id': url,
                'locale': 'en',
                'tt': 'your_tt_token_here'  # You might need to get this from the website
            }
            
            response = requests.post(api_url, data=data)
            
            if response.status_code == 200:
                # Parse the response to get download link
                # This might need adjustment based on the actual API response
                download_url = self.parse_response(response.text)
                return download_url
            return None
            
        except Exception as e:
            print(f"TikTok API error: {e}")
            return None
    
    def parse_response(self, response_text):
        """Parse the API response to extract download URL."""
        # This is a placeholder - you'll need to adjust based on actual API response
        try:
            data = json.loads(response_text)
            return data.get('download_url')
        except:
            # Try to find URL in text
            pattern = r'(https?://[^\s]+\.mp4)'
            match = re.search(pattern, response_text)
            return match.group(1) if match else None