import discord
import asyncio
import os
import logging
from collections import deque

logger = logging.getLogger('ChessCaster')

class AudioPlayer:
    def __init__(self):
        self.voice_client = None
        self.queue = deque()
        self.is_playing = False
        self._play_task = None

    def set_voice_client(self, vc: discord.VoiceClient):
        self.voice_client = vc

    def add_to_queue(self, filepath: str):
        """Adds an audio file to the playback queue."""
        if not filepath or not os.path.exists(filepath):
            return
            
        self.queue.append(filepath)
        
        if not self.is_playing and self.voice_client and self.voice_client.is_connected():
            self._start_playback()

    def _start_playback(self):
        if not self.queue:
            self.is_playing = False
            return

        if self.voice_client and self.voice_client.is_connected() and not self.voice_client.is_playing():
            self.is_playing = True
            filepath = self.queue.popleft()
            
            logger.info(f"Playing audio: {filepath}")
            
            try:
                # Assuming ffmpeg is in system PATH
                source = discord.FFmpegPCMAudio(filepath)
                
                # We use a lambda to pass the filepath to the cleanup callback
                self.voice_client.play(
                    source, 
                    after=lambda e: self._on_playback_finished(e, filepath)
                )
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                self._cleanup_file(filepath)
                self.is_playing = False
                self._start_playback() # Try next

    def _on_playback_finished(self, error, filepath: str):
        if error:
            logger.error(f"Playback error: {error}")
            
        self._cleanup_file(filepath)
        self.is_playing = False
        
        # Schedule the next track to play
        if self.queue:
            asyncio.run_coroutine_threadsafe(self._async_start_playback(), self.voice_client.loop)

    async def _async_start_playback(self):
        self._start_playback()

    def _cleanup_file(self, filepath: str):
        """Deletes the temporary audio file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Cleaned up {filepath}")
        except Exception as e:
            logger.error(f"Failed to cleanup file {filepath}: {e}")

    def stop(self):
        """Stops playback and clears queue."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            
        while self.queue:
            filepath = self.queue.popleft()
            self._cleanup_file(filepath)
            
        self.is_playing = False
