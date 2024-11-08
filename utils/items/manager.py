# utils/items/manager.py
from typing import Dict, Optional, List, Union, Any
import logging
import json
import pickle
from pathlib import Path
from .item import Item, Weapon, Armor, Shield  # Your existing item classes

class ItemManager:
    """Manages item loading, caching, and retrieval"""
    
    def __init__(self, bot):
        self.bot = bot
        self.items: Dict[str, Item] = {}
        self.items_cache: Dict[str, Item] = {}
        self.cache_duration = 3600  # 1 hour cache
        self.logger = logging.getLogger('item_manager')

    async def initialize(self):
        """Initialize the item manager and load items"""
        try:
            # Try loading from Redis first
            items_data = await self.bot.redis_game.get('items_cache')
            if items_data:
                self.items = pickle.loads(items_data)
                self.logger.info(f"Loaded {len(self.items)} items from Redis cache")
                return

            # If not in Redis, load from JSON
            await self.load_items_from_json()
            
            # Cache in Redis
            await self.bot.redis_game.set(
                'items_cache',
                pickle.dumps(self.items),
                ex=self.cache_duration
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing ItemManager: {e}")
            raise

    async def load_items_from_json(self):
        """Load items from JSON file"""
        try:
            items_file = Path('data/items.json')
            if not items_file.exists():
                self.logger.error("Items file not found")
                return

            with items_file.open('r', encoding='utf-8') as f:
                items_data = json.load(f)

            for item_name, item_data in items_data.items():
                try:
                    item = self.create_item(item_data)
                    if item:
                        self.items[item_name] = item
                except Exception as e:
                    self.logger.error(f"Error loading item {item_name}: {e}")

            self.logger.info(f"Loaded {len(self.items)} items from JSON")

        except Exception as e:
            self.logger.error(f"Error loading items from JSON: {e}")
            raise

    def create_item(self, item_data: Dict[str, Any]) -> Optional[Item]:
        """Create appropriate item instance based on type"""
        try:
            item_type = item_data.get('Type', '').lower()
            
            if item_type == 'weapon':
                return Weapon(
                    name=item_data.get('Name', ''),
                    weight=item_data.get('Weight', 0),
                    damage_amount=item_data.get('Damage_Amount', '1d4'),
                    damage_type=item_data.get('Damage_Type', 'bludgeoning'),
                    description=item_data.get('Description', ''),
                    effect=item_data.get('Effect'),
                    proficiency_needed=item_data.get('Proficiency_Needed'),
                    average_cost=item_data.get('Average_Cost', 0),
                    is_magical=item_data.get('Is_Magical', False),
                    rarity=item_data.get('Rarity', 'Common')
                )
            
            elif item_type == 'armor':
                return Armor(
                    name=item_data.get('Name', ''),
                    weight=item_data.get('Weight', 0),
                    ac_value=item_data.get('AC_Value', 10),
                    max_dex_bonus=item_data.get('Max_Dex_Bonus', None),
                    description=item_data.get('Description', ''),
                    effect=item_data.get('Effect'),
                    proficiency_needed=item_data.get('Proficiency_Needed'),
                    average_cost=item_data.get('Average_Cost', 0),
                    is_magical=item_data.get('Is_Magical', False),
                    rarity=item_data.get('Rarity', 'Common')
                )
            
            elif item_type == 'shield':
                return Shield(
                    name=item_data.get('Name', ''),
                    weight=item_data.get('Weight', 0),
                    ac_value=item_data.get('AC_Value', 2),
                    max_dex_bonus=item_data.get('Max_Dex_Bonus', None),
                    description=item_data.get('Description', ''),
                    effect=item_data.get('Effect'),
                    proficiency_needed=item_data.get('Proficiency_Needed'),
                    average_cost=item_data.get('Average_Cost', 0),
                    is_magical=item_data.get('Is_Magical', False),
                    rarity=item_data.get('Rarity', 'Common')
                )
            
            else:
                return Item(
                    name=item_data.get('Name', ''),
                    weight=item_data.get('Weight', 0),
                    item_type=item_data.get('Type', 'misc'),
                    description=item_data.get('Description', ''),
                    effect=item_data.get('Effect'),
                    proficiency_needed=item_data.get('Proficiency_Needed'),
                    average_cost=item_data.get('Average_Cost', 0),
                    is_magical=item_data.get('Is_Magical', False),
                    rarity=item_data.get('Rarity', 'Common')
                )

        except Exception as e:
            self.logger.error(f"Error creating item: {e}")
            return None

    async def get_item(self, item_name: str) -> Optional[Item]:
        """Get an item by name"""
        try:
            # Check cache first
            item = self.items_cache.get(item_name)
            if item:
                return item

            # Check main items dictionary
            item = self.items.get(item_name)
            if item:
                # Add to cache
                self.items_cache[item_name] = item
                return item

            # If not found, try Redis
            item_data = await self.bot.redis_game.hget('items', item_name)
            if item_data:
                item = pickle.loads(item_data)
                self.items_cache[item_name] = item
                return item

            return None

        except Exception as e:
            self.logger.error(f"Error getting item {item_name}: {e}")
            return None

    async def save_item(self, item: Item) -> bool:
        """Save or update an item"""
        try:
            self.items[item.Name] = item
            self.items_cache[item.Name] = item
            
            # Save to Redis
            await self.bot.redis_game.hset(
                'items',
                item.Name,
                pickle.dumps(item)
            )
            return True

        except Exception as e:
            self.logger.error(f"Error saving item {item.Name}: {e}")
            return False

    async def delete_item(self, item_name: str) -> bool:
        """Delete an item"""
        try:
            if item_name in self.items:
                del self.items[item_name]
            if item_name in self.items_cache:
                del self.items_cache[item_name]
                
            # Remove from Redis
            await self.bot.redis_game.hdel('items', item_name)
            return True

        except Exception as e:
            self.logger.error(f"Error deleting item {item_name}: {e}")
            return False

    def clear_cache(self):
        """Clear the item cache"""
        self.items_cache.clear()

    async def reload_items(self) -> bool:
        """Reload all items from storage"""
        try:
            self.clear_cache()
            await self.initialize()
            return True
        except Exception as e:
            self.logger.error(f"Error reloading items: {e}")
            return False