# Discord Bot Configuration Guide

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here
CHANNEL_ID=your_channel_id_here

# OpenAI API Configuration
OPENAI_API_TOKEN=your_openai_api_key_here

# MongoDB Configuration
MONGODB_URI=your_mongodb_connection_string_here
```

## MongoDB Setup

### Option 1: MongoDB Atlas (Recommended)

1. Create a free MongoDB Atlas account at https://www.mongodb.com/atlas
2. Create a new cluster
3. Enable **Vector Search** in your cluster (required for RAG functionality)
4. Create a database user and get your connection string
5. Set `MONGODB_URI` to your Atlas connection string:
   ```
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/discord_bot?retryWrites=true&w=majority
   ```

### Option 2: Local MongoDB

1. Install MongoDB locally
2. Start MongoDB service
3. Set `MONGODB_URI` to:
   ```
   MONGODB_URI=mongodb://localhost:27017
   ```
   
**Note:** Local MongoDB has limited vector search capabilities. Atlas is recommended for full RAG functionality.

## Features

### RAG (Retrieval Augmented Generation)
- The bot now reads and stores all Discord messages in a vector database
- Generates personalized facts about players based on their chat history
- Uses OpenAI embeddings for semantic search
- Respects privacy by focusing on positive community highlights

### Commands
- `/fact [player]` - Generate a fact (optionally about a specific player)
- `/playerfact <player>` - Generate a fact about a specific player
- `/stats` - Show bot statistics including stored messages and tracked players

### Daily Facts
- Automatically sends player-specific facts at 6:00 AM daily
- Uses RAG to create personalized, community-focused content

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   or if using uv:
   ```bash
   uv sync
   ```

2. Set up your `.env` file with the variables above

3. Run the bot:
   ```bash
   python src/main.py
   ```

## Privacy & Safety

The bot is designed with privacy in mind:
- Only processes public Discord messages
- Focuses on positive, community-friendly facts
- Doesn't store or reveal sensitive information
- Generated facts are respectful and celebratory 