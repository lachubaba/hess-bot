import re
import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger('ChessCaster')

class ChessTracker:
    def __init__(self):
        self.game_id = None
        self.last_move_count = 0
        self.headers = {
            "User-Agent": "ChessCasterBot/1.0 (Discord Voice Bot)"
        }
        self.white_player = "White"
        self.black_player = "Black"

    def set_game_url(self, url: str) -> bool:
        """Parses the chess.com URL to extract the game ID."""
        # Supports:
        # https://www.chess.com/game/live/{game_id}
        # https://www.chess.com/live/game/{game_id}
        # https://www.chess.com/game/{game_id}
        match = re.search(r'chess\.com/(?:live/game|game/live|game)/(\d+)', url)
        if match:
            self.game_id = match.group(1)
            self.full_game_url = f"https://www.chess.com/game/live/{self.game_id}"
            self.last_move_count = 0
            logger.info(f"Tracking game ID: {self.game_id}")
            return True
        return False

    async def poll_game_state(self) -> dict:
        """
        Polls the HTML of the main game page and extracts moves via Regex.
        Returns a dictionary with new moves if any, or None.
        """
        if not self.game_id:
            return None

        # Directly fetch the HTML page
        url = getattr(self, "full_game_url", f"https://www.chess.com/game/live/{self.game_id}")
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Requesting URL: {url}")
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status != 200:
                        body_snippet = (await resp.text())[:200]
                        logger.error(f"Failed to fetch game state. URL: {url} | Status: {resp.status} | Body: {body_snippet}")
                        
                        if resp.status == 404:
                            return {"error": "404 Not Found - The game URL is invalid."}
                            
                        return None
                        
                    html = await resp.text()
                    
                    # Extract players
                    white_match = re.search(r'\{"color":"white","username":"([^"]+)"', html) or re.search(r'"whitePlayer":\{.*?"username":"([^"]+)"', html)
                    if white_match:
                        self.white_player = white_match.group(1)
                        
                    black_match = re.search(r'\{"color":"black","username":"([^"]+)"', html) or re.search(r'"blackPlayer":\{.*?"username":"([^"]+)"', html)
                    if black_match:
                        self.black_player = black_match.group(1)
                    
                    # Extract moveList
                    move_match = re.search(r'"moveList":"([^"]*)"', html)
                    moves = []
                    is_over = False
                    
                    if move_match:
                        moves_str = move_match.group(1)
                        raw_moves = moves_str.split()
                        # Filter out move numbers like '1.' or '2...' or game results
                        moves = [m for m in raw_moves if not re.match(r'^\d+\.+$', m) and m not in ('1-0', '0-1', '1/2-1/2', '*')]
                    else:
                        # Fallback to PGN parsing
                        pgn_match = re.search(r'\[Result ".*?"\].*?\n\n(.*?)(?:1-0|0-1|1/2-1/2|\*|$)', html, re.DOTALL)
                        if pgn_match:
                            raw_moves = pgn_match.group(1).replace('\n', ' ').split()
                            moves = [m for m in raw_moves if not re.match(r'^\d+\.+$', m) and m not in ('1-0', '0-1', '1/2-1/2', '*')]
                    
                    # Check if game is over
                    if re.search(r'"isOver":true', html) or re.search(r'\[Result "(1-0|0-1|1/2-1/2)"\]', html):
                        is_over = True
                        
                    current_count = len(moves)
                    new_moves = []
                    
                    if current_count > self.last_move_count:
                        new_moves = moves[self.last_move_count:current_count]
                        self.last_move_count = current_count
                        
                        return {
                            "all_moves": moves,
                            "new_moves": new_moves,
                            "white": self.white_player,
                            "black": self.black_player,
                            "is_over": is_over
                        }
                    elif is_over:
                        return {
                            "all_moves": moves,
                            "new_moves": [],
                            "white": self.white_player,
                            "black": self.black_player,
                            "is_over": True
                        }
                        
                    return None
                    
        except Exception as e:
            logger.error(f"Error polling game state: {e}")
            return None
