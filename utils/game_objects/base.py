# utils/game_objects/base.py

from typing import Optional, List, Dict, Any

class InventoryMixin:
    def __init__(self, inventory=None, capacity=None):
        self.inventory = inventory if inventory is not None else []
        self.capacity = capacity

    def add_item_to_inventory(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise TypeError("Only items of type 'Item' can be added to the inventory.")
        if self.can_add_item(item):
            self.inventory.append(item)
            print(f"Added {item.Name} to {self.__class__.__name__}'s inventory.")
        else:
            print(f"Cannot add {item.name}; inventory is full.")

    def remove_item_from_inventory(self, item_name):
        for item in self.inventory:
            if item.name == item_name:
                self.inventory.remove(item)
                print(f"Removed {item.name} from {self.__class__.__name__}'s inventory.")
                return item
        print(f"Item {item_name} not found in inventory.")
        return None

    def can_add_item(self, item):
        if self.capacity is None:
            return True  # Unlimited capacity

        current_weight = self.calculate_total_weight()
        if current_weight + item.weight <= self.capacity:
            return True
        else:
            return False

    def calculate_total_weight(self):
        return sum(item.weight for item in self.inventory)
    
    def transfer_item(from_entity, to_entity, item_name):
        item = from_entity.remove_item_from_inventory(item_name)
        if item:
            if to_entity.can_add_item(item):
                to_entity.add_item_to_inventory(item)
                print(f"Transferred {item.name} from {from_entity.name} to {to_entity.name}.")
            else:
                # Return item to original entity if transfer fails
                from_entity.add_item_to_inventory(item)
                print(f"Cannot transfer {item.name}; {to_entity.name}'s inventory is full.")

class Entity(InventoryMixin):
    def __init__(self, name=None, stats=None, inventory=None, **kwargs):
        super().__init__(inventory=inventory)  # Call InventoryMixin's __init__
        self.name = name
        self.stats = stats if stats else {}