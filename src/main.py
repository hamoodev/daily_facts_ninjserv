import discord
from discord.ext import commands, tasks
from discord import app_commands
from openai import AsyncOpenAI
import json
from dotenv import load_dotenv
import os 
from datetime import datetime, time, timedelta
import asyncio
import hashlib
import random
from utils.fact_tracker import FactTracker
from utils.vector_store import VectorStore

load_dotenv()

# Define bot intents 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# CONSTANTS
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# file to store used facts (as hashes to save space)
USED_FACTS_FILE = "used_facts.json"
RATE_LIMIT_FILE = "rate_limits.json"

# Initialize fact tracker and vector store
fact_tracker = FactTracker(USED_FACTS_FILE)
vector_store = VectorStore(client, MONGODB_URI)


def load_rate_limits():
    """Load rate limiting data from file"""
    try:
        if os.path.exists(RATE_LIMIT_FILE):
            with open(RATE_LIMIT_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading rate limits: {e}")
    return {}


def save_rate_limits(rate_limits):
    """Save rate limiting data to file"""
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(rate_limits, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving rate limits: {e}")


def check_and_update_rate_limit(user_id: str, command: str, limit: int = 3) -> bool:
    """Check if user is within rate limit and update usage count"""
    rate_limits = load_rate_limits()
    today = datetime.now().strftime("%Y-%m-%d")
    
    user_key = f"{user_id}_{command}"
    
    if user_key not in rate_limits:
        rate_limits[user_key] = {}
    
    if today not in rate_limits[user_key]:
        rate_limits[user_key][today] = 0
    
    # Clean up old entries (keep only last 7 days)
    cleanup_old_rate_limits(rate_limits)
    
    if rate_limits[user_key][today] >= limit:
        return False  # Rate limit exceeded
    
    # Update usage count
    rate_limits[user_key][today] += 1
    save_rate_limits(rate_limits)
    return True


def cleanup_old_rate_limits(rate_limits):
    """Remove rate limit entries older than 7 days"""
    cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    for user_key in list(rate_limits.keys()):
        user_data = rate_limits[user_key]
        for date in list(user_data.keys()):
            if date < cutoff_date:
                del user_data[date]
        
        # Remove user entry if no dates left
        if not user_data:
            del rate_limits[user_key]


def get_remaining_uses(user_id: str, command: str, limit: int = 3) -> int:
    """Get remaining uses for user today"""
    rate_limits = load_rate_limits()
    today = datetime.now().strftime("%Y-%m-%d")
    user_key = f"{user_id}_{command}"
    
    if user_key not in rate_limits or today not in rate_limits[user_key]:
        return limit
    
    return max(0, limit - rate_limits[user_key][today])


def prepare_message_data(message):
    """Prepare message data for storage with enhanced mention handling"""
    # Extract mention user IDs
    mention_user_ids = [str(user.id) for user in message.mentions]
    mention_names = [user.display_name for user in message.mentions]
    
    message_data = {
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "author_name": message.author.display_name,
        "content": message.content,
        "channel_id": str(message.channel.id),
        "channel_name": message.channel.name,
        "guild_id": str(message.guild.id) if message.guild else None,
        "timestamp": message.created_at,
        "attachments": [att.url for att in message.attachments] if message.attachments else [],
        "mentions": mention_names,
        "mention_user_ids": mention_user_ids  # Enhanced mention tracking
    }
    
    return message_data


async def load_historical_messages():
    """Load historical messages from all channels on startup"""
    print("Starting to load historical messages...")
    
    total_processed = 0
    total_stored = 0
    start_time = datetime.now()
    
    try:
        for guild in bot.guilds:
            if guild.id != 1339871897713901602:
                continue
            print(f"Processing guild: {guild.name}")
            
            for channel in guild.text_channels:
                try:
                    # Check if bot has permission to read message history
                    if not channel.permissions_for(guild.me).read_message_history:
                        print(f"  Skipping {channel.name}: No read history permission")
                        continue
                    
                    print(f"  Processing channel: {channel.name}")
                    channel_processed = 0
                    channel_stored = 0
                    
                    # Process messages in batches for better performance
                    batch_size = 50
                    message_batch = []
                    
                    async for message in channel.history(limit=None, oldest_first=True):
                        # Skip bot messages and commands
                        if message.author.bot or message.content.startswith('!') or message.content.startswith('/'):
                            continue
                        
                        # Skip empty messages or messages that are too short
                        if len(message.content.strip()) < 10:
                            continue
                        
                        channel_processed += 1
                        total_processed += 1
                        
                        # Prepare message data
                        message_data = prepare_message_data(message)
                        
                        # Check if message already exists before storing
                        if not await vector_store.message_exists(message_data['message_id']):
                            message_batch.append(message_data)
                        
                        # Process batch when it's full
                        if len(message_batch) >= batch_size:
                            for msg_data in message_batch:
                                try:
                                    await vector_store.store_message(msg_data)
                                    channel_stored += 1
                                    total_stored += 1
                                except Exception as e:
                                    print(f"      Error storing message {msg_data['message_id']}: {e}")
                            
                            message_batch = []
                            
                            # Progress update
                            elapsed = datetime.now() - start_time
                            print(f"    Progress: {total_processed} processed, {total_stored} stored, elapsed: {elapsed}")
                    
                    # Process any remaining messages in the batch
                    if message_batch:
                        for msg_data in message_batch:
                            try:
                                await vector_store.store_message(msg_data)
                                channel_stored += 1
                                total_stored += 1
                            except Exception as e:
                                print(f"      Error storing message {msg_data['message_id']}: {e}")
                    
                    print(f"    Channel {channel.name}: {channel_processed} processed, {channel_stored} new messages stored")
                    
                except Exception as e:
                    print(f"    Error processing channel {channel.name}: {e}")
                    continue
    
    except Exception as e:
        print(f"Error during historical message loading: {e}")
    
    elapsed_time = datetime.now() - start_time
    print(f"Historical message loading complete!")
    print(f"Total messages processed: {total_processed}")
    print(f"New messages stored: {total_stored}")
    print(f"Time elapsed: {elapsed_time}")
    
    # Get final count
    total_in_db = await vector_store.get_message_count()
    print(f"Total messages now in database: {total_in_db}")


@bot.event
async def on_message(message):
    """Process messages and store them in vector database"""
    # Skip bot messages and commands
    if message.author.bot or message.content.startswith('!') or message.content.startswith('/'):
        return
    
    # Skip empty messages or messages that are too short
    if len(message.content.strip()) < 10:
        return
    
    try:
        # Prepare message data with enhanced mention handling
        message_data = prepare_message_data(message)
        
        # Store message in vector database
        await vector_store.store_message(message_data)
        
    except Exception as e:
        print(f"Error processing message: {e}")
    
    # Process commands
    await bot.process_commands(message)


async def generate_player_fact_with_rag(player_name: str = None, user_id: str = None):
    """Generate a fact about a specific player using RAG with enhanced mention support"""
    try:
        if not player_name and not user_id:
            # Get a random active player
            players = await vector_store.get_all_players()
            if not players:
                return await generate_unique_fact()  # Fallback to general fact
            player_name = random.choice(players)
        
        # Get context about the player (using both name and ID if available)
        if user_id:
            context = await vector_store.get_player_context_by_id(user_id, limit=15)
            # Also get mentions of this user
            mention_context = await vector_store.search_mentions(user_id, limit=5)
            context.extend(mention_context)
        elif player_name:
            context = await vector_store.get_player_context(player_name, limit=10)
        else:
            context = []
        
        if not context:
            return await generate_unique_fact()  # Fallback if no context found
        
        # Prepare context for the AI with more information
        context_text = "\n".join([
            f"- {msg.get('author_name', 'Unknown')} ({msg.get('timestamp', '').strftime('%Y-%m-%d') if msg.get('timestamp') else 'Unknown date'}): {msg.get('content', '')[:200]}"
            for msg in context[:10]  # Limit context to avoid token limits
        ])
        
        # Generate player-specific fact
        target_name = player_name if player_name else context[0].get('author_name', 'Unknown Player')
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are creating personalized 'Did you know' facts about Discord server members based on their chat history and mentions.

Rules:
- Start with 'Did you know'
- Keep it under 280 characters
- Focus on their gaming activities, interests, or positive traits shown in messages
- Don't reveal private/sensitive information
- Be respectful and avoid anything that could be embarrassing
- Use information from both their own messages and messages mentioning them

Context about {target_name}:
{context_text}

Create a fun fact that celebrates this player's presence in the community based on the messages and interactions shown."""
                },
                {
                    "role": "user",
                    "content": f"Generate a fun 'Did you know' fact about {target_name} based on their activity and mentions in the server."
                }
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        fact = response.choices[0].message.content.strip()
        
        # Check if this specific fact has been used
        if not fact_tracker.is_fact_used(fact):
            fact_tracker.mark_fact_used(fact)
            return fact
        
        # If fact was used, try to generate a more general player fact
        return await generate_general_player_fact(target_name)
        
    except Exception as e:
        print(f"Error generating player fact with RAG: {e}")
        return await generate_unique_fact()


async def generate_general_player_fact(player_name: str):
    """Generate a general fact about player without specific context"""
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """Create a fun, generic 'Did you know' fact about a Discord server member.
                    Make it positive and community-focused without needing specific context.
                    Start with 'Did you know' and keep under 280 characters."""
                },
                {
                    "role": "user",
                    "content": f"Generate a fun community fact about {player_name}."
                }
            ],
            max_tokens=100,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating general player fact: {e}")
        return f"Did you know that {player_name} is an awesome member of our gaming community? 🎮"


async def generate_unique_fact():
    """Generate a unique 'Did you know' fact using OpenAI (fallback for when no player context available)"""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Generate a fact
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a fact generator. Create interesting, educational 'Did you know' facts. 
                        Rules:
                        - Start with 'Did you know'
                        - Keep it under 280 characters
                        - Make it genuinely interesting and surprising
                        - Cover diverse topics: science, history, nature, technology, culture, gaming
                        - Ensure accuracy
                        - Make it engaging and fun to read"""
                    },
                    {
                        "role": "user",
                        "content": f"Generate a unique 'Did you know' fact. This is attempt {attempt + 1}, so make it different from common facts."
                    }
                ],
                max_tokens=100,
                temperature=0.8
            )
            
            fact = response.choices[0].message.content.strip()
            
            # Check if this fact (or very similar) has been used
            if not fact_tracker.is_fact_used(fact):
                fact_tracker.mark_fact_used(fact)
                return fact
            
            print(f"Fact already used, attempting again... (Attempt {attempt + 1})")
            
        except Exception as e:
            print(f"Error generating fact (attempt {attempt + 1}): {e}")
            if attempt == max_attempts - 1:
                return "Did you know that this bot is trying its best to bring you interesting facts every day? 🤖"
    
    return "Did you know that persistence is key to success? Today's fact generation needed a few tries! 💪"


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Connect to vector store
    try:
        await vector_store.connect()
        print("Vector store connected successfully!")
        
        # Load historical messages on startup
        # print("Loading historical messages...")
        # await load_historical_messages()
        
    except Exception as e:
        print(f"Warning: Vector store connection failed: {e}")
        print("Bot will continue with limited functionality")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Start the daily fact task
    if not daily_fact.is_running():
        daily_fact.start()

# 6 AM EVERY DAY
@tasks.loop(time=time(6, 0))  # Send at 6:00 AM every day
async def daily_fact():
    """Send daily fact to specified channel"""
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Channel with ID {CHANNEL_ID} not found!")
            return
        
        print("Generating daily player fact...")
        
        # Try to generate a player-specific fact using RAG
        fact = await generate_player_fact_with_rag()
        
        # Create an embed for better presentation
        embed = discord.Embed(
            title="🧠 Daily Did You Know",
            description=fact,
            color=0x3498db,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Hamood wishes you a great and healthy life! 🎮")
        
        await channel.send(embed=embed)
        print(f"Daily fact sent: {fact[:50]}...")
        
    except Exception as e:
        print(f"Error sending daily fact: {e}")

@daily_fact.before_loop
async def before_daily_fact():
    """Wait until bot is ready before starting the loop"""
    await bot.wait_until_ready()

# Slash commands
@bot.tree.command(name="fact", description="Generate a random fact about a player or general topic")
@app_commands.describe(player="Optional: specific player to generate a fact about")
async def manual_fact(interaction: discord.Interaction, player: str = None):
    """Manually trigger a fact"""
    # only admin or hamood can trigger a fact
    if not interaction.user.guild_permissions.administrator and interaction.user.id != 279224191671205890:
        await interaction.response.send_message("Only administrators or Hamood can manually trigger facts!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Get the channel
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await interaction.followup.send(f"Channel with ID {CHANNEL_ID} not found!", ephemeral=True)
        return
    
    # Generate and send fact to the channel
    if player:
        # Try to find the user by name or mention
        user_id = None
        if player.startswith('<@') and player.endswith('>'):
            # Extract user ID from mention
            user_id = player[2:-1].replace('!', '')
        
        fact = await generate_player_fact_with_rag(player, user_id)
        title = f"🧠 Did You Know About {player}"
    else:
        fact = await generate_player_fact_with_rag()
        title = "🧠 Did You Know"
    
    embed = discord.Embed(
        title=title,
        description=fact,
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.set_footer(text="Hamood wishes you a great and healthy life! 🎮")
    
    await channel.send(embed=embed)
    await interaction.followup.send(f"Fact sent to {channel.mention}!", ephemeral=True)

@bot.tree.command(name="stats", description="Show fact bot statistics")
async def fact_stats(interaction: discord.Interaction):
    """Show statistics about used facts and stored messages"""
    
    total_facts = len(fact_tracker.used_facts)
    
    try:
        # Get player count from vector store
        players = await vector_store.get_all_players()
        player_count = len(players)
        
        # Get total message count
        message_count = await vector_store.get_message_count()
        
    except Exception as e:
        print(f"Error getting vector store stats: {e}")
        player_count = "Unknown"
        message_count = "Unknown"
    
    embed = discord.Embed(
        title="📊 Fact Bot Statistics",
        color=0x2ecc71
    )
    embed.add_field(name="Total Unique Facts Sent", value=total_facts, inline=False)
    embed.add_field(name="Active Players Tracked", value=player_count, inline=True)
    embed.add_field(name="Messages Stored", value=message_count, inline=True)
    embed.add_field(name="Next Fact", value="Tomorrow at 6:00 AM", inline=False)
    embed.add_field(name="RAG System", value="✅ Player-specific facts with mentions enabled", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="loadhistory", description="Manually load historical messages (Admin only)")
async def load_history_command(interaction: discord.Interaction):
    """Manually trigger historical message loading"""
    # Only admin or hamood can trigger this
    if not interaction.user.guild_permissions.administrator and interaction.user.id != 279224191671205890:
        await interaction.response.send_message("Only administrators or Hamood can load historical messages!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        await interaction.followup.send("Starting to load historical messages... This may take a while.", ephemeral=True)
        await load_historical_messages()
        await interaction.followup.send("Historical message loading completed! Check the console for details.", ephemeral=True)
    except Exception as e:
        print(f"Error in manual history loading: {e}")
        await interaction.followup.send(f"Error occurred while loading historical messages: {str(e)}", ephemeral=True)

@bot.tree.command(name="remaining", description="Check your remaining daily uses for commands")
async def remaining_uses_command(interaction: discord.Interaction):
    """Check remaining daily uses for rate-limited commands"""
    user_id = str(interaction.user.id)
    
    playerfact_remaining = get_remaining_uses(user_id, "playerfact")
    
    embed = discord.Embed(
        title="📊 Your Remaining Daily Uses",
        color=0x3498db,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="🎭 Player Facts", 
        value=f"{playerfact_remaining}/3 uses remaining", 
        inline=False
    )
    
    if playerfact_remaining == 0:
        embed.add_field(
            name="⏰ Reset Time", 
            value="Resets at midnight UTC", 
            inline=False
        )
    
    embed.set_footer(text="Use your facts wisely! 🎮")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="playerfact", description="Generate a fact about a specific player")
@app_commands.describe(player="The player to generate a fact about")
async def player_fact_command(interaction: discord.Interaction, player: discord.User):
    """Generate a fact about a specific player with rate limiting"""
    # Check rate limit first
    remaining_uses = get_remaining_uses(str(interaction.user.id), "playerfact")
    
    if not check_and_update_rate_limit(str(interaction.user.id), "playerfact"):
        await interaction.response.send_message(
            f"You've reached your daily limit of 3 player facts! Please try again tomorrow. 🕒", 
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Use the selected Discord user
        user_id = str(player.id)
        player_name = player.display_name
        
        # Check if the selected user is in the server
        guild_member = interaction.guild.get_member(player.id)
        if not guild_member:
            await interaction.followup.send(
                f"Sorry, {player_name} is not a member of this server!", 
                ephemeral=True
            )
            return
        
        fact = await generate_player_fact_with_rag(player_name, user_id)
        
        # Show remaining uses
        new_remaining = get_remaining_uses(str(interaction.user.id), "playerfact")
        
        embed = discord.Embed(
            title=f"🧠 Did You Know About {player_name}",
            description=fact,
            color=0x9b59b6,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Powered by Hamood's Smart AI! • {new_remaining} uses remaining today")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error generating player fact: {e}")
        await interaction.followup.send("Sorry, I couldn't generate a fact about that player right now.", ephemeral=True)

# Error handling for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Slash command error: {error}")
    
    try:
        if isinstance(error, app_commands.MissingPermissions):
            error_msg = "You don't have permission to use this command!"
        else:
            error_msg = "An error occurred while processing the command."
        
        # Check if interaction has already been responded to
        if not interaction.response.is_done():
            await interaction.response.send_message(error_msg, ephemeral=True)
        else:
            # Use followup if response is already done
            await interaction.followup.send(error_msg, ephemeral=True)
            
    except Exception as e:
        print(f"Error in error handler: {e}")
        # Last resort - just log the error if we can't send any message

# Keep traditional command error handling for any remaining prefix commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command!")
    else:
        print(f"Error: {error}")
        await ctx.send("An error occurred while processing the command.")

if __name__ == "__main__":
    # Check for required environment variables
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        exit(1)
    
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable not set!")
        exit(1)
    
    if CHANNEL_ID == 0:
        print("WARNING: CHANNEL_ID not set. Use the /fact command after starting the bot.")
    
    if MONGODB_URI == "mongodb://localhost:27017":
        print("WARNING: Using default MongoDB URI. Set MONGODB_URI environment variable for production.")
    
    # Run the bot
    bot.run(DISCORD_TOKEN)
