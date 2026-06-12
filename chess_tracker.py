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
            self.last_move_count = 0
            logger.info(f"Tracking game ID: {self.game_id}")
            return True
        return False

    async def poll_game_state(self) -> dict:
        """
        Polls the unofficial chess.com live callback endpoint.
        Returns a dictionary with new moves if any, or None.
        """
        if not self.game_id:
            return None

        url = f"https://www.chess.com/callback/live/game/{self.game_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status != 200:
                        logger.warning(f"Failed to fetch game state. Status: {resp.status}")
                        return None
                        
                    data = await resp.json()
                    game_data = data.get("game", {})
                    
                    if not game_data:
                        return None
                        
                    # Extract players
                    players = game_data.get("players", {})
                    if "top" in players and "bottom" in players:
                        # Chess.com callback usually returns top/bottom and indicates who is white/black
                        for pos in ["top", "bottom"]:
                            if players[pos].get("color") == "white":
                                self.white_player = players[pos].get("username", "White")
                            elif players[pos].get("color") == "black":
                                self.black_player = players[pos].get("username", "Black")
                    
                    # Extract moves
                    move_list_str = game_data.get("moveList", "")
                    # moveList is typically a string like "e4 e5 Nf3 Nc6"
                    # But sometimes it's an array or heavily formatted. 
                    # Assuming standard chess.com behavior (space-separated algebraic notation)
                    moves = move_list_str.split() if isinstance(move_list_str, str) else move_list_str
                    
                    if not isinstance(moves, list):
                        moves = []
                        
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
                            "is_over": game_data.get("isOver", False)
                        }
                    elif game_data.get("isOver", False):
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
