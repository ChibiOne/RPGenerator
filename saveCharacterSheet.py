import json

CHARACTER_DATA_FILE = 'characters.json'

def load_characters():
    try:
        with open(CHARACTER_DATA_FILE, 'r') as f:
            data = json.load(f)
            characters = {name: Character(**char_data) for name, char_data in data.items()}
            return characters
    except FileNotFoundError:
        return {}

def save_characters(characters):
    data = {name: vars(char) for name, char in characters.items()}
    with open(CHARACTER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)