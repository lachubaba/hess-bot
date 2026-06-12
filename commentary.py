import aiohttp
import logging
import os
import uuid
import json
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('ChessCaster')

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

COMMENTATOR_PROMPT = """You are an extremely energetic, funny, and dramatic Indian sports commentator covering a live chess match.
Your job is to provide highly entertaining, sarcastic, and hype commentary on specific chess moves.
You mix English with occasional Indian slang (e.g., 'Arre bhai', 'kya baat hai', 'gajab', 'khel khatam').
Keep your commentary short (1-3 sentences maximum). Make it punchy and impactful.
Do not over-explain the chess mechanics, focus on the HYPE, the blunders, and the drama!
Never repeat the exact same phrases. Keep it fresh.
"""

async def generate_commentary_text(event: dict, white: str, black: str) -> str:
    """Uses NVIDIA LLM to generate text commentary based on the event."""
    if not NVIDIA_API_KEY:
        logger.error("No NVIDIA_API_KEY found.")
        return "Oh my god, what a move! Unbelievable!"

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    # Construct the context
    context = f"Match: {white} (White) vs {black} (Black).\n"
    context += f"Player to move: {event['player']}\n"
    context += f"Move played: {event['move']}\n"
    
    if event["is_checkmate"]:
        context += "Situation: CHECKMATE! The game is over!\n"
    elif event["is_blunder"]:
        context += f"Situation: MASSIVE BLUNDER! Evaluation dropped by {abs(event['eval_diff']/100.0):.2f} points!\n"
    elif event["is_check"]:
        context += "Situation: CHECK!\n"
    elif event["is_capture"] and abs(event["eval"]) > 300:
        context += "Situation: Brutal capture!\n"
    else:
        context += "Situation: A brilliant, unexpected move!\n"

    context += "\nGive me 1-3 sentences of explosive Indian-style sports commentary for this exact moment."

    payload = {
        "model": "meta/llama-3.1-70b-instruct",
        "temperature": 0.8,
        "max_tokens": 150,
        "messages": [
            {"role": "system", "content": COMMENTATOR_PROMPT},
            {"role": "user", "content": context}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"LLM API Error {resp.status}: {await resp.text()}")
                    return "What a dramatic turn of events!"
    except Exception as e:
        logger.error(f"Failed to generate commentary: {e}")
        return "What a dramatic turn of events!"

import edge_tts
from datetime import datetime

async def generate_speech(text: str) -> str:
    """
    Uses Microsoft Edge TTS to convert text to speech.
    Returns the file path to the generated MP3 file.
    """
    # Ensure temp directory exists
    os.makedirs("temp", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"temp/commentary_{timestamp}_{uuid.uuid4().hex[:4]}.mp3"
    
    voice = "en-IN-PrabhatNeural"
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        return filename
    except Exception as e:
        logger.error(f"Failed to generate Edge TTS speech: {e}")
        return None
