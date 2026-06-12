# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies: FFmpeg (for Discord Voice) and Stockfish (for Chess Engine)
RUN apt-get update && \
    apt-get install -y ffmpeg stockfish && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variable default for Stockfish (Ubuntu/Debian default path)
ENV STOCKFISH_PATH=/usr/games/stockfish

# Command to run the bot
CMD ["python", "-u", "bot.py"]
