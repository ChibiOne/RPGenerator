# utils/world/state_manager.py
import logging
import random
from typing import Dict, Any

class WorldStateManager:
    def __init__(self, bot):
        self.bot = bot
        self.npcs = {}
        self.area_lookup = {}

    async def update_npc_locations(self):
        """Move NPCs between areas based on their schedules and behaviors"""
        try:
            for npc in npcs.values():
                if random.random() < 0.1:  # 10% chance to move
                    current_area = npc.current_area
                    if current_area and current_area.connected_areas:
                        new_area = random.choice(current_area.connected_areas)
                        # Remove NPC from current area
                        current_area.npcs.remove(npc)
                        # Add NPC to new area
                        new_area.npcs.append(npc)
                        npc.current_area = new_area
                        logging.info(f"NPC {npc.Name} moved from {current_area.name} to {new_area.name}")
        except Exception as e:
            logging.error(f"Error updating NPC locations: {e}")

    async def update_area_inventories(self):
        """Update item spawns and removals in areas"""
        try:
            for area in area_lookup.values():
                # Chance to spawn new items
                if random.random() < 0.05:  # 5% chance
                    new_item = generate_random_item()
                    area.inventory.append(new_item)
                    logging.info(f"New item {new_item.Name} spawned in {area.name}")
                
                # Chance to remove old items
                if area.inventory and random.random() < 0.05:
                    removed_item = random.choice(area.inventory)
                    area.inventory.remove(removed_item)
                    logging.info(f"Item {removed_item.Name} removed from {area.name}")
        except Exception as e:
            logging.error(f"Error updating area inventories: {e}")

    async def update_npc_states(self):
        """Update NPC states, behaviors, and inventories"""
        try:
            for npc in npcs.values():
                # Update NPC health regeneration
                if npc.curr_hp < npc.max_hp:
                    npc.curr_hp = min(npc.max_hp, npc.curr_hp + 1)
                
                # Update NPC inventory
                if random.random() < 0.1:  # 10% chance
                    if len(npc.inventory) > 0:
                        # Maybe trade or drop items
                        pass
                    else:
                        # Maybe acquire new items
                        pass
                
                # Update NPC attitude/relationships
                for other_npc in npcs.values():
                    if other_npc != npc and random.random() < 0.01:  # 1% chance
                        # Modify relationships based on proximity, events, etc.
                        pass
        except Exception as e:
            logging.error(f"Error updating NPC states: {e}")

    def save_world_state(self):
        """Save the current state of the dynamic world"""
        try:
            # Save current NPC states
            save_npcs(npcs)
            
            # Save current area states
            save_areas(area_lookup)
            
            logging.info("World state saved successfully")
        except Exception as e:
            logging.error(f"Error saving world state: {e}")

    async def update_world_state(self):
        """Update dynamic aspects of the world periodically"""
        try:
            # Update NPC positions
            await update_npc_locations()
            
            # Update available items in areas
            await update_area_inventories()
            
            # Update NPC states (like health, inventory, etc.)
            await update_npc_states()
            
            # Save current world state
            save_world_state()
            
        except Exception as e:
            logging.error(f"Error updating world state: {e}")

def assign_npcs_to_areas(area_lookup, npc_lookup):
    for area in area_lookup.values():
        area.npcs = [npc_lookup[npc_name] for npc_name in area.npc_names if npc_name in npc_lookup]