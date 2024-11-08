async def sync_commands(bot):
    """
    Synchronize commands to all configured guilds with rate limit awareness
    """
    try:
        successful_syncs = 0
        total_guilds = len(GUILD_CONFIGS)
        
        # First sync globally with rate limit handling
        try:
            await bot.sync_commands()
            logging.info("Synced commands globally")
        except discord.HTTPException as e:
            if e.code == 429:
                logging.warning(f"Rate limited during global sync. Waiting {e.retry_after} seconds")
                await asyncio.sleep(e.retry_after)
                await bot.sync_commands()
            else:
                logging.error(f"Error syncing commands globally: {e}")
        
        # Sync to specific guilds with rate limiting
        for guild_id in GUILD_CONFIGS:
            try:
                shard_id = (guild_id >> 22) % bot.shard_count if bot.shard_count else None
                if shard_id is not None and shard_id not in bot.shards:
                    continue  # Skip if guild doesn't belong to this shard
                    
                success = await bot.sync_guild_commands(guild_id)
                if success:
                    successful_syncs += 1
                    logging.info(f"Successfully synced commands to guild {guild_id} (Shard: {shard_id})")
                
            except discord.Forbidden:
                logging.error(f"Missing permissions to sync commands in guild {guild_id}")
            except discord.HTTPException as e:
                logging.error(f"HTTP error syncing commands to guild {guild_id}: {e}")
            except Exception as e:
                logging.error(f"Error syncing commands to guild {guild_id}: {e}")
        
        if successful_syncs == total_guilds:
            logging.info(f"Successfully synced commands to all {total_guilds} guilds")
        else:
            logging.warning(f"Synced commands to {successful_syncs}/{total_guilds} guilds")
            
    except Exception as e:
        logging.error(f"Error in sync_commands: {e}", exc_info=True)

async def main():
    try:
        # First set up sharding
        await setup_sharding(bot)
        
        # Then start the bot with your token
        async with bot:
            await bot.start(DISCORD_BOT_TOKEN)
            
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        return