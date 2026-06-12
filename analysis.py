import chess
import chess.engine
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('ChessCaster')

class ChessAnalyzer:
    def __init__(self):
        self.board = chess.Board()
        self.engine_path = "stockfish" # Relies on the binary being in the system PATH (installed via Docker)
        self.engine = None
        self.last_eval = 0 # In centipawns from White's perspective
        
        self.init_engine()

    def init_engine(self):
        if not self.engine_path or not os.path.exists(self.engine_path):
            logger.warning(f"Stockfish not found at {self.engine_path}. Analysis will be limited.")
            return
            
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            logger.info("Stockfish engine initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Stockfish: {e}")

    def reset(self):
        self.board = chess.Board()
        self.last_eval = 0

    def push_moves(self, move_strings: list[str]) -> list[dict]:
        """
        Pushes a list of algebraic notation moves to the board.
        Analyzes each move and returns a list of event dictionaries.
        """
        events = []
        for move_str in move_strings:
            try:
                move = self.board.push_san(move_str)
                event = self.analyze_current_position(move_str, move)
                if event:
                    events.append(event)
            except ValueError as e:
                logger.error(f"Invalid move '{move_str}': {e}")
                
        return events

    def analyze_current_position(self, move_str: str, move: chess.Move) -> dict:
        """Analyzes the board state after a move has been made."""
        is_checkmate = self.board.is_checkmate()
        is_check = self.board.is_check()
        is_capture = self.board.is_capture(move)
        
        # Who just moved? If it's black's turn now, white just moved.
        player = "White" if self.board.turn == chess.BLACK else "Black"
        
        event = {
            "move": move_str,
            "player": player,
            "is_checkmate": is_checkmate,
            "is_check": is_check,
            "is_capture": is_capture,
            "eval": 0,
            "eval_diff": 0,
            "is_blunder": False,
            "is_significant": False
        }

        if not self.engine:
            # Basic fallback if no engine
            event["is_significant"] = is_checkmate or is_check or is_capture
            return event

        try:
            # Analyze position with depth 15 (fast enough for real-time)
            info = self.engine.analyse(self.board, chess.engine.Limit(depth=15))
            score = info["score"].white()
            
            if score.is_mate():
                current_eval = 10000 if score.mate() > 0 else -10000
            else:
                current_eval = score.score()

            eval_diff = current_eval - self.last_eval
            
            # If white moved, a negative diff means they worsened their position
            # If black moved, a positive diff means they worsened their position
            if player == "White":
                blunder_threshold = -250 # Dropped 2.5 pawns
                significant_threshold = 150
                is_blunder = eval_diff <= blunder_threshold
                is_brilliant = eval_diff >= significant_threshold
            else:
                blunder_threshold = 250
                significant_threshold = -150
                is_blunder = eval_diff >= blunder_threshold
                is_brilliant = eval_diff <= significant_threshold

            event["eval"] = current_eval
            event["eval_diff"] = eval_diff
            event["is_blunder"] = is_blunder
            
            # Determine if this move is significant enough to warrant commentary
            event["is_significant"] = (
                is_checkmate or 
                is_check or 
                is_blunder or 
                is_brilliant or
                (is_capture and abs(current_eval) > 300) # Significant capture
            )
            
            self.last_eval = current_eval
            
        except Exception as e:
            logger.error(f"Engine analysis error: {e}")

        return event

    def get_score_string(self) -> str:
        """Returns a string representation of the current evaluation."""
        if not self.engine:
            return "Engine not available."
            
        if self.last_eval > 9000:
            return "White has a forced mate."
        elif self.last_eval < -9000:
            return "Black has a forced mate."
        else:
            cp = self.last_eval / 100.0
            if cp > 0:
                return f"White is winning by +{cp:.2f}"
            elif cp < 0:
                return f"Black is winning by {cp:.2f}"
            else:
                return "The game is dead even (0.00)."

    def close(self):
        if self.engine:
            self.engine.quit()
