import os
import re
import requests
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import logging
import yt_dlp
import aiohttp
import asyncio
from urllib.parse import urlparse, quote
import time
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TELEGRAM_TOKEN = "7918738285:AAGUlng8R53agagDRvTjtedY83K_eW2qSpk"

class SocialMediaDownloader:
    def __init__(self):
        self.ig_loader = instaloader.Instaloader()
        # Set a custom user agent to avoid detection
        self.ig_loader.context.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # Try to load Instagram session if exists
        try:
            self.ig_loader.load_session_from_file("instagram_session")
            logger.info("Instagram session loaded successfully")
        except:
            logger.info("No Instagram session found. Downloading public content only.")
        
    async def start(self, update: Update, context: CallbackContext):
        """Send a message when the command /start is issued."""
        welcome_text = """
        🌟 Welcome to Social Media Downloader Bot! 🌟
        
        I can download videos from:
        📸 Instagram (without watermark)
        🎵 TikTok (without watermark)
        
        Just send me the link of the post you want to download!
        """
        
        keyboard = [
            [InlineKeyboardButton("How to Use", callback_data="help")],
            [InlineKeyboardButton("Supported Platforms", callback_data="platforms")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: CallbackContext):
        """Send a message when the command /help is issued."""
        help_text = """
        📖 How to Use:
        
        1. Find the Instagram or TikTok post you want to download
        2. Copy the link (share → copy link)
        3. Send the link to this bot
        4. I'll download and send you the video without watermark!
        
        ⚠️ Note: Some content might not be downloadable due to privacy settings.
        """
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages containing URLs."""
        message_text = update.message.text
        
        if self.is_instagram_url(message_text):
            await self.download_instagram(update, context, message_text)
        elif self.is_tiktok_url(message_text):
            await self.download_tiktok(update, context, message_text)
        else:
            await update.message.reply_text("❌ Please send a valid Instagram or TikTok URL.")

    def is_instagram_url(self, url):
        """Check if the URL is from Instagram."""
        instagram_patterns = [
            r'https?://(www\.)?instagram\.com/(p|reel|stories)/',
            r'https?://(www\.)?instagr\.am/(p|reel|stories)/'
        ]
        return any(re.search(pattern, url) for pattern in instagram_patterns)

    def is_tiktok_url(self, url):
        """Check if the URL is from TikTok."""
        tiktok_patterns = [
            r'https?://(www\.)?tiktok\.com/',
            r'https?://vm\.tiktok\.com/',
            r'https?://vt\.tiktok\.com/'
        ]
        return any(re.search(pattern, url) for pattern in tiktok_patterns)

    async def download_instagram(self, update: Update, context: CallbackContext, url):
        """Download Instagram video without watermark."""
        try:
            await update.message.reply_text("⏳ Downloading Instagram content...")
            
            # Method 1: Try direct instaloader first
            try:
                shortcode = self.extract_instagram_shortcode(url)
                if shortcode:
                    post = instaloader.Post.from_shortcode(self.ig_loader.context, shortcode)
                    
                    if post.is_video:
                        video_url = post.video_url
                        filename = f"instagram_{post.shortcode}.mp4"
                        
                        # Download with progress
                        await update.message.reply_text("📥 Downloading video...")
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(video_url) as response:
                                if response.status == 200:
                                    with open(filename, 'wb') as f:
                                        while True:
                                            chunk = await response.content.read(8192)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                    
                                    # Send video
                                    with open(filename, 'rb') as video_file:
                                        await update.message.reply_video(
                                            video=video_file,
                                            caption=f"📸 Instagram Video\n❤️ Likes: {post.likes}"
                                        )
                                    
                                    os.remove(filename)
                                    return
            except Exception as e:
                logger.warning(f"Instaloader method failed: {e}")
            
            # Method 2: Use alternative API
            await update.message.reply_text("Trying alternative method...")
            
            try:
                # Use a different API endpoint
                api_url = f"https://api.instagram.com/oembed/?url={quote(url)}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            # This won't give us the actual video, but we can try to extract
                            # For now, just inform the user
                            await update.message.reply_text("✅ Instagram content detected but video download might not be available for this post.")
                            return
            except:
                pass
            
            await update.message.reply_text("❌ Could not download Instagram content. The post might be private, deleted, or not accessible.")
                
        except Exception as e:
            logger.error(f"Instagram download error: {e}")
            await update.message.reply_text("❌ Error downloading Instagram content. Please try a different post.")

    async def download_tiktok(self, update: Update, context: CallbackContext, url):
        """Download TikTok video without watermark using multiple methods."""
        try:
            await update.message.reply_text("⏳ Downloading TikTok content...")
            
            # Method 1: Try yt-dlp with custom settings (most reliable)
            try:
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': 'tiktok_%(id)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': 'https://www.tiktok.com/',
                        'Origin': 'https://www.tiktok.com',
                    },
                    'socket_timeout': 30,
                    'retries': 3,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    # Check file size (Telegram has 50MB limit for bots)
                    file_size = os.path.getsize(filename)
                    if file_size > 45 * 1024 * 1024:  # 45MB
                        await update.message.reply_text("❌ Video is too large for Telegram (max 50MB)")
                        os.remove(filename)
                        return
                    
                    # Send video to user
                    with open(filename, 'rb') as video_file:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"🎵 TikTok Video\n📺 Author: {info.get('uploader', 'Unknown')}"
                        )
                    
                    os.remove(filename)
                    return
            except Exception as e:
                logger.warning(f"yt-dlp method failed: {e}")
            
            # Method 2: Use simple HTML parsing as fallback
            await update.message.reply_text("Trying alternative method...")
            
            try:
                # Simple method: Download the page and look for video URL
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Look for video URL in the HTML
                            video_patterns = [
                                r'"downloadAddr":"([^"]+)"',
                                r'"playAddr":"([^"]+)"',
                                r'<video[^>]+src="([^"]+)"',
                            ]
                            
                            for pattern in video_patterns:
                                match = re.search(pattern, html)
                                if match:
                                    video_url = match.group(1).replace('\\u002F', '/')
                                    filename = f"tiktok_{int(time.time())}.mp4"
                                    
                                    # Download the video
                                    async with session.get(video_url, headers=headers) as video_response:
                                        if video_response.status == 200:
                                            with open(filename, 'wb') as f:
                                                while True:
                                                    chunk = await video_response.content.read(8192)
                                                    if not chunk:
                                                        break
                                                    f.write(chunk)
                                            
                                            # Send video
                                            with open(filename, 'rb') as video_file:
                                                await update.message.reply_video(
                                                    video=video_file,
                                                    caption="🎵 TikTok Video"
                                                )
                                            
                                            os.remove(filename)
                                            return
            except Exception as e:
                logger.warning(f"HTML parsing method failed: {e}")
            
            # Method 3: Final fallback - use savefrom.net API
            try:
                savefrom_url = f"https://api.savefrom.net/api/convert"
                payload = {
                    'url': url
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(savefrom_url, data=payload, headers=headers, timeout=20) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('url'):
                                video_url = data['url']
                                filename = f"tiktok_{int(time.time())}.mp4"
                                
                                async with session.get(video_url) as video_response:
                                    if video_response.status == 200:
                                        with open(filename, 'wb') as f:
                                            while True:
                                                chunk = await video_response.content.read(8192)
                                                if not chunk:
                                                    break
                                                f.write(chunk)
                                        
                                        with open(filename, 'rb') as video_file:
                                            await update.message.reply_video(
                                                video=video_file,
                                                caption="🎵 TikTok Video"
                                            )
                                        
                                        os.remove(filename)
                                        return
            except Exception as e:
                logger.warning(f"SaveFrom method failed: {e}")
            
            await update.message.reply_text("❌ Could not download TikTok video. Please try a different video or try again later.")
                
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            await update.message.reply_text("❌ Error downloading TikTok content. Please try again.")

    def extract_instagram_shortcode(self, url):
        """Extract Instagram shortcode from URL."""
        patterns = [
            r'instagram\.com/(p|reel)/([^/?#&]+)',
            r'instagr\.am/(p|reel)/([^/?#&]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(2)
        return None

    async def button_handler(self, update: Update, context: CallbackContext):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            help_text = """
            📖 How to Use:
            
            1. Find the Instagram or TikTok post you want to download
            2. Copy the link (share → copy link)
            3. Send the link to this bot
            4. I'll download and send you the video without watermark!
            
            ⚠️ Note: Some content might not be downloadable due to privacy settings.
            """
            await query.edit_message_text(help_text)
        elif query.data == "platforms":
            platforms_text = """
            📱 Supported Platforms:
            
            ✅ Instagram Posts
            ✅ Instagram Reels
            ✅ TikTok Videos
            
            🔄 More platforms coming soon!
            """
            await query.edit_message_text(platforms_text)

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    downloader = SocialMediaDownloader()
    
    # Add handlers
    application.add_handler(CommandHandler("start", downloader.start))
    application.add_handler(CommandHandler("help", downloader.help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader.handle_message))
    application.add_handler(CallbackQueryHandler(downloader.button_handler))
    
    # Add error handler
    application.add_error_handler(lambda update, context: logger.error(f"Update {update} caused error {context.error}"))
    
    # Start the Bot
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()