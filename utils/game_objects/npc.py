# utils/game_objects/npc.py
import logging
import random
from typing import Optional, Dict, List, Any, Union

from .base import Entity
from .items import Item, Weapon

class NPC(Entity):
    """
    Represents a non-player character in the game world.
    """
    def __init__(
            self,
            name: Optional[str] = None,
            role: Optional[str] = None,
            inventory: Optional[List[Item]] = None,
            capacity: Optional[float] = None,
            stats: Optional[Dict[str, int]] = None,
            movement_speed: Optional[int] = None,
            travel_end_time: Optional[float] = None,
            max_hp: Optional[int] = None,
            curr_hp: Optional[int] = None,
            spellslots: Optional[Dict[str, int]] = None,
            ac: Optional[int] = None,
            abilities: Optional[Dict[str, Any]] = None,
            spells: Optional[Dict[str, Any]] = None,
            attitude: Optional[str] = None,
            faction: Optional[str] = None,
            reputation: Optional[Dict[str, int]] = None,
            relations: Optional[Dict[str, Any]] = None,
            dialogue: Optional[List[str]] = None,
            description: Optional[str] = None,
            is_hostile: Optional[bool] = None,
            current_area: Optional['Area'] = None,
            **kwargs: Any
    ):
        # Call Entity's __init__ with name parameter
        super().__init__(name=name, stats=stats, inventory=inventory, **kwargs)
        
        self.role = role
        self.movement_speed = movement_speed if movement_speed is not None else 30
        self.travel_end_time = travel_end_time
        self.max_hp = max_hp if max_hp is not None else 10
        self.curr_hp = curr_hp if curr_hp is not None else self.max_hp
        self.spellslots = spellslots or {}
        self.ac = ac if ac is not None else 10
        self.abilities = abilities or {}
        self.spells = spells or {}
        self.attitude = attitude
        self.faction = faction
        self.reputation = reputation or {}
        self.relations = relations or {}
        self.dialogue = dialogue or []
        self.description = description
        self.is_hostile = is_hostile if is_hostile is not None else False
        self.current_area = current_area

    def to_dict(self) -> Dict[str, Any]:
        """Convert NPC instance to dictionary."""
        try:
            return {
                'Name': self.name,
                'Description': self.description,
                'Dialogue': self.dialogue,
                'Inventory': [item.to_dict() for item in self.inventory if hasattr(item, 'to_dict')],
                'Stats': self.stats,
                'Is_Hostile': self.is_hostile,
                'Role': self.role,
                'Movement_Speed': self.movement_speed,
                'Travel_End_Time': self.travel_end_time,
                'Max_HP': self.max_hp,
                'Curr_HP': self.curr_hp,
                'Spellslots': self.spellslots,
                'AC': self.ac,
                'Abilities': self.abilities,
                'Spells': self.spells,
                'Attitude': self.attitude,
                'Faction': self.faction,
                'Reputation': self.reputation,
                'Relations': self.relations
            }
        except Exception as e:
            logging.error(f"Error converting NPC {self.name} to dict: {e}")
            raise

    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_lookup: Dict[str, Item]) -> 'NPC':
        """Create an NPC instance from dictionary data."""
        try:
            logging.info(f"Creating NPC from data: {data}")
            name = data.get('Name')
            if not name:
                logging.error("No name provided in NPC data")
                raise ValueError("NPC name is required")
                
            inventory_names = data.get('Inventory', [])
            inventory = [item_lookup[item_name] for item_name in inventory_names 
                        if item_name in item_lookup]
            
            npc = cls(
                name=name,
                description=data.get('Description', ''),
                role=data.get('Role'),
                dialogue=data.get('Dialogue', []),
                inventory=inventory,
                stats=data.get('Stats', {}),
                is_hostile=data.get('Is_Hostile', False),
                movement_speed=data.get('Movement_Speed'),
                travel_end_time=data.get('Travel_End_Time'),
                max_hp=data.get('Max_HP'),
                curr_hp=data.get('Curr_HP'),
                spellslots=data.get('Spellslots'),
                ac=data.get('AC'),
                abilities=data.get('Abilities'),
                spells=data.get('Spells'),
                attitude=data.get('Attitude'),
                faction=data.get('Faction'),
                reputation=data.get('Reputation'),
                relations=data.get('Relations')
            )
            logging.info(f"Successfully created NPC: {name}")
            return npc
        except Exception as e:
            logging.error(f"Error creating NPC: {e}")
            raise

    def move_to_area(self, new_area: 'Area') -> bool:
        """Move NPC to a new area."""
        try:
            if self.current_area:
                self.current_area.remove_npc(self.name)
            self.current_area = new_area
            new_area.add_npc(self)
            return True
        except Exception as e:
            logging.error(f"Error moving NPC {self.name} to new area: {e}")
            return False
    
    def attack(self, target: Union['Character', 'NPC'], weapon: Weapon) -> str:
        """
        Perform an attack on a target using a weapon.
        Args:
            target: The target character or NPC
            weapon: The weapon being used
        Returns:    
            str: The result of the attack
        """
        try:
            # Calculate the attack roll
            attack_roll = random.randint(1, 20) + self.get_stat_modifier('Strength')
            # Calculate the damage roll
            damage_roll = random.randint(1, weapon.damage_amount) + self.get_stat_modifier('Strength')
            # Apply the damage to the target
            target.curr_hp = max(0, target.curr_hp - damage_roll)
            return f"{self.name} attacks {target.name} with {weapon.name} for {damage_roll} damage."
        except Exception as e:
            logging.error(f"Error during attack from {self.name}: {e}")
            return f"{self.name}'s attack failed."
    
    def get_dialogue(self) -> str:
        """Get the next dialogue line for this NPC."""
        try:
            if self.dialogue:
                return self.dialogue.pop(0)
            return f"{self.name} has nothing more to say."
        except Exception as e:
            logging.error(f"Error getting dialogue for {self.name}: {e}")
            return f"{self.name} is unable to speak at the moment."
        
    def update(self, **kwargs: Any) -> None:
        """Update the NPC's attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'Inventory':
                    if isinstance(value, list):
                        self.inventory = value
                elif hasattr(self, key.lower()):  # Convert to lowercase for consistency
                    setattr(self, key.lower(), value)
        except Exception as e:
            logging.error(f"Error updating NPC {self.name}: {e}")
            
    def get_stat_modifier(self, stat: str) -> int:
        """Calculate the modifier for a given ability score."""
        try:
            return (self.stats.get(stat, 10) - 10) // 2
        except Exception as e:
            logging.error(f"Error calculating {stat} modifier for {self.name}: {e}")
            return 0