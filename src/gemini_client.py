"""
Google Gemini AI client and fact generation functions
"""

import asyncio
import random
from google import genai
from models import FactResponse, PlayerFactResponse, PersonalityCard


class GeminiFactGenerator:
    """Handles all AI fact generation using Google Gemini"""
    
    def __init__(self, api_key: str, fact_tracker, vector_store):
        self.client = genai.Client(api_key=api_key)
        self.fact_tracker = fact_tracker
        self.vector_store = vector_store
    
    async def generate_player_fact_with_rag(self, player_name: str = None, user_id: str = None):
        """Generate a fact about a specific player using RAG with enhanced mention support"""
        try:
            if not player_name and not user_id:
                # Get a random active player
                players = await self.vector_store.get_all_players()
                if not players:
                    return await self.generate_unique_fact()  # Fallback to general fact
                player_name = random.choice(players)
            
            # Get context about the player (using both name and ID if available)
            if user_id:
                context = await self.vector_store.get_player_context_by_id(user_id, limit=15)
                # Also get mentions of this user
                mention_context = await self.vector_store.search_mentions(user_id, limit=5)
                context.extend(mention_context)
            elif player_name:
                context = await self.vector_store.get_player_context(player_name, limit=10)
            else:
                context = []
            
            if not context:
                return await self.generate_unique_fact()  # Fallback if no context found
            
            # Prepare context for the AI with more information
            context_text = "\n".join([
                f"- {msg.get('author_name', 'Unknown')} ({msg.get('timestamp', '').strftime('%Y-%m-%d') if msg.get('timestamp') else 'Unknown date'}): {msg.get('content', '')[:200]}"
                for msg in context[:10]  # Limit context to avoid token limits
            ])
            
            # Generate player-specific fact
            target_name = player_name if player_name else context[0].get('author_name', 'Unknown Player')
            
            # Prepare the prompt for structured response
            prompt = f"""You are creating personalized 'Did you know' facts about Discord server members based on their chat history and mentions.

Rules:
- Start with 'Did you know'
- Keep it under 280 characters
- Focus on their gaming activities, interests, or positive traits shown in messages
- Don't reveal private/sensitive information
- You can be harsh and roast them a little bit for fun
- Use information from both their own messages and messages mentioning them

Context about {target_name}:
{context_text}

Generate a fun 'Did you know' fact about {target_name} based on their activity and mentions in the server."""

            # Run the synchronous Gemini call in an async context
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": PlayerFactResponse,
                        "max_output_tokens": 150,
                        "temperature": 0.7
                    }
                )
            )
            
            fact_data = PlayerFactResponse.model_validate_json(response.text)
            fact = fact_data.fact
            
            # Check if this specific fact has been used
            if not self.fact_tracker.is_fact_used(fact):
                self.fact_tracker.mark_fact_used(fact)
                return fact
            
            # If fact was used, try to generate a more general player fact
            return await self.generate_general_player_fact(target_name)
            
        except Exception as e:
            print(f"Error generating player fact with RAG: {e}")
            return await self.generate_unique_fact()

    async def generate_general_player_fact(self, player_name: str):
        """Generate a general fact about player without specific context"""
        try:
            prompt = f"""Create a fun, generic 'Did you know' fact about a Discord server member named {player_name}.
Make it positive and community-focused without needing specific context.
Start with 'Did you know' and keep under 280 characters."""

            # Run the synchronous Gemini call in an async context
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": PlayerFactResponse,
                        "max_output_tokens": 120,
                        "temperature": 0.8
                    }
                )
            )
            
            fact_data = PlayerFactResponse.model_validate_json(response.text)
            return fact_data.fact
            
        except Exception as e:
            print(f"Error generating general player fact: {e}")
            return f"Did you know that {player_name} is an awesome member of our gaming community? 🎮"

    async def generate_unique_fact(self):
        """Generate a unique 'Did you know' fact using Gemini (fallback for when no player context available)"""
        max_attempts = 5
        
        for attempt in range(max_attempts):
            try:
                prompt = f"""You are a fact generator. Create interesting, educational 'Did you know' facts. 
Rules:
- Start with 'Did you know'
- Keep it under 280 characters
- Make it genuinely interesting and surprising
- Cover diverse topics: science, history, nature, technology, culture, gaming
- Ensure accuracy
- Make it engaging and fun to read

Generate a unique 'Did you know' fact. This is attempt {attempt + 1}, so make it different from common facts."""

                # Run the synchronous Gemini call in an async context
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model="gemini-2.0-flash-exp",
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": FactResponse,
                            "max_output_tokens": 120,
                            "temperature": 0.8
                        }
                    )
                )
                
                fact_data = FactResponse.model_validate_json(response.text)
                fact = fact_data.fact
                
                # Check if this fact (or very similar) has been used
                if not self.fact_tracker.is_fact_used(fact):
                    self.fact_tracker.mark_fact_used(fact)
                    return fact
                
                print(f"Fact already used, attempting again... (Attempt {attempt + 1})")
                
            except Exception as e:
                print(f"Error generating fact (attempt {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    return "Did you know that this bot is trying its best to bring you interesting facts every day? 🤖"
        
        return "Did you know that persistence is key to success? Today's fact generation needed a few tries! 💪"

    async def generate_personality_card(self, player_name: str, user_id: str = None):
        """Generate a personality card for a specific player using RAG"""
        try:
            # Get context about the player (using both name and ID if available)
            if user_id:
                context = await self.vector_store.get_player_context_by_id(user_id, limit=20)
                # Also get mentions of this user
                mention_context = await self.vector_store.search_mentions(user_id, limit=8)
                context.extend(mention_context)
            elif player_name:
                context = await self.vector_store.get_player_context(player_name, limit=15)
            else:
                context = []
            
            if not context:
                # Fallback personality card
                return PersonalityCard(
                    name=player_name,
                    positive_traits=["Mysterious", "Unique", "Independent"],
                    negative_traits=["Elusive", "Hard to read", "Keeps secrets"],
                    yaps_about="the mysteries of life",
                    fun_stat=f"{player_name} is so mysterious, even their own shadow doesn't know what they're thinking! 🕵️"
                )
            
            # Prepare context for the AI with more comprehensive information
            context_text = "\n".join([
                f"- {msg.get('author_name', 'Unknown')} ({msg.get('timestamp', '').strftime('%Y-%m-%d') if msg.get('timestamp') else 'Unknown date'}): {msg.get('content', '')[:300]}"
                for msg in context[:15]  # More context for personality analysis
            ])
            
            # Generate personality card with structured prompt
            target_name = player_name if player_name else context[0].get('author_name', 'Unknown Player')
            
            prompt = f"""You are creating a personality card for a Discord server member based on their chat history and mentions. Analyze their communication patterns, interests, and social interactions.

IMPORTANT RULES:
- Be playful but respectful - this is meant to be fun, not mean-spirited
- Base traits on actual observed behavior in messages
- Make the "yaps_about" field their most discussed topic
- The fun_stat should be a little harsh  roast
- Keep traits concise (1-3 words each)
- Attack on titans themed

Context about {target_name}:
{context_text}

Create a personality card that captures their Discord persona in a fun, engaging way. Focus on their communication style, interests, and quirks observed in their messages."""

            # Run the synchronous Gemini call in an async context
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": PersonalityCard,
                        "max_output_tokens": 300,
                        "temperature": 0.8
                    }
                )
            )
            
            personality_data = PersonalityCard.model_validate_json(response.text)
            return personality_data
            
        except Exception as e:
            print(f"Error generating personality card: {e}")
            # Return a safe fallback
            return PersonalityCard(
                name=player_name,
                positive_traits=["Friendly", "Active", "Engaging"],
                negative_traits=["Sometimes quiet", "Mysterious", "Unpredictable"],
                yaps_about="various interesting topics",
                fun_stat=f"{player_name} is like a good book - interesting, but we're still figuring out the plot! 📚"
            ) 