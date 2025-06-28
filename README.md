# Discord Daily Bot with RAG 🤖

A Discord bot that generates personalized "Did you know" facts about server members using RAG (Retrieval Augmented Generation) technology. The bot analyzes chat history to create fun, community-focused facts about players.

## 🌟 Features

### RAG-Powered Facts
- **Personalized Content**: Generates facts about players based on their actual Discord activity
- **Vector Search**: Uses OpenAI embeddings and MongoDB vector search for semantic understanding
- **Privacy-Focused**: Creates positive, respectful facts that celebrate community members
- **Smart Fallbacks**: Falls back to general facts when player context isn't available

### Commands
- `/fact [player]` - Generate a random fact, optionally about a specific player
- `/playerfact <player>` - Generate a fact about a specific player
- `/stats` - Show bot statistics including stored messages and tracked players

### Automated Daily Facts
- Sends personalized facts at 6:00 AM daily
- Randomly selects active community members for facts
- Creates engaging content to boost community interaction

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- MongoDB (Atlas recommended for vector search)
- OpenAI API key
- Discord bot token

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ninjserv_daily_bot
   ```

2. **Install dependencies**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file:
   ```env
   DISCORD_BOT_TOKEN=your_bot_token_here
   CHANNEL_ID=your_channel_id_here
   OPENAI_API_TOKEN=your_openai_api_key_here
   MONGODB_URI=your_mongodb_connection_string_here
   ```

4. **Configure MongoDB**
   
   **MongoDB Atlas (Recommended):**
   - Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/atlas)
   - Enable Vector Search in your cluster
   - Use connection string format: `mongodb+srv://username:password@cluster.mongodb.net/discord_bot`
   
   **Local MongoDB:**
   - Install and run MongoDB locally
   - Use: `mongodb://localhost:27017`

5. **Run the bot**
   ```bash
   python src/main.py
   ```

## 🔧 Configuration

See [CONFIG.md](CONFIG.md) for detailed configuration instructions.

## 🧠 How RAG Works

1. **Message Collection**: The bot monitors Discord messages and stores them with vector embeddings
2. **Semantic Search**: When generating facts, it searches for relevant context about players
3. **Fact Generation**: Uses retrieved context to create personalized, positive facts via OpenAI
4. **Privacy Protection**: Focuses on public, positive aspects and avoids sensitive information

## 📊 Technology Stack

- **Discord.py**: Discord API integration
- **OpenAI**: GPT-3.5-turbo for fact generation and text embeddings
- **MongoDB**: Vector database for message storage and semantic search
- **Motor**: Async MongoDB driver
- **Python-dotenv**: Environment variable management

## 🛡️ Privacy & Safety

- Only processes public Discord messages
- Generates positive, community-friendly content
- Doesn't store or reveal sensitive personal information
- Respects user privacy while celebrating community participation
- Admin/owner controls for manual fact generation

## 🎮 Perfect for Gaming Communities

Originally designed for gaming Discord servers, the bot:
- Celebrates player achievements and activities
- Creates engaging daily content
- Builds stronger community connections
- Highlights positive community interactions

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for improvements.

## 📄 License

This project is open source. Please check the license file for details.

---

**Built with ❤️ for Discord gaming communities**
