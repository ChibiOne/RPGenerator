# rpGenerator.py

import discord
from discord.ext import commands
import requests
import random
import json
import os
from dotenv import load_dotenv
from openai import OpenAI  # Use AsyncOpenAI if using asynchronous calls
import asyncio
import re  # Import the 're' module for regex

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WORLD_ANVIL_API_KEY = os.getenv('WORLD_ANVIL_API_KEY')
WORLD_ANVIL_BASE_URL = 'https://www.worldanvil.com/api/aragorn'
CHARACTER_DATA_FILE = 'characters.json'

intents = discord.Intents.default()
intents.message_content = True  # Enable if you want to read message content
# Remove or comment out the following line if you don't need member intents
intents.members = True  # Needed if you are accessing guild members

bot = commands.Bot(command_prefix='!', intents=intents)

# Instantiate OpenAI client
# client = OpenAI(api_key=OPENAI_API_KEY)
# For asynchronous calls, use AsyncOpenAI
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

def load_actions():
    try:
        with open('actions.json', 'r') as f:
            actions = json.load(f)
            return actions
    except FileNotFoundError:
        print("actions.json file not found.")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding actions.json: {e}")
        return {}
    
actions = load_actions()

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
            'Athletics': 5,
            'Acrobatics': 5,
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

def perform_ability_check(character, stat):
    modifier = character.get_stat_modifier(stat)
    roll = random.randint(1, 20)
    total = roll + modifier
    print(f'You rolled a {roll} plus {modifier} for a total of :{total}')
    return roll, total

@bot.event
async def show_actions(message):
    global actions
    action_list = ', '.join(actions.keys())
    await message.channel.send(f"Sorry, I don't recognize that action. Recognized actions: {action_list}")

async def parse_action(message):
    message_content = message.content
    # Define the actions and their associated stats
    global actions
    action_list = ', '.join(actions.keys())

    # Use regex to find words starting with '?' not followed by a space
    matches = re.findall(r'\?[A-Za-z]+', message_content.lower())
    print(f"Parsing message: '{message_content}'")
    print(f"Matches found: {matches}")
    for match in matches:
        match = match.lstrip('?')
        print(f"Parsing word: {match}")
        if match in actions:
            print(f"Action recognized: {match}")
            return match, actions[match]
    await show_actions(message)
    print("No action recognized.")
    return None, None 

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check for '?listactions' command
    if message.content.strip() == '?listactions':
        global actions
        action_list = ', '.join(actions.keys())
        await message.channel.send(f"Recognized actions: {action_list}")
        return

    player_name = str(message.author)

    if player_name not in characters:
        characters[player_name] = Character(name=player_name)
        save_characters(characters)
        await message.channel.send(f'Character created for {player_name}.')

    character = characters[player_name]
    action, stat = await parse_action(message)
    if action and stat:
        roll, total = perform_ability_check(character, stat)
        world_data = {}  # Replace with actual world data fetching if needed

        # Fetch the last 10 messages from the channel
        channel_history = [msg async for msg in message.channel.history(limit=10)]

        # Filter out the current message
        last_messages = [
            msg for msg in channel_history
        ]

        # Get the content of the last 5 messages
        last_messages_content = [msg.content for msg in last_messages[:5]]

        # Construct the prompt
        prompt = (
            f"Player {character.name} attempts to {action}. "
            f"Their {stat} check result is {total} (rolled {roll} + modifier {character.get_stat_modifier(stat)}).\n"
            f"Based on the context of the action and the surrounding circumstances, determine \n"
            f"how difficult the task is, (Its DC). \n"
            f"This should be represented with a number between 10 and 30, with 10 being very easy, \n"
            f"12 being easy, 15 being challenging, 17 being difficult, \n"
            f"20 being extremely difficult. Above 20 should be reserved for actions that are \n"
            f"increasingly impossible. No difficulty should ever go above 30, which should be reserved \n"
            f"for actions that are almost certainly impossible, but a freak chance of luck exists.\n"
            f"If the player's total is higher than the DC, they succeed. If the player's total is lower than the DC, \n"
            f"they fail. If the player's total is equal to the DC, they succeed with a complication. They achieve what they were \n" 
            f"attempting, but are in a new predicament. The complication should make the situation \n" 
            f"more intense. For example, if trying to leap across a crevasse, a success with a \n"
            f"complication might mean that they make it across barely, grabbing the ledge on the \n"
            f"other side. Now they are dangling precariously and someone must help them up. \n"
            f"If the player's roll was a 20 (not the total, the roll), they succeed with a critical success. In this case, they \n"
            f"should achieve more than they hoped and find themselves in a significantly better \n"
            f"situation. \n"
            f"World data: {world_data}\n"
            f"As the game master, describe what happens next in vivid detail. \n"
            f"Always end with 'What do you do? The DC was: <assigned difficutly number> \n" 
            f"And a brief explanation on the reasoning behind why you assigned that number as DC. \n"
            f"Limit responses to 100 words.\n"
        )

        response = await get_chatgpt_response(prompt, last_messages_content, stat, total, roll, character)
        await message.channel.send(response)
        # update_world_anvil(character, action, response)
    else:
        # Optionally, do not send any message if no action is recognized
        pass

    await bot.process_commands(message)

async def get_chatgpt_response(prompt, channel_messages, stat, total, roll, character):
    try:
        messages = [
            {"role": "system", "content": "You are a game master for a fantasy role-playing game. Your job is to narrate the settings the players journey through, the results of their actions, and provide a sense of atmosphere through vivid and engaging descriptins."}
        ]

        # Add the last channel messages in chronological order
        for msg_content in reversed(channel_messages):
            messages.append({"role": "user", "content": msg_content})

        messages.append({"role": "user", "content": prompt})

        # If using AsyncOpenAI client, use await
        completion = await client.chat.completions.create(
        # If using OpenAI client synchronously
        # completion = client.chat.completions.create(
            model='gpt-4',
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        message = f"*{character.name}, your {stat} check result is {total} (rolled {roll} + modifier {character.get_stat_modifier(stat)}).* \n\n{completion.choices[0].message.content.strip()}"
        return message
    except Exception as e:
        print(f"An error occurred: {e}")
        return "Sorry, I couldn't process that request."

# If you have any commands, you can add them here
# Example: Command to reset conversation history (if implemented)
# @bot.command()
# async def reset_history(ctx):
#     # Your code here
#     pass

bot.run(DISCORD_BOT_TOKEN)