# utils/character/types.py
from typing import TypedDict, Dict, Optional, List, Union, Literal
from datetime import datetime

# Valid Species and Classes
SpeciesType = Literal["Human", "Elf", "Dwarf", "Orc"]
ClassType = Literal["Warrior", "Mage", "Rogue", "Cleric"]
StatType = Literal["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]

# Item Types
ItemType = Literal["Weapon", "Armor", "Shield", "Consumable", "Equipment"]

# Equipment Slots
EquipmentSlotType = Literal[
    "Armor",
    "Left_Hand",
    "Right_Hand",
    "Back",
    "Belt_Slots",
    "Magic_Slots"
]

class Stats(TypedDict):
    Strength: int
    Dexterity: int
    Constitution: int
    Intelligence: int
    Wisdom: int
    Charisma: int

class Equipment(TypedDict):
    Armor: Optional['Item']
    Left_Hand: Optional['Item']
    Right_Hand: Optional['Item']
    Back: Optional['Item']
    Belt_Slots: List[Optional['Item']]
    Magic_Slots: List[Optional['Item']]

class CharacterData(TypedDict):
    user_id: str
    name: str
    species: SpeciesType
    char_class: ClassType
    gender: str
    pronouns: str
    description: str
    stats: Stats
    equipment: Equipment
    inventory: Dict[str, 'Item']
    creation_date: datetime
    last_modified: datetime
    last_interaction_guild: Optional[int]
