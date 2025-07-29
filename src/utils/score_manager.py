"""
Score Manager

Handles database operations for AOTTG scores using MongoDB.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import pymongo

from models import ScoreRecord


class ScoreManager:
    """Manages AOTTG score storage and retrieval"""
    
    def __init__(self, mongo_uri: str, db_name: str = "ninjserv"):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.collection: Optional[AsyncIOMotorCollection] = None
        
    async def connect(self):
        """Initialize MongoDB connection"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db.scores
            
            # Create indexes for efficient queries
            await self._ensure_indexes()
            print("Connected to MongoDB score manager")
            
        except Exception as e:
            print(f"Error connecting to MongoDB score manager: {e}")
            raise
            
    async def _ensure_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Index for user lookups
            await self.collection.create_index([
                ("user_id", pymongo.ASCENDING),
                ("guild_id", pymongo.ASCENDING)
            ])
            
            # Index for leaderboard queries (KD ratio descending)
            await self.collection.create_index([
                ("guild_id", pymongo.ASCENDING),
                ("kd_ratio", pymongo.DESCENDING)
            ])
            
            # Index for timestamp queries
            await self.collection.create_index("submitted_at")
            
        except Exception as e:
            print(f"Error creating indexes: {e}")
    
    async def save_score(self, score_record: ScoreRecord) -> bool:
        """
        Save or update a user's score record
        
        Args:
            score_record: ScoreRecord instance to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert Pydantic model to dict
            score_data = score_record.model_dump()
            
            # Update or insert the score (upsert based on user_id and guild_id)
            result = await self.collection.replace_one(
                {
                    "user_id": score_record.user_id,
                    "guild_id": score_record.guild_id
                },
                score_data,
                upsert=True
            )
            
            return True
            
        except Exception as e:
            print(f"Error saving score: {e}")
            return False
    
    async def get_user_score(self, user_id: str, guild_id: str) -> Optional[ScoreRecord]:
        """
        Get a user's current score record
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            ScoreRecord if found, None otherwise
        """
        try:
            score_data = await self.collection.find_one({
                "user_id": user_id,
                "guild_id": guild_id
            })
            
            if score_data:
                # Remove MongoDB's _id field
                score_data.pop("_id", None)
                return ScoreRecord(**score_data)
                
            return None
            
        except Exception as e:
            print(f"Error getting user score: {e}")
            return None
    
    async def get_leaderboard(self, guild_id: str, limit: int = 10) -> List[ScoreRecord]:
        """
        Get leaderboard sorted by KD ratio
        
        Args:
            guild_id: Discord guild ID
            limit: Number of top players to return
            
        Returns:
            List of ScoreRecord objects sorted by KD ratio descending
        """
        try:
            cursor = self.collection.find(
                {"guild_id": guild_id}
            ).sort("kd_ratio", pymongo.DESCENDING).limit(limit)
            
            leaderboard = []
            async for score_data in cursor:
                score_data.pop("_id", None)
                leaderboard.append(ScoreRecord(**score_data))
                
            return leaderboard
            
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []
    
    async def get_user_rank(self, user_id: str, guild_id: str) -> Optional[int]:
        """
        Get a user's rank in the leaderboard
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            Rank (1-based) or None if user not found
        """
        try:
            user_score = await self.get_user_score(user_id, guild_id)
            if not user_score:
                return None
            
            # Count users with higher KD ratio
            higher_count = await self.collection.count_documents({
                "guild_id": guild_id,
                "kd_ratio": {"$gt": user_score.kd_ratio}
            })
            
            return higher_count + 1
            
        except Exception as e:
            print(f"Error getting user rank: {e}")
            return None
    
    async def get_total_players(self, guild_id: str) -> int:
        """
        Get total number of players with scores in a guild
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Number of players
        """
        try:
            return await self.collection.count_documents({"guild_id": guild_id})
        except Exception as e:
            print(f"Error getting total players: {e}")
            return 0 