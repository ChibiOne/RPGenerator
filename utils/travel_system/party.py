# utils/travel_system/party.py
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

@dataclass
class TravelParty:
    """Represents a group of traveling characters"""
    leader_id: str
    members: Dict[str, 'Character']
    guild_id: str

    @property
    def leader(self) -> Optional['Character']:
        """Get the party leader"""
        return self.members.get(self.leader_id)
    
    def get_slowest_member(self) -> 'Character':
        """Determine the slowest party member"""
        return min(self.members.values(), key=lambda x: x.movement_speed)
    
    def get_lowest_health(self) -> 'Character':
        """Get the member with lowest health percentage"""
        return min(self.members.values(), 
                  key=lambda x: (x.curr_hp / x.max_hp if x.max_hp > 0 else 0))
    
    def get_member_names(self) -> List[str]:
        """Get list of member names"""
        return [char.name for char in self.members.values()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert party to dictionary for storage"""
        return {
            'leader_id': self.leader_id,
            'members': {uid: char.to_dict() for uid, char in self.members.items()},
            'guild_id': self.guild_id
        }
    
    @classmethod
    async def from_dict(cls, data: Dict[str, Any], bot) -> 'TravelParty':
        """Create party instance from dictionary data"""
        try:
            members = {}
            for uid, char_data in data['members'].items():
                char = await bot.get_character(uid, data['guild_id'])
                if char:
                    members[uid] = char
            
            return cls(
                leader_id=data['leader_id'],
                members=members,
                guild_id=data['guild_id']
            )
        except Exception as e:
            bot.logger.error(f"Error creating party from dict: {e}")
            return None

    def __len__(self) -> int:
        return len(self.members)