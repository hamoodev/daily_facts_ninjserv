"""
Daily Facts Discord Bot - Main Entry Point

A Discord bot that generates personalized facts about server members using RAG and Google Gemini AI.
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from utils.fact_tracker import FactTracker  
from utils.vector_store import VectorStore
from gemini_client import GeminiFactGenerator
from events import setup_events
from commands import setup_commands

# Load environment variables
load_dotenv()

# Constants
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# File paths
USED_FACTS_FILE = "used_facts.json"


def create_bot():
    """Create and configure the Discord bot"""
    # Define bot intents 
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    return commands.Bot(command_prefix="!", intents=intents)


def validate_environment():
    """Validate that all required environment variables are set"""
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        return False
    
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set!")
        print("Please set the GEMINI_API_KEY environment variable with your Google AI API key")
        return False
    
    if CHANNEL_ID == 0:
        print("WARNING: CHANNEL_ID not set. Use the /fact command after starting the bot.")
    
    if MONGODB_URI == "mongodb://localhost:27017":
        print("WARNING: Using default MongoDB URI. Set MONGODB_URI environment variable for production.")
    
    return True


def main():
    """Main function to run the bot"""
    print("🤖 Starting Daily Facts Discord Bot...")
    
    # Validate environment
    if not validate_environment():
        exit(1)
    
    # Create bot instance
    bot = create_bot()
    
    # Initialize components
    print("📊 Initializing components...")
    fact_tracker = FactTracker(USED_FACTS_FILE)
    vector_store = VectorStore(None, MONGODB_URI)  # Client will be set up in vector store
    fact_generator = GeminiFactGenerator(GEMINI_API_KEY, fact_tracker, vector_store)
    
    print("🔧 Setting up events and commands...")
    # Setup events and commands
    daily_fact_task = setup_events(bot, vector_store, fact_generator, CHANNEL_ID)
    setup_commands(bot, fact_generator, fact_tracker, vector_store, CHANNEL_ID)
    
    print("🚀 Starting bot...")
    print(f"Bot will send daily facts to channel ID: {CHANNEL_ID}")
    print("✅ All systems ready! Bot is starting...")
    
    # Run the bot
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
