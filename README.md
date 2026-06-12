# ChessCaster AI

ChessCaster AI is a Discord voice bot that tracks live games on Chess.com, analyzes them in real-time using Stockfish, and provides highly energetic, humorous audio commentary imitating an Indian sports commentator.

## Features
- **Live Game Tracking**: Follows active chess.com games in real-time.
- **Stockfish Analysis**: Detects blunders, checks, forks, and brilliant moves.
- **LLM Commentary**: Generates dynamic commentary using NVIDIA's `meta/llama-3.1-70b-instruct`.
- **Edge TTS Speech**: Converts text to speech using `edge-tts` (Microsoft Edge Text-to-Speech) for expressive audio playback in Discord Voice Channels.

## Railway Deployment Instructions

This bot is fully containerized and deployment-ready for Railway.app.

1. Fork or push this repository to your GitHub account.
2. Log into [Railway.app](https://railway.app/) and create a new project -> **Deploy from GitHub repo**.
3. Railway will automatically detect the `railway.json` and `Dockerfile`. It will build a Linux container and automatically install `ffmpeg` and `stockfish` during the build process.
4. Go to the **Variables** tab in your Railway service and add:
   - `DISCORD_TOKEN`: Your Discord bot token.
   - `NVIDIA_API_KEY`: Your NVIDIA API key.
5. The bot will automatically use Edge TTS and generate temporary files in a `temp` directory, deleting them after playback.

## Commands
- `!watch <chess.com_url>`: Joins your voice channel and starts commentating on the live game.
- `!stop`: Stops tracking and leaves the voice channel.
- `!analysis`: Prints the current Stockfish evaluation of the watched game in the text channel.
- `!score`: Prints the current material and centipawn advantage.
