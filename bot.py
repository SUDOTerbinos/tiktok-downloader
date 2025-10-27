import logging
import os
import re
import asyncio
from uuid import uuid4

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import pyktok as pk

# --- Basic Setup ---

# Enable logging to see errors and bot activity
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

# Create a directory for temporary video downloads if it doesn't exist
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        "I can download TikTok videos for you without a watermark. "
        "Just send me a TikTok video link!\n\n"
        "Use /help to see all available commands."
    )
    await update.message.reply_html(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = (
        "<b>How to use me:</b>\n"
        "Simply send me a valid TikTok video link, and I will send the video back to you without a watermark.\n\n"
        "<b>Example links:</b>\n"
        "• https://www.tiktok.com/@username/video/1234567890123456789\n"
        "• https://vm.tiktok.com/someRandomCode/\n\n"
        "That's it! Happy downloading. ✨"
    )
    await update.message.reply_html(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages to check for TikTok URLs."""
    message_text = update.message.text
    # Regex to find TikTok URLs in the message
    tiktok_regex = r"https?://(?:www\.|vm\.)?tiktok\.com/.*"
    match = re.search(tiktok_regex, message_text)

    if not match:
        await update.message.reply_text(
            "Please send me a valid TikTok video link. "
            "Use /help for more information."
        )
        return

    url = match.group(0)
    processing_message = await update.message.reply_text("⬇️ Downloading your video, please wait...")

    try:
        # Use a unique filename to avoid conflicts
        unique_id = str(uuid4())
        # pyktok automatically names files, so we just need the directory
        pk.set_output_folder(DOWNLOAD_DIR)

        # Download the video using pyktok. It's already async!
        # The function returns the filepath of the downloaded video.
        output_path = await pk.save_tiktok(url, True)

        # Check if the video was downloaded successfully
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Video downloaded successfully to {output_path}")
            # Use a 'with' statement to ensure the file is closed properly
            with open(output_path, "rb") as video_file:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=f"Here is your video! ✨\nDownloaded with @{context.bot.username}",
                    read_timeout=120, # Increased timeout for large files
                    write_timeout=120,
                )
        else:
            raise ValueError("Download failed, file not found or is empty.")

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't download the video. The link might be invalid, "
            "the video could be private, or an internal error occurred. Please try another link."
        )
    finally:
        # Clean up: delete the temporary message and the downloaded file
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id
        )
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
            logger.info(f"Cleaned up temporary file: {output_path}")

def main() -> None:
    """Starts the bot and sets up handlers."""
    application = Application.builder().token(TOKEN).build()

    # --- Register Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
