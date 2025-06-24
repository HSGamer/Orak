import io
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from PIL import Image

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.gui_utils import (
    _isMac,
    _isWin,
)
from mcp_game_servers.gameio.io_env import IOEnvironment
from mcp_game_servers.utils.types.game_io import Action, Obs

if _isWin():
    from mcp_game_servers.gameio.window_capture import WindowCapture
elif _isMac():
    from mcp_game_servers.gameio.window_capture_mac import capture


# --- State Parser for GSPuzzle ---

class GspuzzleStateParser:
    def __init__(self, state_path: str, sleep_time: float = 0.1):
        self.state_path = state_path
        self.sleep_time = sleep_time

    def get_state(self, timeout: Optional[float] = None) -> Optional[dict]:
        deadline = time.time() + timeout if timeout else None
        while True:
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                state = {}
                for line in lines:
                    if ":" in line:
                        k, v = line.strip().split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k == "Game Status":
                            k = "game_status"
                        elif k == "Level":
                            k = "level"
                        elif k == "Player Moves":
                            k = "player_moves"
                            if v == "None":
                                v = []
                            else:
                                v = v.split("-")
                        elif k == "Shadow Moves":
                            k = "shadow_moves"
                            if v == "None":
                                v = []
                            else:
                                v = v.split("-")
                        elif k == "Steps Before Shadow Appears":
                            k = "steps_before_shadow_appears"
                        state[k] = v
                if state:
                    return state
            except Exception:
                pass
            if deadline and time.time() > deadline:
                return None
            time.sleep(self.sleep_time)


# --- Observation and Action ---

@dataclass
class GspuzzleObs(Obs):
    state: dict
    image: Image.Image = None
    score: int = 100
    done: bool = False

    def to_text(self) -> str:
        s = self.state
        lines = [
            f"Game Status: {s.get('game_status', '')}",
            f"Level: {s.get('level', '')}",
            f"Player Valid Moves: {s.get('player_moves', '')}",
            f"Shadow Moves: {s.get('shadow_moves', '')}",
            f"Steps Before Shadow Appears: {s.get('steps_before_shadow_appears', '')}",
        ]
        return "\n".join(lines)


@dataclass
class GspuzzleAction(Action):
    type: str  # left, right, up, down, next, reset

    @classmethod
    def from_string(cls, action_str: str) -> "GspuzzleAction":
        action = action_str.strip().lower()
        if action in ["left", "right", "up", "down", "next", "reset"]:
            return cls(type=action)
        return cls(type="")


# --- Environment ---

class GspuzzleEnv(BaseEnv):
    @dataclass
    class Config:
        state_path: str
        log_path: str
        final_level: str
        sleep_time: float
        task: str
        input_modality: str
        window_capture_mode: str
        image_max_bytes: int
        io_env: dict

    cfg: Config

    def configure(self) -> None:
        self.state_path = os.path.expanduser(self.cfg.state_path)
        self.log_path = os.path.expanduser(self.cfg.log_path)
        self.final_level = self.cfg.final_level
        self.sleep_time = self.cfg.sleep_time
        self.io_env = IOEnvironment(self.cfg.io_env)
        self.state_parser = GspuzzleStateParser(self.state_path)
        self.logger = logging.getLogger("GSPuzzle")
        self.input_modality = self.cfg.input_modality
        self.window_capture_mode = self.cfg.window_capture_mode
        self.image_max_bytes = self.cfg.image_max_bytes
        self.use_image = self.input_modality in ["image", "text_image"]
        if self.use_image and _isWin():
            self.window_capture = WindowCapture(
                self.io_env.config.win_name_pattern,
                mode=self.window_capture_mode,
            )

    def get_activate_window(self):
        windows = self.io_env.get_windows_by_config()
        if not windows:
            raise RuntimeError("Game window not found")
        window = windows[0] if _isWin() else next((w for w in windows if w.window.get("kCGWindowName")), None)
        window.activate()
        return window

    def capture_image(self) -> Optional[Image.Image]:
        if not self.use_image:
            return None
        if _isWin():
            image = self.window_capture.capture(log_path=self.log_path)
        elif _isMac():
            window = self.get_activate_window()
            image = capture(window, log_path=self.log_path)
        else:
            return None
        # # Resize if needed
        buf = io.BytesIO()
        image.save(buf, format="png")
        image_bytes = buf.tell()
        scale = image_bytes / self.image_max_bytes
        w, h = image.size
        new_size = (int(w / scale), int(h / scale)) if scale > 1 else (w, h)
        return image.resize(new_size, Image.Resampling.LANCZOS)

    def initial_obs(self) -> GspuzzleObs:
        _ = self.get_activate_window()  # Ensure the game window is active
        state = self.state_parser.get_state()
        image = self.capture_image()
        obs = GspuzzleObs(state=state, image=image)
        self.last_obs = obs
        return obs

    def obs2text(self, obs: GspuzzleObs) -> str:
        return obs.to_text()

    def text2action(self, text: str) -> GspuzzleAction:
        self.logger.info(f"Converting text to action: {text}")
        return GspuzzleAction.from_string(text)

    def step(self, action: GspuzzleAction) -> tuple[GspuzzleObs, float, bool, bool, dict[str, Any]]:
        _ = self.get_activate_window()  # Ensure the game window is active
        info = {}

        # Map action to key
        key_map = {
            "left": "left",
            "right": "right",
            "up": "up",
            "down": "down",
            "next": "enter",
            "reset": "space",
        }
        key = key_map.get(action.type)
        if key:
            self.io_env.key_press(key)
            time.sleep(self.sleep_time)
        else:
            self.logger.warning(f"Unknown action: {action.type}")

        # Wait for state update
        state = self.state_parser.get_state()

        # Give a score based on action and game status
        if action.type == "reset" and self.last_obs.state.get("game_status") == "Lost":
            score = self.last_obs.score - 10
        elif action.type == "next" and self.last_obs.state.get("game_status") == "Won":
            score = 100
        else:
            score = self.last_obs.score - 1

        # Check for done
        done = (state.get("level") == self.final_level and state.get("game_status") == "Won")
        image = self.capture_image()
        obs = GspuzzleObs(state=state, image=image, score=score, done=done)
        self.last_obs = obs
        terminated = done
        return obs, score, terminated, False, info

    def evaluate(self, obs: GspuzzleObs) -> tuple[int, bool]:
        return obs.score, obs.done

    def get_game_info(self) -> dict:
        self.logger.info("Getting game info...")
        return {
            "prev_state_str": None,
            "level": self.last_obs.state.get("level", "") if hasattr(self, "last_obs") else "",
            "game_status": self.last_obs.state.get("game_status", "") if hasattr(self, "last_obs") else "",
        }
