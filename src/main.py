import discord
from discord.ext import commands, tasks
from discord import app_commands
from openai import AsyncOpenAI
import json
from dotenv import load_dotenv
import os 
from datetime import datetime, time
import asyncio
import hashlib
from utils.fact_tracker import FactTracker

load_dotenv()

# Define bot intents 
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# CONSTANTS
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# file to store used facts (as hashes to save space)
USED_FACTS_FILE = "used_facts.json"

# Initialize fact tracker
fact_tracker = FactTracker(USED_FACTS_FILE)


async def generate_unique_fact():
    """Generate a unique 'Did you know' fact using OpenAI"""
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
                        - Cover diverse topics: science, history, nature, technology, culture
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
@tasks.loop(time=time(6, 0))  # Send at 12:00 PM every day
async def daily_fact():
    """Send daily fact to specified channel"""
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Channel with ID {CHANNEL_ID} not found!")
            return
        
        print("Generating daily fact...")
        fact = await generate_unique_fact()
        
        # Create an embed for better presentation
        embed = discord.Embed(
            title="🧠 Daily Did You Know",
            description=fact,
            color=0x3498db,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Hamood wishes you a great life and healthy life!")
        
        await channel.send(embed=embed)
        print(f"Daily fact sent: {fact[:50]}...")
        
    except Exception as e:
        print(f"Error sending daily fact: {e}")

@daily_fact.before_loop
async def before_daily_fact():
    """Wait until bot is ready before starting the loop"""
    await bot.wait_until_ready()

# Slash commands
@bot.tree.command(name="fact", description="Generate a random fact")
@app_commands.describe()
async def manual_fact(interaction: discord.Interaction):
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
    fact = await generate_unique_fact()
    embed = discord.Embed(
        title="🧠 Did You Know",
        description=fact,
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.set_footer(text="Hamood wishes you a great life and healthy life!")
    
    await channel.send(embed=embed)
    await interaction.followup.send(f"Fact sent to {channel.mention}!", ephemeral=True)

@bot.tree.command(name="stats", description="Show fact bot statistics")
async def fact_stats(interaction: discord.Interaction):
    """Show statistics about used facts"""
    
    total_facts = len(fact_tracker.used_facts)
    embed = discord.Embed(
        title="📊 Fact Bot Statistics",
        color=0x2ecc71
    )
    embed.add_field(name="Total Unique Facts Sent", value=total_facts, inline=False)
    embed.add_field(name="Next Fact", value="Tomorrow at 12:00 PM", inline=False)
    await interaction.response.send_message(embed=embed)

# @bot.tree.command(name="setchannel", description="Set the channel for daily facts")
# @app_commands.describe(channel="The channel to send daily facts to (optional, defaults to current channel)")
# async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
#     """Set the channel for daily facts (Admin only)"""
#     if not interaction.user.guild_permissions.administrator:
#         await interaction.response.send_message("Only administrators can set the channel!", ephemeral=True)
#         return
    
#     if channel is None:
#         channel = interaction.channel
    
#     # Update environment variable (you'll need to restart bot for this to persist)
#     global CHANNEL_ID
#     CHANNEL_ID = channel.id
#     await interaction.response.send_message(f"Daily facts will now be sent to {channel.mention}")

# Error handling for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
    else:
        print(f"Slash command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while processing the command.", ephemeral=True)

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
        print("WARNING: CHANNEL_ID not set. Use !setchannel command after starting the bot.")
    
    # Run the bot
    bot.run(DISCORD_TOKEN)
