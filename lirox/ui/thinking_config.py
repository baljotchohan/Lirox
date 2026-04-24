"""
Configuration for thinking display
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class ThinkingDisplayConfig:
    """
    Configure how thinking is displayed
    """
    
    # Display mode
    auto_expand: bool = False  # Auto-expand or wait for click?
    display_style: Literal['rich', 'simple', 'minimal'] = 'rich'
    
    # Streaming
    stream_speed: float = 0.03  # Seconds per character
    show_typing_cursor: bool = True
    
    # Agents
    num_agents: int = 5
    show_all_agents: bool = True
    agents_in_parallel: bool = False  # Show all at once or sequential?
    
    # Debate
    show_debate: bool = True
    debate_detail: Literal['high', 'medium', 'low'] = 'high'
    
    # Synthesis
    show_synthesis: bool = True
    synthesis_style: Literal['detailed', 'summary'] = 'detailed'
    
    # Performance
    thinking_mode: Literal['fast', 'balanced', 'deep'] = 'balanced'
    
    # Keyboard
    enable_keyboard_shortcuts: bool = True
    shortcuts = {
        't': 'toggle',
        'e': 'expand',
        'c': 'collapse',
        'd': 'show_debate',
        's': 'show_synthesis',
        'a': 'show_all_agents',
    }


# Default config
DEFAULT_THINKING_CONFIG = ThinkingDisplayConfig()
