"""
Pydantic models for structured AI responses
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FactResponse(BaseModel):
    """A structured fact response"""
    fact: str
    category: str = "general"
    

class PlayerFactResponse(BaseModel):
    """A structured player-specific fact response"""
    fact: str
    player_name: str = "Unknown Player"
    category: str = "player"
    confidence_score: float = 0.8


class PersonalityCard(BaseModel):
    """A structured personality card for a Discord user"""
    name: str
    positive_traits: list[str]  # 3 positive traits
    negative_traits: list[str]  # 3 negative traits  
    yaps_about: str  # Top topic they talk about most
    fun_stat: str  # A roasting fun fact about them


class ScoreRecord(BaseModel):
    """A user's AOTTG score record"""
    user_id: str
    username: str
    kills: int
    deaths: int
    kd_ratio: float
    submitted_at: datetime
    guild_id: str  # To support multiple servers
    
    @classmethod
    def create(cls, user_id: str, username: str, kills: int, deaths: int, guild_id: str):
        """Create a new score record with calculated KD ratio"""
        kd_ratio = kills / deaths if deaths > 0 else float(kills)
        return cls(
            user_id=user_id,
            username=username,
            kills=kills,
            deaths=deaths,
            kd_ratio=kd_ratio,
            submitted_at=datetime.now(),
            guild_id=guild_id
        ) 