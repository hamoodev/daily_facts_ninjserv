"""
Pydantic models for structured AI responses
"""

from pydantic import BaseModel


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