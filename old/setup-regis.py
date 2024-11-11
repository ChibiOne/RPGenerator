import redis.asyncio as redis
import asyncio
import logging
import json
import pickle
from pathlib import Path
import aiofiles

class RedisDatabaseSetup:
    def __init__(self):
        self.redis_url = 'redis://localhost'
        self.player_db = 0
        self.game_db = 1
        self.player_redis = None
        self.game_redis = None

    async def init_redis(self):
        """Initialize Redis connections"""
        try:
            self.player_redis = await redis.from_url(
                self.redis_url, 
                db=self.player_db,
                decode_responses=False
            )
            
            self.game_redis = await redis.from_url(
                self.redis_url,
                db=self.game_db,
                decode_responses=False
            )
            
            logging.info("Successfully connected to Redis")
            
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise

    async def cleanup(self):
        """Properly close Redis connections"""
        if self.player_redis:
            await self.player_redis.close()
        if self.game_redis:
            await self.game_redis.close()

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
            data_dir = Path('data')
            
            # Create data directory if it doesn't exist
            data_dir.mkdir(exist_ok=True)
            
            # Load areas if file exists
            areas_path = data_dir / 'areas.json'
            if areas_path.exists():
                with open(areas_path, 'r') as f:
                    areas_data = json.load(f)
                    for area_name, area_data in areas_data.items():
                        await self.game_redis.hset(
                            "areas",
                            area_name,
                            pickle.dumps(area_data)
                        )
                logging.info(f"Loaded {len(areas_data)} areas")
            else:
                logging.warning(f"No areas.json found in {data_dir}")

            # Load items if file exists
            items_path = data_dir / 'items.json'
            if items_path.exists():
                with open(items_path, 'r') as f:
                    items_data = json.load(f)
                    for item_name, item_data in items_data.items():
                        await self.game_redis.hset(
                            "items",
                            item_name,
                            pickle.dumps(item_data)
                        )
                logging.info(f"Loaded {len(items_data)} items")
            else:
                logging.warning(f"No items.json found in {data_dir}")

            # Set version info
            await self.game_redis.set("game_data_version", "1.0")
            
        except Exception as e:
            logging.error(f"Failed to load game data: {e}")
            raise

    async def verify_setup(self):
        """Verify the database setup"""
        try:
            areas_count = await self.game_redis.hlen("areas")
            items_count = await self.game_redis.hlen("items")
            version = await self.game_redis.get("game_data_version")
            
            logging.info(f"""
Database Setup Verification:
- Game Data Version: {version.decode() if version else None}
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
        await setup.init_redis()
        await setup.clear_databases()
        await setup.load_game_data()
        await setup.verify_setup()
        logging.info("Database setup completed successfully")
        
    except Exception as e:
        logging.error(f"Database setup failed: {e}")
        raise
    
    finally:
        await setup.cleanup()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_databases())