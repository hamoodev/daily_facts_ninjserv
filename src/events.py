"""
Discord event handlers
"""

import discord
from discord.ext import tasks
from datetime import datetime, time


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


async def load_historical_messages(bot, vector_store):
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


def setup_events(bot, vector_store, fact_generator, fact_tracker, score_manager, channel_id):
    """Setup all Discord event handlers"""
    
    # Import setup_commands here to avoid circular imports
    from commands import setup_commands
    
    @bot.event
    async def on_ready():
        print(f'{bot.user} has connected to Discord!')
        print(f'Bot is in {len(bot.guilds)} guilds')
        
        # Connect to vector store
        try:
            await vector_store.connect()
            print("Vector store connected successfully!")
            
            # Load historical messages on startup (commented out for now)
            # print("Loading historical messages...")
            # await load_historical_messages(bot, vector_store)
            
        except Exception as e:
            print(f"Warning: Vector store connection failed: {e}")
            print("Bot will continue with limited functionality")
        
        # Setup commands (needs to be async)
        try:
            await setup_commands(bot, fact_generator, fact_tracker, vector_store, score_manager, channel_id)
            print("Commands setup completed successfully!")
        except Exception as e:
            print(f"Error setting up commands: {e}")
        
        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
        
        # Start the daily fact task
        if not daily_fact.is_running():
            daily_fact.start()

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

    @tasks.loop(time=time(6, 0))  # Send at 6:00 AM every day
    async def daily_fact():
        """Send daily fact to specified channel"""
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"Channel with ID {channel_id} not found!")
                return
            
            print("Generating daily player fact...")
            
            # Try to generate a player-specific fact using RAG
            fact = await fact_generator.generate_player_fact_with_rag()
            
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

    # Error handling for events
    @bot.event
    async def on_command_error(ctx, error):
        from discord.ext import commands
        
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command!")
        else:
            print(f"Error: {error}")
            await ctx.send("An error occurred while processing the command.")

    return daily_fact 