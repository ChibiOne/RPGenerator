import aioredis
import asyncio
import logging
import json
import pickle
from pathlib import Path

class RedisDatabaseSetup:
    def __init__(self):
        self.redis_url = 'redis://localhost'  # Change if using password: 'redis://:password@localhost'
        self.player_db = 0  # Redis DB number for player data
        self.game_db = 1    # Redis DB number for game data

    async def init_redis(self):
        """Initialize Redis connections"""
        try:
            # Connect to Redis
            self.player_redis = await aioredis.from_url(
                self.redis_url, 
                db=self.player_db,
                decode_responses=False
            )
            
            self.game_redis = await aioredis.from_url(
                self.redis_url,
                db=self.game_db,
                decode_responses=False
            )
            
            logging.info("Successfully connected to Redis")
            
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise

    async def clear_databases(self):
        """Clear existing data (be careful!)"""
        try:
            await self.player_redis.flushdb()
            await self.game_redis.flushdb()
            logging.info("Cleared existing Redis databases")
        except Exception as e:
            logging.error(f"Failed to clear databases: {e}")
            raise

    async def load_game_data(self):
        """Load initial game data from JSON files"""
        try:
            data_dir = Path('data')  # Adjust path as needed
            
            # Load areas
            if (data_dir / 'areas.json').exists():
                async with aiofiles.open(data_dir / 'areas.json', 'r') as f:
                    areas_data = json.loads(await f.read())
                    for area_name, area_data in areas_data.items():
                        await self.game_redis.hset(
                            "areas",
                            area_name,
                            pickle.dumps(area_data)
                        )
                logging.info(f"Loaded {len(areas_data)} areas")

            # Load items
            if (data_dir / 'items.json').exists():
                async with aiofiles.open(data_dir / 'items.json', 'r') as f:
                    items_data = json.loads(await f.read())
                    for item_name, item_data in items_data.items():
                        await self.game_redis.hset(
                            "items",
                            item_name,
                            pickle.dumps(item_data)
                        )
                logging.info(f"Loaded {len(items_data)} items")

            # Set version info
            await self.game_redis.set("game_data_version", "1.0")
            
        except Exception as e:
            logging.error(f"Failed to load game data: {e}")
            raise

    async def verify_setup(self):
        """Verify the database setup"""
        try:
            # Check game data
            areas_count = await self.game_redis.hlen("areas")
            items_count = await self.game_redis.hlen("items")
            version = await self.game_redis.get("game_data_version")
            
            logging.info(f"""
Database Setup Verification:
- Game Data Version: {version}
- Areas loaded: {areas_count}
- Items loaded: {items_count}
- Player DB Ready: {await self.player_redis.ping()}
- Game DB Ready: {await self.game_redis.ping()}
            """)
            
        except Exception as e:
            logging.error(f"Failed to verify setup: {e}")
            raise

async def setup_databases():
    """Run the database setup"""
    setup = RedisDatabaseSetup()
    
    try:
        # Initialize connections
        await setup.init_redis()
        
        # Clear existing data (comment out if you want to preserve data)
        await setup.clear_databases()
        
        # Load game data
        await setup.load_game_data()
        
        # Verify setup
        await setup.verify_setup()
        
        logging.info("Database setup completed successfully")
        
    except Exception as e:
        logging.error(f"Database setup failed: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_databases())