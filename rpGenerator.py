import discord
from discord.ext import commands
from discord.ui import View, Button, Select
import requests
import random
import json
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio
import re
import logging

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WORLD_ANVIL_API_KEY = os.getenv('WORLD_ANVIL_API_KEY')
WORLD_ANVIL_BASE_URL = 'https://www.worldanvil.com/api/aragorn'
CHARACTER_DATA_FILE = 'characters.json'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.dm_messages = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='/', intents=intents)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

tree = bot.tree  # Shortcut for command tree

# Initialize global variables
character_creation_sessions = {}
error_cooldowns = {}
last_error_time = None  # For global cooldown

# Create a dictionary of actions
def load_actions():
    try:
        with open('actions.json', 'r') as f:
            actions = json.load(f)
            logging.info("actions.json loaded successfully.")
            return actions
    except FileNotFoundError:
        logging.error("actions.json file not found.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding actions.json: {e}")
        return {}

actions = load_actions()

# Character class definition
class Character:
    def __init__(self, name, race=None, char_class=None, gender=None, pronouns=None, description=None, stats=None, skills=None, inventory=None, equipment=None, currency=None, spells=None, abilities=None):
        self.name = name
        self.race = race
        self.char_class = char_class
        self.gender = gender  # New Attribute
        self.pronouns = pronouns  # New Attribute
        self.description = description  # New Attribute
        self.stats = stats if stats else {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }
        self.skills = skills if skills else {}
        self.inventory = inventory if inventory else {}
        self.equipment = equipment if equipment else {}
        self.currency = currency if currency else {}
        self.spells = spells if spells else {}
        self.abilities = abilities if abilities else {}

    def get_stat_modifier(self, stat):
        return (self.stats.get(stat, 10) - 10) // 2

# Load character data
def load_characters():
    try:
        with open(CHARACTER_DATA_FILE, 'r') as f:
            data = json.load(f)
            characters = {user_id: Character(**char_data) for user_id, char_data in data.items()}
            logging.info("Characters loaded successfully.")
            return characters
    except FileNotFoundError:
        logging.warning("characters.json not found. Starting with an empty character list.")
        return {}
    except TypeError as e:
        logging.error(f"Error loading characters: {e}")
        return {}

def save_characters(characters):
    data = {
        user_id: {
            'name': char.name,
            'race': char.race,
            'char_class': char.char_class,
            'gender': char.gender,  # New Attribute
            'pronouns': char.pronouns,  # New Attribute
            'description': char.description,  # New Attribute
            'stats': char.stats,
            'skills': char.skills,
            'inventory': char.inventory,
            'equipment': char.equipment,
            'currency': char.currency,
            'spells': char.spells,
            'abilities': char.abilities
        } for user_id, char in characters.items() if char is not None  # Exclude None characters
    }
    with open(CHARACTER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    logging.info("Characters saved successfully.")

characters = load_characters()

# Create point-buy system for ability scores
POINT_BUY_TOTAL = 27
ABILITY_SCORE_COSTS = {
    8: -2,  # Lowering to 8 gains 2 points
    9: -1,  # Lowering to 9 gains 1 point
    10: 0,  # Base score, no cost
    11: 1,
    12: 2,
    13: 3,
    14: 5,
    15: 7
}

def calculate_score_cost(score):
    """
    Returns the point cost for a given ability score based on the point-buy system.
    Negative values indicate points gained by lowering the score.
    """
    return ABILITY_SCORE_COSTS.get(score, None)

def is_valid_point_allocation(allocation):
    """
    Validates if the total points spent/gained in the allocation meet the point-buy criteria.
    """
    total_cost = sum(calculate_score_cost(score) for score in allocation.values())
    if total_cost > POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) exceed the allowed pool of {POINT_BUY_TOTAL}."
    if total_cost < POINT_BUY_TOTAL - (2 * list(allocation.values()).count(8) + 1 * list(allocation.values()).count(9)):
        return False, f"Total points spent ({total_cost}) are too low. Ensure you spend exactly {POINT_BUY_TOTAL} points."
    for score in allocation.values():
        if score < 8 or score > 15:
            return False, f"Ability scores must be between 8 and 15. Found {score}."
    return True, "Valid allocation."

# Start Character Creation View
class CharacterCreationView(View):
    def __init__(self):
        super().__init__()
        self.add_item(StartCharacterButton())

class StartCharacterButton(Button):
    def __init__(self):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            # Initialize session
            user_id = str(interaction.user.id)
            character_creation_sessions[user_id] = {'stats': {}, 'points_spent': 0}

            # Send instructions
            await interaction.user.send(
                "Let's begin your character creation!\n\n"
                f"You have **{POINT_BUY_TOTAL} points** to distribute among your abilities using the point-buy system.\n\n"
                "Here's how the costs work:\n"
                "- **8:** Gain 2 points\n"
                "- **9:** Gain 1 point\n"
                "- **10:** 0 points\n"
                "- **11:** Spend 1 point\n"
                "- **12:** Spend 2 points\n"
                "- **13:** Spend 3 points\n"
                "- **14:** Spend 5 points\n"
                "- **15:** Spend 7 points\n\n"
                "No ability score can be raised above **15**, and none can be lowered below **8**.\n\n"
                "Please enter your character's name:"
            )

            # Wait for the user's response for the character name
            def check_name(m):
                return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)

            try:
                name_message = await bot.wait_for('message', check=check_name, timeout=60)
                character_creation_sessions[user_id]['name'] = name_message.content
                await interaction.user.send("Character name set! Please select your gender:", view=GenderSelectionView())
            except asyncio.TimeoutError:
                await interaction.user.send("Character creation timed out. Please try again.")
                del character_creation_sessions[user_id]
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in StartCharacterButton callback: {e}")

# Gender Selection View
class GenderSelectionView(View):
    def __init__(self):
        super().__init__()
        self.add_item(GenderDropdown())

class GenderDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Male", description="Male gender"),
            discord.SelectOption(label="Female", description="Female gender"),
            discord.SelectOption(label="Non-binary", description="Non-binary gender"),
            discord.SelectOption(label="Other", description="Other or unspecified gender"),
        ]
        super().__init__(placeholder="Choose your character's gender...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)
            selected_gender = self.values[0]
            character_creation_sessions[user_id]['gender'] = selected_gender

            # Proceed to pronouns selection
            await interaction.user.send(f"Gender set to **{selected_gender}**! Please select your pronouns:", view=PronounsSelectionView())
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in GenderDropdown callback: {e}")

# Pronouns Selection View
class PronounsSelectionView(View):
    def __init__(self):
        super().__init__()
        self.add_item(PronounsDropdown())

class PronounsDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="He/Him", description="He/Him pronouns"),
            discord.SelectOption(label="She/Her", description="She/Her pronouns"),
            discord.SelectOption(label="They/Them", description="They/Them pronouns"),
            discord.SelectOption(label="Other", description="Other pronouns"),
        ]
        super().__init__(placeholder="Choose your character's pronouns...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)
            selected_pronouns = self.values[0]
            character_creation_sessions[user_id]['pronouns'] = selected_pronouns

            # Proceed to description input
            await interaction.user.send("Please enter a brief description of your character (max 200 words):")
            await interaction.user.send("You have 200 words to describe your character's appearance, personality, background, etc.")
            # Wait for description input
            def check_description(m):
                return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)

            try:
                description_message = await bot.wait_for('message', check=check_description, timeout=120)
                description = description_message.content
                if len(description.split()) > 200:
                    await interaction.user.send("Description is too long. Please limit it to 200 words.")
                    return
                character_creation_sessions[user_id]['description'] = description
                await interaction.user.send("Description set! Please select a race:", view=RaceSelectionView())
            except asyncio.TimeoutError:
                await interaction.user.send("Character creation timed out during description input. Please try again.")
                del character_creation_sessions[user_id]
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in PronounsDropdown callback: {e}")

# Race Selection View
class RaceSelectionView(View):
    def __init__(self):
        super().__init__()
        self.add_item(RaceDropdown())

class RaceDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Human", description="A versatile and adaptable race."),
            discord.SelectOption(label="Elf", description="Graceful and attuned to magic."),
            discord.SelectOption(label="Dwarf", description="Sturdy and resilient."),
            discord.SelectOption(label="Orc", description="Strong and fierce."),
            # Add more races as needed
        ]
        super().__init__(placeholder="Choose your race...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)
            selected_race = self.values[0]
            character_creation_sessions[user_id]['race'] = selected_race

            # Proceed to class selection
            await interaction.user.send(f"Race set to **{selected_race}**! Please select a class:", view=ClassSelectionView())
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in RaceDropdown callback: {e}")

# Class Selection View
class ClassSelectionView(View):
    def __init__(self):
        super().__init__()
        self.add_item(ClassDropdown())

class ClassDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Warrior", description="A strong fighter."),
            discord.SelectOption(label="Mage", description="A wielder of magic."),
            discord.SelectOption(label="Rogue", description="A stealthy character."),
            discord.SelectOption(label="Cleric", description="A healer and protector."),
            # Add more classes as needed
        ]
        super().__init__(placeholder="Choose your class...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)
            selected_class = self.values[0]
            character_creation_sessions[user_id]['char_class'] = selected_class

            # Proceed to ability score assignment
            await interaction.user.send(
                f"Class set to **{selected_class}**! Now, assign your ability scores using the point-buy system.",
                view=AbilityScoreView(user_id)
            )
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in ClassDropdown callback: {e}")

# Ability Score Assignment View
class AbilityScoreView(View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.allocated_stats = character_creation_sessions[user_id].get('stats', {}).copy()
        self.remaining_points = POINT_BUY_TOTAL - sum(calculate_score_cost(score) for score in self.allocated_stats.values())
        self.add_item(AbilityScoreDropdown(user_id, self.remaining_points))

class AbilityScoreDropdown(Select):
    def __init__(self, user_id, remaining_points):
        self.user_id = user_id
        self.remaining_points = remaining_points

        # Define which abilities are already assigned
        assigned_stats = character_creation_sessions[user_id].get('stats', {})
        all_stats = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
        unassigned_stats = [stat for stat in all_stats if stat not in assigned_stats]

        # Define dropdown options for unassigned abilities
        options = [
            discord.SelectOption(label=stat, description=f"Assign score to {stat}") for stat in unassigned_stats
        ]

        super().__init__(placeholder="Choose an ability to assign...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = self.user_id
            chosen_stat = self.values[0]

            # Prompt user to enter a score for the chosen ability
            await interaction.user.send(f"Please enter a score for **{chosen_stat}** (8-15):")

            # Wait for the user's score input
            def check_score(m):
                return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)

            try:
                score_message = await bot.wait_for('message', check=check_score, timeout=60)
                score = int(score_message.content)

                if score < 8 or score > 15:
                    await interaction.user.send("Invalid score. Please enter a number between 8 and 15.")
                    return

                # Calculate point cost
                cost = calculate_score_cost(score)
                new_total_spent = character_creation_sessions[user_id]['points_spent'] + cost

                # Check if the point allocation is within limits
                if new_total_spent > POINT_BUY_TOTAL:
                    await interaction.user.send(
                        f"Insufficient points. You have **{POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']} points** remaining."
                    )
                    return

                # Update session data
                character_creation_sessions[user_id]['stats'][chosen_stat] = score
                character_creation_sessions[user_id]['points_spent'] += cost
                remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']

                await interaction.user.send(
                    f"**{chosen_stat}** set to **{score}**. Remaining points: **{remaining_points}**."
                )

                # Remove the assigned stat dropdown
                self.view.remove_item(self)
                self.view.remaining_points = remaining_points

                # Check if there are abilities left to assign
                all_stats = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
                assigned_stats = character_creation_sessions[user_id].get('stats', {})
                remaining_stats = [stat for stat in all_stats if stat not in assigned_stats]

                if remaining_stats and remaining_points >= -2:  # Minimum score is 8, which gains 2 points
                    # Continue assigning
                    await interaction.user.send(
                        "Please assign the next ability score.",
                        view=AbilityScoreView(user_id)
                    )
                else:
                    # All stats assigned or no points left
                    # Validate total points spent
                    allocation = character_creation_sessions[user_id]['stats']
                    is_valid, message = is_valid_point_allocation(allocation)
                    if is_valid:
                        await interaction.user.send(
                            "All ability scores have been assigned correctly. Click the button below to finish.",
                            view=FinishCharacterView()
                        )
                    else:
                        await interaction.user.send(f"Point allocation error: {message}. Please adjust your scores.")
            except asyncio.TimeoutError:
                await interaction.user.send("Ability score assignment timed out. Please try again.")
            except ValueError:
                await interaction.user.send("Invalid input. Please enter a numeric value between 8 and 15.")
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in AbilityScoreDropdown callback: {e}")

# Finish Character Creation View
class FinishCharacterView(View):
    def __init__(self):
        super().__init__()
        self.add_item(FinishCharacterButton())

class FinishCharacterButton(Button):
    def __init__(self):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        try:
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)
            session = character_creation_sessions.get(user_id, {})

            if not session:
                await interaction.user.send("No character data found. Please start over.")
                return

            allocation = session.get('stats', {})
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.user.send(f"Character creation failed: {message}")
                return

            character = await finalize_character(interaction, user_id)
            if character:
                # Save the character data
                characters[user_id] = character
                save_characters(characters)
                del character_creation_sessions[user_id]

                # Confirm creation
                await interaction.user.send(
                    f"Character '{character.name}' (Race: {character.race}, Class: {character.char_class}, Gender: {character.gender}, Pronouns: {character.pronouns}) has been created successfully!\n"
                    f"Ability Scores: {character.stats}\n"
                    f"Description: {character.description}"
                )
            else:
                await interaction.user.send("Character creation failed. Please start over.")
        except Exception as e:
            await interaction.user.send(f"An error occurred: {e}")
            logging.error(f"Error in FinishCharacterButton callback: {e}")

# Finalize Character Function
async def finalize_character(interaction: discord.Interaction, user_id):
    session = character_creation_sessions.get(user_id, {})
    if not session:
        await interaction.user.send("No character data found.")
        return None

    allocation = session.get('stats', {})
    is_valid, message = is_valid_point_allocation(allocation)
    if not is_valid:
        await interaction.user.send(f"Character creation failed: {message}")
        return None

    # Create the Character instance
    character = Character(
        name=session.get('name', "Unnamed Character"),
        race=session.get('race', "Unknown Race"),
        char_class=session.get('char_class', "Unknown Class"),
        gender=session.get('gender', "Unspecified"),
        pronouns=session.get('pronouns', "They/Them"),
        description=session.get('description', "No description provided."),
        stats=session.get('stats', {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }),
        skills=session.get('skills', {}),
        inventory=session.get('inventory', {}),
        equipment=session.get('equipment', {}),
        currency=session.get('currency', {}),
        spells=session.get('spells', {}),
        abilities=session.get('abilities', {})
    )

    return character

# Command to start character creation
@bot.tree.command(name="create_character", description="Create a new character")
async def create_character(interaction: discord.Interaction):
    try:
        await interaction.user.send("Let's create your character!", view=CharacterCreationView())
        await interaction.response.send_message("Check your DMs to start character creation!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            "Unable to send you a DM. Please check your privacy settings.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.",
            ephemeral=True
        )
        logging.error(f"Error in create_character command: {e}")

@bot.event
async def on_ready():
    try:
        print(f'Logged in as {bot.user.name}')
        guild = discord.utils.get(bot.guilds, name='Just For Me')
        if guild:
            permissions = guild.me.guild_permissions
            if permissions.send_messages and permissions.read_message_history:
                print("Bot has the necessary permissions.")
            else:
                print("Bot does not have the necessary permissions.")
        await bot.tree.sync()
        print("Command tree synchronized.")
    except Exception as e:
        print(f"An error occurred in on_ready: {e}")
        logging.error(f"Error in on_ready event: {e}")

def perform_ability_check(character, stat):
    try:
        modifier = character.get_stat_modifier(stat)
        roll = random.randint(1, 20)
        total = roll + modifier
        logging.info(f'You rolled a {roll} plus {modifier} for a total of {total}')
        return roll, total
    except Exception as e:
        logging.error(f"Error in perform_ability_check: {e}")
        return None, None

async def parse_action(message):
    message_content = message.content
    # Define the actions and their associated stats
    global actions
    action_list = ', '.join(actions.keys())

    # Use regex to find words starting with '?' followed by letters
    matches = re.findall(r'\?[A-Za-z]+', message_content.lower())
    logging.info(f"Parsing message: '{message_content}'")
    logging.info(f"Matches found: {matches}")
    for match in matches:
        match = match.lstrip('?')
        logging.info(f"Parsing word: {match}")
        if match in actions:
            logging.info(f"Action recognized: {match}")
            return match, actions[match]
        await show_actions(message)
    logging.info("No action recognized.")
    return None, None 

async def show_actions(message):
    global actions
    action_list = ', '.join(actions.keys())
    await message.channel.send(f"Sorry, I don't recognize that action. Recognized actions: {action_list}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check for '?listactions' command
    if message.content.strip() == '?listactions':
        action_list = ', '.join(actions.keys())
        await message.channel.send(f"Recognized actions: {action_list}")
        return

    user_id = str(message.author.id)

    if user_id not in characters:
        characters[user_id] = Character(name=message.author.name)
        save_characters(characters)
        await message.channel.send(f'Character created for {message.author.name}.')

    character = characters[user_id]
    action, stat = await parse_action(message)
    if action and stat:
        roll, total = perform_ability_check(character, stat)
        if roll is None or total is None:
            return  # Ability check failed due to an error

        # Fetch the last 10 messages from the channel
        channel_history = [msg async for msg in message.channel.history(limit=10)]

        # Get the content of the last 5 messages
        last_messages_content = [msg.content for msg in channel_history[:5]]

        # Construct the prompt
        difficulty_prompt = (
            f"Player {character.name} attempts to {action}. "
            f"Keeping in mind that player characters are meant to be a cut above the average person, \n"
            f"based on the context of the action and the surrounding \n"
            f"circumstances contained in previous messages, talk yourself through the nuances of the \n"
            f"scene, the action, and what else is happening around them, and determine the difficulty (DC) of the task. "
            f"This should be represented with a number between 5 and 30, \n"
            f"with 5 being trivial (something like climbing a tree to escape a pursuing creature), 10 being very easy (something like recalling what you know about defeating an enemy), 12 being easy (something like tossing a rock at a close target), "
            f"15 being challenging (actions like identifying rare mushrooms and their unique properties), 17 being difficult (actions like breaking down a heavy wooden door), 20 being extremely \n"
            f"difficult (something like using rope to grapple onto an object while falling). \n"
            f"Above 20 should be reserved for actions that are increasingly \n"
            f"impossible. For example, 25 might be something like interpreting words in a language you don't understand \n"
            f"No difficulty should ever go above 30, which should be reserved \n"
            f"for actions that are almost certainly impossible, but a freak \n"
            f"chance of luck exists, something like convincing the main villain to abandon their plan and be their friend.\n"
            f"Just provide the number."
        )

        difficulty_response = await get_chatgpt_response(
            difficulty_prompt, last_messages_content, stat, total, roll, character, include_roll_info=False
        )
        try:
            difficulty = int(re.search(r'\d+', difficulty_response).group())
            logging.info(f"Difficulty determined: {difficulty}")
        except (AttributeError, ValueError):
            COOLDOWN_PERIOD = 5  # Cooldown period in seconds
            current_time = asyncio.get_event_loop().time()
            global last_error_time
            if last_error_time is None or current_time - last_error_time > COOLDOWN_PERIOD:
                await message.channel.send("Sorry, I couldn't determine the difficulty of the task.")
                last_error_time = current_time
            return

        # Determine the result based on the difficulty
        if roll == 20:
            result = "succeed with a critical success"
        elif total > difficulty:
            result = "succeed"
        elif total == difficulty:
            result = "succeed, but with a complication that heightens the tension"
        else:
            result = "fail"

        logging.info(f"Player {character.name} attempted to {action}. The DC was {difficulty}. It was a {result}.")

        # Construct the final prompt
        prompt = (
            f"{character.name} attempted to {action} and they {result}.\n"
            f"As the game master, describe their action and how the narrative and scene and NPCs react to this action. \n"
            f"Always end with 'What do you do? The DC was: {difficulty}.' \n" 
            f"And a brief explanation on the reasoning behind that number as DC. \n"
            f"Limit responses to 100 words.\n"
        )

        response = await get_chatgpt_response(
           prompt, last_messages_content, stat, total, roll, character, include_roll_info=True
        )
        await message.channel.send(response)
        # update_world_anvil(character, action, response)
    else:
        # Optionally, do not send any message if no action is recognized
        pass

    await bot.process_commands(message)

async def get_chatgpt_response(prompt, channel_messages, stat, total, roll, character, include_roll_info=True):
    try:
        messages = [
            {"role": "system", "content": "You are a game master for a fantasy role-playing game. Your job is to narrate the settings the players journey through, the results of their actions, and provide a sense of atmosphere through vivid and engaging descriptions."}
        ]

        # Add the last channel messages in chronological order
        for msg_content in reversed(channel_messages):
            messages.append({"role": "user", "content": msg_content})

        messages.append({"role": "user", "content": prompt})

        # Ensure the model name is correct
        completion = await client.chat.completions.create(
            model='gpt-4',
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        if include_roll_info:
            message_content = f"*{character.name}, your {stat} check result is {total} (rolled {roll} + modifier {character.get_stat_modifier(stat)}).* \n\n{completion.choices[0].message.content.strip()}"
        else:
            message_content = completion.choices[0].message.content.strip()
        return message_content
    except Exception as e:
        logging.error(f"Error in get_chatgpt_response: {e}")
        return "Sorry, I couldn't process that request."

# Running the bot
bot.run(DISCORD_BOT_TOKEN)