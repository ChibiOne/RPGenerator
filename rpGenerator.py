# rpGenerator.py

import discord
from discord.ext import commands
import requests
import random
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WORLD_ANVIL_API_KEY = os.getenv('WORLD_ANVIL_API_KEY')
WORLD_ANVIL_BASE_URL = 'https://www.worldanvil.com/api/boromir'
CHARACTER_DATA_FILE = 'characters.json'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Instantiate OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

class Character:
    def __init__(self, name, stats=None, skills=None):
        self.name = name
        self.stats = stats if stats else {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }
        self.skills = skills if skills else {
            'Athletics': 0,
            'Acrobatics': 0,
            # Add other skills as needed
        }

    def get_stat_modifier(self, stat):
        return (self.stats[stat] - 10) // 2

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

characters = load_characters()

def get_world_info(endpoint):
    headers = {
        'Authorization': f'Bearer {WORLD_ANVIL_API_KEY}'
    }
    response = requests.get(f'{WORLD_ANVIL_BASE_URL}/{endpoint}', headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error fetching world data: {response.status_code}')
        return None

def update_world_anvil(character, action, result):
    headers = {
        'Authorization': f'Bearer {WORLD_ANVIL_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'title': f'Event by {character.name}',
        'content': f'{character.name} attempted to {action}. Result: {result}'
    }
    response = requests.post(f'{WORLD_ANVIL_BASE_URL}/article', headers=headers, json=data)
    if response.status_code == 201:
        print('World Anvil updated successfully.')
    else:
        print(f'Error updating World Anvil: {response.status_code}')

def get_chatgpt_response(prompt):
    try:
        completion = client.chat.completions.create(
            model='gpt-4',
            messages=[
                {"role": "system", "content": "You are a game master for a fantasy role-playing game."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        message = completion.choices[0].message.content.strip()
        return message
    except Exception as e:
        print(f"An error occurred: {e}")
        return "Sorry, I couldn't process that request."

def perform_ability_check(character, stat):
    modifier = character.get_stat_modifier(stat)
    roll = random.randint(1, 20)
    total = roll + modifier
    return roll, total

def parse_action(message_content):
    actions = {
        'climb': 'Strength',
        'sneak': 'Dexterity',
        'perceive': 'Wisdom',
        # Add other actions and associated stats
    }
    for action, stat in actions.items():
        if action in message_content.lower():
            return action, stat
    return None, None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    player_name = str(message.author)
    if player_name not in characters:
        characters[player_name] = Character(name=player_name)
        save_characters(characters)
        await message.channel.send(f'Character created for {player_name}.')

    character = characters[player_name]
    action, stat = parse_action(message.content)
    if stat:
        roll, total = perform_ability_check(character, stat)
        world_data = {}  # Replace with actual world data fetching if needed
        prompt = (
            f"Player {character.name} attempts to {action}. "
            f"Their {stat} check result is {total} (rolled {roll} + modifier {character.get_stat_modifier(stat)}).\n"
            f"World data: {world_data}\n"
            f"As the game master, describe what happens next in vivid detail. Always end by asking the players what they wish to do next."
        )
        response = get_chatgpt_response(prompt)
        await message.channel.send(response)
        update_world_anvil(character, action, response)
    else:
        await message.channel.send("Action not recognized. Please try again.")

    await bot.process_commands(message)

bot.run(DISCORD_BOT_TOKEN)