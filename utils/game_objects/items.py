# utils/game_objects/items.py
from typing import Optional, Dict, Any, Tuple, Union, List, TypeVar, Type
import logging
import random

# Remove circular import, base.py will use string literal for type hints
T = TypeVar('T', bound='Item')  # For class methods

class Item:
    def __init__(
        self, 
        name: str,
        weight: float,
        item_type: str,
        description: str = '',
        effect: Optional[Union[Dict[str, Any], str]] = None,
        proficiency_needed: Optional[str] = None,
        average_cost: float = 0.0,
        is_magical: bool = False,
        rarity: str = 'Common'
    ):
        self.name = name
        self.weight = weight
        self.type = item_type
        self.description = description
        self.effect = self._parse_effect(effect)
        self.proficiency_needed = proficiency_needed
        self.average_cost = average_cost
        self.is_magical = is_magical
        self.rarity = rarity

    def to_dict(self) -> Dict[str, Any]:
        """Convert Item instance to dictionary."""
        try:
            effect_dict = {}
            if self.effect:
                if not isinstance(self.effect, dict):
                    logging.error(f"Effect is not a dict for item {self.name}: {type(self.effect)}")
                else:
                    for key, effect in self.effect.items():
                        try:
                            if isinstance(effect, dict) and effect.get('type') == 'code':
                                effect_dict[key] = f"code:{effect['code']}"
                            else:
                                effect_dict[key] = effect.get('value', effect)
                        except Exception as e:
                            logging.error(f"Error converting effect {key} for item {self.name}: {e}")
                            effect_dict[key] = str(effect)

            return {
                'name': self.name,
                'weight': self.weight,
                'type': self.type,
                'description': self.description,
                'effect': effect_dict,
                'proficiency_needed': self.proficiency_needed,
                'average_cost': self.average_cost,
                'is_magical': self.is_magical,
                'rarity': self.rarity
            }
        except Exception as e:
            logging.error(f"Error in Item.to_dict for {self.name}: {e}")
            raise

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create an item instance from dictionary data."""
        try:
            name = data.get('name')
            if not name:
                raise ValueError("Item name is required")
                
            weight = data.get('weight', 0.0)
            if not isinstance(weight, (int, float)):
                logging.warning(f"Invalid weight for item {name}, defaulting to 0")
                weight = 0.0
                
            item_type = data.get('type')
            if not item_type:
                logging.warning(f"No type specified for item {name}, defaulting to 'Item'")
                item_type = 'Item'

            return cls(
                name=name,
                weight=weight,
                item_type=item_type,
                description=data.get('description', 'No description available'),
                effect=data.get('effect'),
                proficiency_needed=data.get('proficiency_needed'),
                average_cost=data.get('average_cost', 0.0),
                is_magical=data.get('is_magical', False),
                rarity=data.get('rarity', 'Common')
            )
        except Exception as e:
            logging.error(f"Error creating item from data: {e}")
            raise

    def _parse_effect(self, effect: Optional[Union[Dict[str, Any], str]]) -> Dict[str, Any]:
        """Parse effect data which could be simple values or code."""
        if not effect:
            return {}
                
        if isinstance(effect, dict):
            parsed_effect = {}
            for key, value in effect.items():
                if isinstance(value, str) and value.startswith('code:'):
                    parsed_effect[key] = {
                        'type': 'code',
                        'code': value[5:].strip(),
                        'compiled': compile(value[5:].strip(), f'{self.name}_{key}_effect', 'exec')
                    }
                else:
                    parsed_effect[key] = {'type': 'value', 'value': value}
            return parsed_effect
            
        logging.info(f"Unexpected effect type for item {self.name}, defaulting to empty dict")
        return {}

    def get_ac_bonus(self) -> int:
        """Get AC bonus from item if it provides one."""
        if self.effect and 'AC' in self.effect:
            return self.effect['AC'].get('value', 0) if isinstance(self.effect['AC'], dict) else self.effect['AC']
        return 0

    def get_damage(self) -> Optional[Dict[str, str]]:
        """Get damage dice and type if item is a weapon."""
        if self.effect and 'Damage' in self.effect:
            return {
                'dice': self.effect['Damage'].get('value', '1d4') if isinstance(self.effect['Damage'], dict) else self.effect['Damage'],
                'type': self.effect.get('Damage_Type', {}).get('value', 'Bludgeoning') if isinstance(self.effect.get('Damage_Type'), dict) else self.effect.get('Damage_Type', 'Bludgeoning')
            }
        return None

    def get_healing(self) -> int:
        """Get healing amount if item provides healing."""
        if self.effect and 'Heal' in self.effect:
            return self.effect['Heal'].get('value', 0) if isinstance(self.effect['Heal'], dict) else self.effect['Heal']
        return 0

    def can_be_equipped(self, slot: str) -> bool:
        """Check if item can be equipped in given slot."""
        slot_types = {
            'Armor': ['Armor'],
            'Left_Hand': ['Weapon', 'Shield'],
            'Right_Hand': ['Weapon'],
            'Belt_Slots': ['Consumable', 'Equipment'],
            'Back': ['Equipment'],
            'Magic_Slots': ['Equipment', 'Consumable']
        }
        return self.type in slot_types.get(slot, [])

    def check_proficiency(self, character: Any) -> bool:
        """Check if character has required proficiency."""
        if not self.proficiency_needed:
            return True
        return hasattr(character, 'proficiencies') and self.proficiency_needed in character.proficiencies

    def calculate_stat_changes(self) -> Dict[str, Union[int, float]]:
        """Calculate how this item affects character stats when equipped."""
        changes = {}
        
        if self.type in ["Armor", "Shield"]:
            changes['AC'] = self.get_ac_bonus()
        
        if self.is_magical and self.effect:
            for stat, value in self.effect.items():
                if stat not in ['Damage', 'Damage_Type', 'AC', 'Heal']:
                    changes[stat] = value.get('value', 0) if isinstance(value, dict) else value
                    
        return changes

    def apply_equip_effects(self, character: Any) -> bool:
        """Apply item effects when equipped."""
        if not self.check_proficiency(character):
            logging.warning(f"{character.name} lacks proficiency for {self.name}")
            return False
            
        stat_changes = self.calculate_stat_changes()
        for stat, value in stat_changes.items():
            if stat == 'AC':
                character.ac += value
            elif hasattr(character, stat.lower()):
                current_value = getattr(character, stat.lower())
                setattr(character, stat.lower(), current_value + value)

        return True

    def remove_equip_effects(self, character: Any) -> None:
        """Remove item effects when unequipped."""
        stat_changes = self.calculate_stat_changes()
        for stat, value in stat_changes.items():
            if stat == 'AC':
                character.ac -= value
            elif hasattr(character, stat.lower()):
                current_value = getattr(character, stat.lower())
                setattr(character, stat.lower(), current_value - value)

    def use_consumable(self, character: Any) -> Tuple[bool, str]:
        """Use a consumable item and apply its effects."""
        if self.type != 'Consumable':
            return False, "This item cannot be consumed"

        if 'Heal' in self.effect:
            healing = self.get_healing()
            old_hp = character.curr_hp
            character.curr_hp = min(character.max_hp, character.curr_hp + healing)
            actual_healing = character.curr_hp - old_hp
            return True, f"Healed for {actual_healing} HP"

        return False, "This item has no consumable effect"

    def roll_damage(self) -> Tuple[int, Optional[str]]:
        """Roll damage for weapon."""
        damage_info = self.get_damage()
        if not damage_info:
            return 0, None

        try:
            num_dice, dice_size = map(int, damage_info['dice'].lower().split('d'))
            total_damage = sum(random.randint(1, dice_size) for _ in range(num_dice))
            return total_damage, damage_info['type']
        except Exception as e:
            logging.error(f"Error rolling damage for {self.name}: {e}")
            return 0, None

    def update(self, **kwargs: Any) -> None:
        """Update the item's attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        return f"<Item: {self.name} ({self.type})>"

class Weapon(Item):
    def __init__(
        self,
        damage_amount: str,
        damage_type: str,
        equip: bool = True,
        **kwargs: Any
    ):
        super().__init__(item_type='Weapon', **kwargs)
        self.damage_amount = damage_amount
        self.damage_type = damage_type
        self.equip = equip
        self.effect = {'Damage_Amount': self.damage_amount, 'Damage_Type': self.damage_type}
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'damage_amount': self.damage_amount,
            'damage_type': self.damage_type,
            'equip': self.equip
        })
        return data

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(
            name=data.get('name', ''),
            weight=data.get('weight', 0.0),
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0.0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            damage_amount=data.get('damage_amount', '1d4'),
            damage_type=data.get('damage_type', 'Bludgeoning'),
            equip=data.get('equip', True)
        )

class Armor(Item):
    def __init__(
        self,
        ac_value: int,
        max_dex_bonus: int,
        equip: bool = True,
        **kwargs: Any
    ):
        super().__init__(item_type='Armor', **kwargs)
        self.ac_value = ac_value
        self.max_dex_bonus = max_dex_bonus
        self.equip = equip
        self.effect = {'AC': self.ac_value, 'Max_Dex_Bonus': self.max_dex_bonus}
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'ac_value': self.ac_value,
            'max_dex_bonus': self.max_dex_bonus,
            'equip': self.equip
        })
        return data

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(
            name=data.get('name', ''),
            weight=data.get('weight', 0.0),
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0.0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            ac_value=data.get('ac_value', 10),
            max_dex_bonus=data.get('max_dex_bonus', 0),
            equip=data.get('equip', True)
        )

class Shield(Item):
    def __init__(
        self,
        ac_value: int,
        equip: bool = True,
        **kwargs: Any
    ):
        super().__init__(item_type='Shield', **kwargs)
        self.ac_value = ac_value
        self.equip = equip
        self.effect = {'AC': self.ac_value}
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'ac_value': self.ac_value,
            'equip': self.equip
        })
        return data

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(
            name=data.get('name', ''),
            weight=data.get('weight', 0.0),
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0.0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            ac_value=data.get('ac_value', 2),
            equip=data.get('equip', True)
        )