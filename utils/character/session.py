# utils/character/session.py
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

@dataclass
class CharacterCreationSession:
    user_id: str
    points_spent: int = 0
    stats: Dict[str, int] = field(default_factory=dict)
    name: Optional[str] = None
    gender: Optional[str] = None
    pronouns: Optional[str] = None
    species: Optional[str] = None
    char_class: Optional[str] = None
    description: Optional[str] = None
    equipment: Dict[str, Any] = field(default_factory=lambda: {
        'Armor': None,
        'Left_Hand': None,
        'Right_Hand': None,
        'Belt_Slots': [None] * 4,
        'Back': None,
        'Magic_Slots': [None] * 3
    })
    inventory: Dict[str, Any] = field(default_factory=dict)

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, CharacterCreationSession] = {}

    def create_session(self, user_id: str) -> CharacterCreationSession:
        """Create a new character creation session"""
        self.sessions[user_id] = CharacterCreationSession(user_id=user_id)
        return self.sessions[user_id]

    def get_session(self, user_id: str) -> Optional[CharacterCreationSession]:
        """Get existing session or None"""
        return self.sessions.get(user_id)

    def end_session(self, user_id: str):
        """End and cleanup a session"""
        if user_id in self.sessions:
            del self.sessions[user_id]

# Global instance
session_manager = SessionManager()