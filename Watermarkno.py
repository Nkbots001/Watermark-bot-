import os
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
import ffmpeg
import subprocess
import json

# Load environment variables
load_dotenv()

# Configuration from .env
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
DEFAULT_WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Your Text")
DEFAULT_FONT_SIZE = int(os.getenv("FONT_SIZE", 24))
DEFAULT_FONT_COLOR = os.getenv("FONT_COLOR", "white")
DEFAULT_FONT_FILE = os.getenv("FONT_FILE", "arial.ttf")
DEFAULT_POSITION = os.getenv("POSITION", "bottom_right")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100)) * 1024 * 1024  # 100MB

# Settings file
SETTINGS_FILE = "watermark_settings.json"

app = Client("watermark_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

class WatermarkSettings:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    pass
        return {
            "text": DEFAULT_WATERMARK_TEXT,
            "font_size": DEFAULT_FONT_SIZE,
            "font_color": DEFAULT_FONT_COLOR,
            "position": DEFAULT_POSITION
        }

    def save_settings(self):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f)

    def get(self, key):
        return self.settings.get(key, self.load_settings().get(key))

    def update(self, **kwargs):
        self.settings.update(kwargs)
        self.save_settings()

settings = WatermarkSettings()

def get_position_args(position):
    positions = {
        "top_left": {"x": "10", "y": "10"},
        "top_right": {"x": "(w-text_w)-10", "y": "10"},
        "bottom_left": {"x": "10", "y": "(h-text_h)-10"},
        "bottom_right": {"x": "(w-text_w)-10", "y": "(h-text_h)-10"},
        "center": {"x": "(w-text_w)/2", "y": "(h-text_h)/2"}
    }
    return positions.get(position, positions["bottom_right"])

async def generate_thumbnail(input_path, output_path="thumbnail.jpg", time="00:00:01"):
    try:
        (
            ffmpeg
            .input(input_path, ss=time)
            .output(output_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path if os.path.exists(output_path) else None
    except ffmpeg.Error as e:
        print(f"Thumbnail error: {e.stderr.decode()}")
        return None

async def add_watermark_to_video(input_path, output_path):
    pos = get_position_args(settings.get("position"))
    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f"drawtext=text='{settings.get('text')}':fontfile={DEFAULT_FONT_FILE}:"
                   f"fontcolor={settings.get('font_color')}:fontsize={settings.get('font_size')}:"
                   f"x={pos['x']}:y={pos['y']}",
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Video watermark error: {str(e)}")
        return False

async def add_watermark_to_image(input_path, output_path):
    pos = get_position_args(settings.get("position"))
    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f"drawtext=text='{settings.get('text')}':fontfile={DEFAULT_FONT_FILE}:"
                   f"fontcolor={settings.get('font_color')}:fontsize={settings.get('font_size')}:"
                   f"x={pos['x']}:y={pos['y']}",
            '-y',
            output_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Image watermark error: {str(e)}")
        return False

@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "Welcome to the Watermark Bot!\n"
        "Send me a video or image and I'll add a text watermark.\n\n"
        "Commands:\n"
        "/watermark - Customize watermark settings\n"
        "/current - Show current settings\n\n"
        f"Current settings:\n"
        f"Text: {settings.get('text')}\n"
        f"Position: {settings.get('position')}\n"
        f"Font size: {settings.get('font_size')}\n"
        f"Color: {settings.get('font_color')}"
    )

@app.on_message(filters.command("current") & filters.private)
async def current_settings(client: Client, message: Message):
    await message.reply_text(
        "Current watermark settings:\n\n"
        f"Text: {settings.get('text')}\n"
        f"Position: {settings.get('position')}\n"
        f"Font size: {settings.get('font_size')}\n"
        f"Color: {settings.get('font_color')}"
    )

@app.on_message(filters.command("watermark") & filters.private)
async def watermark_settings(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Change Text", callback_data="change_text")],
        [InlineKeyboardButton("Change Position", callback_data="change_position")],
        [InlineKeyboardButton("Change Font Size", callback_data="change_size")],
        [InlineKeyboardButton("Change Color", callback_data="change_color")],
        [InlineKeyboardButton("Reset to Default", callback_data="reset_settings")]
    ])
    await message.reply_text(
        "Watermark Settings:\n\n"
        f"Current text: {settings.get('text')}\n"
        f"Current position: {settings.get('position')}\n"
        f"Current font size: {settings.get('font_size')}\n"
        f"Current color: {settings.get('font_color')}",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.id
    
    if data == "change_text":
        await client.send_message(
            chat_id,
            "Please send the new watermark text:",
            reply_to_message_id=message_id
        )
        await callback_query.answer()
        
    elif data == "change_position":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Top Left", callback_data="pos_top_left")],
            [InlineKeyboardButton("Top Right", callback_data="pos_top_right")],
            [InlineKeyboardButton("Bottom Left", callback_data="pos_bottom_left")],
            [InlineKeyboardButton("Bottom Right", callback_data="pos_bottom_right")],
            [InlineKeyboardButton("Center", callback_data="pos_center")]
        ])
        await client.edit_message_text(
            chat_id,
            message_id,
            "Select watermark position:",
            reply_markup=keyboard
        )
        await callback_query.answer()
        
    elif data == "change_size":
        await client.send_message(
            chat_id,
            "Please send the new font size (number between 10 and 100):",
            reply_to_message_id=message_id
        )
        await callback_query.answer()
        
    elif data == "change_color":
        await client.send_message(
            chat_id,
            "Please send the new font color (e.g., white, black, red, #FFFFFF):",
            reply_to_message_id=message_id
        )
        await callback_query.answer()
        
    elif data == "reset_settings":
        settings.update(
            text=DEFAULT_WATERMARK_TEXT,
            font_size=DEFAULT_FONT_SIZE,
            font_color=DEFAULT_FONT_COLOR,
            position=DEFAULT_POSITION
        )
        await client.edit_message_text(
            chat_id,
            message_id,
            "Settings reset to default values!"
        )
        await callback_query.answer("Settings reset!")
        
    elif data.startswith("pos_"):
        position = data[4:]
        settings.update(position=position)
        await client.edit_message_text(
            chat_id,
            message_id,
            f"Watermark position set to: {position}"
        )
        await callback_query.answer(f"Position set to {position}")

@app.on_message(filters.private & (filters.text | filters.video | filters.photo))
async def handle_messages(client: Client, message: Message):
    if message.text and message.reply_to_message:
        reply = message.reply_to_message
        if "watermark text" in reply.text:
            settings.update(text=message.text)
            await message.reply_text(f"Watermark text updated to: {message.text}")
            
        elif "font size" in reply.text:
            try:
                size = int(message.text)
                if 10 <= size <= 100:
                    settings.update(font_size=size)
                    await message.reply_text(f"Font size updated to: {size}")
                else:
                    await message.reply_text("Please enter a number between 10 and 100")
            except ValueError:
                await message.reply_text("Please enter a valid number")
                
        elif "font color" in reply.text:
            settings.update(font_color=message.text)
            await message.reply_text(f"Font color updated to: {message.text}")
            
    elif message.video or message.photo:
        await process_media(client, message)

async def process_media(client: Client, message: Message):
    try:
        is_video = bool(message.video)
        file_type = "video" if is_video else "image"
        file_size = message.video.file_size if is_video else message.photo.file_size
        
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(f"File is too large (max {MAX_FILE_SIZE//(1024*1024)}MB allowed).")
            return
            
        sent_msg = await message.reply_text(f"Downloading {file_type}...")
        
        unique_id = message.video.file_unique_id if is_video else message.photo.file_unique_id
        input_path = f"downloads/input_{unique_id}.{'mp4' if is_video else 'jpg'}"
        output_path = f"downloads/output_{unique_id}.{'mp4' if is_video else 'jpg'}"
        thumbnail_path = f"downloads/thumb_{unique_id}.jpg"
        
        os.makedirs("downloads", exist_ok=True)

        try:
            await message.download(
                file_name=input_path,
                progress=progress_callback,
                progress_args=(sent_msg, "Downloading")
            )
        except Exception as e:
            await sent_msg.edit_text(f"Download failed: {str(e)}")
            return

        if is_video:
            await sent_msg.edit_text("Generating thumbnail...")
            await generate_thumbnail(input_path, thumbnail_path)

        await sent_msg.edit_text(f"Adding watermark to {file_type}...")
        
        success = False
        if is_video:
            success = await add_watermark_to_video(input_path, output_path)
        else:
            success = await add_watermark_to_image(input_path, output_path)

        if not success:
            await sent_msg.edit_text(f"Failed to add watermark to {file_type}.")
            return

        await sent_msg.edit_text(f"Uploading watermarked {file_type}...")
        try:
            if is_video:
                await message.reply_video(
                    video=output_path,
                    thumb=thumbnail_path if os.path.exists(thumbnail_path) else None,
                    caption="Here's your watermarked video!",
                    progress=progress_callback,
                    progress_args=(sent_msg, "Uploading")
                )
            else:
                await message.reply_photo(
                    photo=output_path,
                    caption="Here's your watermarked image!"
                )
        except Exception as e:
            await sent_msg.edit_text(f"Upload failed: {str(e)}")
            return

        await sent_msg.delete()
        for file_path in [input_path, output_path, thumbnail_path]:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {str(e)}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")

async def progress_callback(current, total, message: Message, stage):
    try:
        percent = min(int(current * 100 / total), 100)
        await message.edit_text(f"{stage}... {percent}%")
    except:
        pass

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("Bot is running...")
    app.run()
