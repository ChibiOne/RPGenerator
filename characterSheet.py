class Character:
    def __init__(self, name):
        self.name = name
        self.stats = {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }
        self.skills = {
            'Athletics': 0,
            'Acrobatics': 0,
            # Add other skills as needed
        }
        # Additional attributes like inventory, level, experience, etc.

    def get_stat_modifier(self, stat):
        # Convert stat to a modifier (D&D style)
        return (self.stats[stat] - 10) // 2