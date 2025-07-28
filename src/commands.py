"""
Discord slash commands
"""

import discord
from discord import app_commands
from datetime import datetime
import json
import os
from datetime import timedelta


# Rate limiting functions
def load_rate_limits():
    """Load rate limiting data from file"""
    try:
        rate_limit_file = "rate_limits.json"
        if os.path.exists(rate_limit_file):
            with open(rate_limit_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading rate limits: {e}")
    return {}


def save_rate_limits(rate_limits):
    """Save rate limiting data to file"""
    try:
        rate_limit_file = "rate_limits.json"
        with open(rate_limit_file, 'w') as f:
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


def setup_commands(bot, fact_generator, fact_tracker, vector_store, channel_id):
    """Setup all slash commands"""
    
    from events import load_historical_messages
    
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
        channel = bot.get_channel(channel_id)
        if not channel:
            await interaction.followup.send(f"Channel with ID {channel_id} not found!", ephemeral=True)
            return
        
        # Generate and send fact to the channel
        if player:
            # Try to find the user by name or mention
            user_id = None
            if player.startswith('<@') and player.endswith('>'):
                # Extract user ID from mention
                user_id = player[2:-1].replace('!', '')
            
            fact = await fact_generator.generate_player_fact_with_rag(player, user_id)
            title = f"🧠 Did You Know About {player}"
        else:
            fact = await fact_generator.generate_player_fact_with_rag()
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
            await load_historical_messages(bot, vector_store)
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
            name="🎭 Personality Cards", 
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

    @bot.tree.command(name="playerfact", description="Generate a personality card for a specific player")
    @app_commands.describe(player="The player to generate a personality card for")
    async def player_fact_command(interaction: discord.Interaction, player: discord.User):
        """Generate a personality card for a specific player with rate limiting"""
        # Check rate limit first
        remaining_uses = get_remaining_uses(str(interaction.user.id), "playerfact")
        
        if not check_and_update_rate_limit(str(interaction.user.id), "playerfact"):
            await interaction.response.send_message(
                f"You've reached your daily limit of 3 personality cards! Please try again tomorrow. 🕒", 
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
            
            # Generate personality card instead of a simple fact
            personality_card = await fact_generator.generate_personality_card(player_name, user_id)
            
            # Show remaining uses
            new_remaining = get_remaining_uses(str(interaction.user.id), "playerfact")
            
            # Create personality card embed
            embed = discord.Embed(
                title="🎭 Personality Card",
                color=0x9b59b6,
                timestamp=datetime.now()
            )
            
            # Add name field
            embed.add_field(
                name="👤 Name", 
                value=f"**{personality_card.name}**", 
                inline=False
            )
            
            # Add positive traits
            positive_traits_text = " • ".join([f"✨ {trait}" for trait in personality_card.positive_traits])
            embed.add_field(
                name="💚 Positive Traits", 
                value=positive_traits_text, 
                inline=False
            )
            
            # Add negative traits (but call them "quirks" to be nicer)
            negative_traits_text = " • ".join([f"🤔 {trait}" for trait in personality_card.negative_traits])
            embed.add_field(
                name="🔸 Quirks & Flaws", 
                value=negative_traits_text, 
                inline=False
            )
            
            # Add what they yap about
            embed.add_field(
                name="💬 Yaps A Lot About", 
                value=f"🗣️ **{personality_card.yaps_about}**", 
                inline=False
            )
            
            # Add fun stat (roast)
            embed.add_field(
                name="📊 Fun Stat", 
                value=f"🔥 {personality_card.fun_stat}", 
                inline=False
            )
            
            embed.set_footer(text=f"Powered by Hamood's Smart AI! • {new_remaining} uses remaining today")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error generating personality card: {e}")
            await interaction.followup.send("Sorry, I couldn't generate a personality card for that player right now.", ephemeral=True)

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