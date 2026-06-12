import discord
from discord.ext import commands, tasks
import logging
import os
import asyncio
from dotenv import load_dotenv

from chess_tracker import ChessTracker
from analysis import ChessAnalyzer
from commentary import generate_commentary_text, generate_speech
from audio_player import AudioPlayer

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('ChessCaster')

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# State
tracker = ChessTracker()
analyzer = ChessAnalyzer()
audio_player = AudioPlayer()
is_watching = False
current_voice = "en-IN-PrabhatNeural"

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info("ChessCaster AI is ready!")

@bot.command(name='watch')
async def watch(ctx, url: str):
    """Starts watching a chess.com game and providing audio commentary."""
    global is_watching
    
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first.")
        return

    if is_watching:
        await ctx.send("I am already watching a game! Use !stop first.")
        return

    # Join voice channel
    channel = ctx.author.voice.channel
    
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
        vc = ctx.voice_client
    else:
        vc = await channel.connect()
        
    audio_player.set_voice_client(vc)

    # Set up game tracking
    if not tracker.set_game_url(url):
        await ctx.send("Invalid chess.com live game URL. Please provide a valid URL like https://www.chess.com/game/live/1234567")
        return

    analyzer.reset()
    is_watching = True
    
    await ctx.send("ChessCaster is now live.")
    
    if not poll_game_loop.is_running():
        poll_game_loop.start(ctx.channel)

@bot.command(name='stop')
async def stop(ctx):
    """Stops watching the game and leaves the voice channel."""
    global is_watching
    
    is_watching = False
    if poll_game_loop.is_running():
        poll_game_loop.cancel()
        
    audio_player.stop()
    
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        
    await ctx.send("🛑 Stopped tracking the game and left the voice channel.")

@bot.command(name='analysis')
async def analysis(ctx):
    """Prints the current raw Stockfish evaluation."""
    if not is_watching:
        await ctx.send("I am not currently watching a game.")
        return
        
    score_str = analyzer.get_score_string()
    await ctx.send(f"Current Evaluation: **{score_str}**")

@bot.command(name='score')
async def score(ctx):
    """Alias for analysis."""
    await analysis(ctx)

@bot.command(name='voice')
async def set_voice(ctx, voice_name: str):
    """Sets the commentator voice. Available: prabhat, neerja"""
    global current_voice
    voice_name = voice_name.lower()
    if voice_name == "prabhat":
        current_voice = "en-IN-PrabhatNeural"
        await ctx.send("🎙️ Voice set to **Prabhat** (Male).")
    elif voice_name == "neerja":
        current_voice = "en-IN-NeerjaNeural"
        await ctx.send("🎙️ Voice set to **Neerja** (Female).")
    else:
        await ctx.send("⚠️ Available voices: `prabhat`, `neerja`")

@bot.command(name='say')
async def say(ctx, *, message: str):
    """Speaks the provided message in the voice channel."""
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first.")
        return

    # Join voice channel
    channel = ctx.author.voice.channel
    
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
        vc = ctx.voice_client
    else:
        vc = await channel.connect()
        
    audio_player.set_voice_client(vc)

    # Generate Audio
    audio_path = await generate_speech(message, voice=current_voice)
    
    if audio_path:
        audio_player.add_to_queue(audio_path)
        await ctx.send(f"🗣️ Saying: {message}")
    else:
        await ctx.send("Failed to generate speech.")

@bot.command(name='debuggame')
async def debuggame(ctx, url: str):
    """Debugs the tracking logic for a chess.com URL."""
    temp_tracker = ChessTracker()
    if not temp_tracker.set_game_url(url):
        await ctx.send("Invalid URL format.")
        return
    
    game_url = getattr(temp_tracker, "full_game_url", f"https://www.chess.com/game/live/{temp_tracker.game_id}")
    await ctx.send(f"**Game ID**: {temp_tracker.game_id}\n**Endpoint**: {game_url}")
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(game_url, headers=temp_tracker.headers) as resp:
                status = resp.status
                body = await resp.text()
                snippet = body[:500].replace('`', '')
                
                await ctx.send(f"**Status**: {status}\n**Body Snippet**:\n```html\n{snippet}\n```")
    except Exception as e:
        await ctx.send(f"**Error**: {e}")

@tasks.loop(seconds=3)
async def poll_game_loop(text_channel):
    """Background loop that polls chess.com and processes new moves."""
    global is_watching
    
    if not is_watching:
        return
        
    state = await tracker.poll_game_state()
    if not state:
        return
        
    if "error" in state:
        logger.error(f"Tracking stopped due to error: {state['error']}")
        await text_channel.send(f"❌ Stopped tracking: {state['error']}")
        is_watching = False
        poll_game_loop.cancel()
        audio_player.stop()
        if text_channel.guild.voice_client:
            await text_channel.guild.voice_client.disconnect()
        return
        
    new_moves = state.get("new_moves", [])
    
    if new_moves:
        logger.info(f"New moves detected: {new_moves}")
        
        # We push all new moves and get events
        events = analyzer.push_moves(new_moves)
        
        for event in events:
            # We only generate commentary for significant events to avoid spamming the channel
            if event["is_significant"]:
                logger.info(f"Significant event detected for move {event['move']}: {event}")
                
                # Let people know in text channel too
                if event["is_checkmate"]:
                    await text_channel.send(f"🏆 **CHECKMATE!** {event['player']} has won the game!")
                elif event["is_blunder"]:
                    await text_channel.send(f"🚨 **BLUNDER DETECTED!** {event['player']} just blundered ({event['eval_diff']/100.0:.2f})!")
                    
                # Generate Commentary
                commentary_text = await generate_commentary_text(event, state["white"], state["black"])
                
                # Generate Audio
                audio_path = await generate_speech(commentary_text, voice=current_voice)
                
                if audio_path:
                    audio_player.add_to_queue(audio_path)
                    
    if state.get("is_over"):
        logger.info("Game is over.")
        await text_channel.send("The game has concluded! Use `!stop` to disconnect me.")
        is_watching = False
        poll_game_loop.cancel()

if __name__ == "__main__":
    if not TOKEN:
        logger.critical("DISCORD_TOKEN is missing from .env!")
    else:
        bot.run(TOKEN)
