import asyncio
import hashlib
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
import pymongo


class VectorStore:
    def __init__(self, openai_client: AsyncOpenAI, mongo_uri: str, db_name: str = "ninjserv"):
        self.openai_client = openai_client
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.collection = None
        
    async def connect(self):
        """Initialize MongoDB connection"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db.messages
            
            # Create vector search index if it doesn't exist
            await self._ensure_vector_index()
            # Create text indexes for fallback search
            await self._ensure_text_indexes()
            print("Connected to MongoDB vector store")
            
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            raise
    
    async def _ensure_vector_index(self):
        """Ensure vector search index exists"""
        try:
            # Check if index exists
            indexes = await self.collection.list_indexes().to_list(length=None)
            vector_index_exists = any(
                index.get('name') == 'vector_index' for index in indexes
            )
            
            if not vector_index_exists:
                # Create vector search index
                index_definition = {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            "embedding": {
                                "type": "knnVector",
                                "dimensions": 1536,  # OpenAI embedding dimension
                                "similarity": "cosine"
                            }
                        }
                    }
                }
                
                # Note: This requires MongoDB Atlas with vector search enabled
                # For local MongoDB, you might need different approach
                print("Vector index setup attempted (requires MongoDB Atlas with vector search)")
                
        except Exception as e:
            print(f"Note: Vector index setup failed - {e}")
            print("Make sure you're using MongoDB Atlas with vector search enabled")
    
    async def _ensure_text_indexes(self):
        """Ensure text search indexes exist for fallback"""
        try:
            # Create text indexes for better search performance
            await self.collection.create_index([
                ("content", "text"),
                ("author_name", "text"),
                ("content_for_search", "text")
            ], name="text_search_index", background=True)
            
            # Create indexes for efficient queries
            await self.collection.create_index("message_id", unique=True, background=True)
            await self.collection.create_index("author_id", background=True)
            await self.collection.create_index("timestamp", background=True)
            await self.collection.create_index("mention_user_ids", background=True)
            
        except Exception as e:
            print(f"Note: Text index setup failed - {e}")
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI"""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            raise
    
    async def message_exists(self, message_id: str) -> bool:
        """Check if message already exists in database"""
        try:
            result = await self.collection.find_one({"message_id": message_id})
            return result is not None
        except Exception as e:
            print(f"Error checking message existence: {e}")
            return False
    
    async def store_message(self, message_data: Dict[str, Any]):
        """Store message with its embedding"""
        try:
            # Check if message already exists
            if await self.message_exists(message_data['message_id']):
                return  # Skip if already stored
            
            # Extract mention user IDs for better searchability
            mention_user_ids = []
            if 'mention_user_ids' in message_data:
                mention_user_ids = message_data['mention_user_ids']
            
            # Create enhanced text content for embedding (includes user IDs for better mention search)
            content_parts = [
                f"User: {message_data['author_name']} (ID: {message_data['author_id']})",
                f"Message: {message_data['content']}",
                f"Channel: {message_data['channel_name']}"
            ]
            
            # Add mention information to the content for better vectorization
            if mention_user_ids:
                mentioned_names = message_data.get('mentions', [])
                mention_text = f"Mentions: {', '.join(mentioned_names)} (IDs: {', '.join(mention_user_ids)})"
                content_parts.append(mention_text)
            
            content_for_embedding = "\n".join(content_parts)
            
            # Get embedding
            embedding = await self.get_embedding(content_for_embedding)
            
            # Create document with enhanced structure
            document = {
                **message_data,
                "embedding": embedding,
                "content_for_search": content_for_embedding,
                "mention_user_ids": mention_user_ids,  # Store as separate field for efficient queries
                "created_at": datetime.utcnow()
            }
            
            # Store in MongoDB
            await self.collection.insert_one(document)
            
        except Exception as e:
            print(f"Error storing message: {e}")
    
    async def search_similar_messages(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for messages similar to query"""
        try:
            # Get query embedding
            query_embedding = await self.get_embedding(query)
            
            # Perform vector search
            # Note: This uses MongoDB Atlas vector search syntax
            # For local MongoDB, you might need different approach
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": limit * 3,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "author_name": 1,
                        "author_id": 1,
                        "content": 1,
                        "channel_name": 1,
                        "timestamp": 1,
                        "mentions": 1,
                        "mention_user_ids": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            results = []
            async for doc in self.collection.aggregate(pipeline):
                results.append(doc)
            
            return results
            
        except Exception as e:
            print(f"Error in vector search: {e}")
            # Fallback to text search if vector search fails
            return await self._fallback_text_search(query, limit)
    
    async def _fallback_text_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fallback text search when vector search is not available"""
        try:
            # Simple text search as fallback
            cursor = self.collection.find(
                {"$text": {"$search": query}},
                {
                    "author_name": 1, "author_id": 1, "content": 1, 
                    "channel_name": 1, "timestamp": 1, "mentions": 1, "mention_user_ids": 1
                }
            ).limit(limit)
            
            results = []
            async for doc in cursor:
                results.append(doc)
            
            return results
            
        except Exception as e:
            print(f"Error in fallback search: {e}")
            return []
    
    async def get_player_context(self, player_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get context about a specific player"""
        try:
            # Search for messages mentioning the player
            query = f"messages about {player_name} player gaming activity"
            results = await self.search_similar_messages(query, limit)
            
            # Also get direct messages from the player
            direct_messages = []
            cursor = self.collection.find(
                {"author_name": {"$regex": player_name, "$options": "i"}},
                {
                    "author_name": 1, "author_id": 1, "content": 1, 
                    "channel_name": 1, "timestamp": 1, "mentions": 1
                }
            ).limit(limit // 2).sort("timestamp", -1)
            
            async for doc in cursor:
                direct_messages.append(doc)
            
            return results + direct_messages
            
        except Exception as e:
            print(f"Error getting player context: {e}")
            return []
    
    async def get_player_context_by_id(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get context about a specific player by user ID"""
        try:
            # Get messages from the player by user ID
            direct_messages = []
            cursor = self.collection.find(
                {"author_id": user_id},
                {
                    "author_name": 1, "author_id": 1, "content": 1, 
                    "channel_name": 1, "timestamp": 1, "mentions": 1
                }
            ).limit(limit).sort("timestamp", -1)
            
            async for doc in cursor:
                direct_messages.append(doc)
            
            # Also search for messages mentioning this user ID
            mentioned_messages = []
            cursor = self.collection.find(
                {"mention_user_ids": user_id},
                {
                    "author_name": 1, "author_id": 1, "content": 1, 
                    "channel_name": 1, "timestamp": 1, "mentions": 1
                }
            ).limit(limit // 2).sort("timestamp", -1)
            
            async for doc in cursor:
                mentioned_messages.append(doc)
            
            return direct_messages + mentioned_messages
            
        except Exception as e:
            print(f"Error getting player context by ID: {e}")
            return []
    
    async def search_mentions(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for messages that mention a specific user ID"""
        try:
            cursor = self.collection.find(
                {"mention_user_ids": user_id},
                {
                    "author_name": 1, "author_id": 1, "content": 1, 
                    "channel_name": 1, "timestamp": 1, "mentions": 1
                }
            ).limit(limit).sort("timestamp", -1)
            
            results = []
            async for doc in cursor:
                results.append(doc)
            
            return results
            
        except Exception as e:
            print(f"Error searching mentions: {e}")
            return []
    
    async def get_all_players(self) -> List[str]:
        """Get list of all active players (users who have sent messages)"""
        try:
            pipeline = [
                {"$group": {"_id": "$author_name", "message_count": {"$sum": 1}, "user_id": {"$first": "$author_id"}}},
                {"$match": {"message_count": {"$gte": 5}}},  # At least 5 messages
                {"$sort": {"message_count": -1}},
                {"$limit": 50}
            ]
            
            players = []
            async for doc in self.collection.aggregate(pipeline):
                players.append(doc["_id"])
            
            return players
            
        except Exception as e:
            print(f"Error getting players: {e}")
            return []
    
    async def get_message_count(self) -> int:
        """Get total number of messages stored"""
        try:
            return await self.collection.count_documents({})
        except Exception as e:
            print(f"Error getting message count: {e}")
            return 0
    
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close() 