import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from discord import SelectOption, Embed
import json
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio
import re
import logging
import random

# ---------------------------- #
#        Configuration         #
# ---------------------------- #

# Load environment variables from .env file
load_dotenv()

# Discord and OpenAI API keys
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# File paths
CHARACTER_DATA_FILE = 'characters.json'
ACTIONS_FILE = 'actions.json'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Initialize OpenAI Async Client
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,  # Optional if set via environment variable
)

# Define Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.dm_messages = True

# Initialize the bot
bot = commands.Bot(command_prefix='/', intents=intents)
tree = bot.tree  # Shortcut for command tree

# Initialize global variables
character_creation_sessions = {}
last_error_time = {}  # For global cooldowns per user

# ---------------------------- #
#          Utilities            #
# ---------------------------- #

def load_actions():
    """
    Loads actions from the actions.json file.
    Returns:
        dict: A dictionary mapping actions to their associated stats.
    """
    try:
        with open(ACTIONS_FILE, 'r') as f:
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

class Character:
    """
    Represents a player's character with various attributes.
    """
    def __init__(self, name, species=None, char_class=None, gender=None, pronouns=None, description=None, stats=None, skills=None, inventory=None, equipment=None, currency=None, spells=None, abilities=None):
        self.name = name
        self.species = species
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
        """
        Calculates the modifier for a given ability score.
        Args:
            stat (str): The name of the stat.
        Returns:
            int: The modifier.
        """
        return (self.stats.get(stat, 10) - 10) // 2

def load_characters():
    """
    Loads character data from the characters.json file.
    Returns:
        dict: A dictionary mapping user IDs to Character instances.
    """
    try:
        with open(CHARACTER_DATA_FILE, 'r') as f:
            data = json.load(f)
            characters = {}
            for user_id, char_data in data.items():
                try:
                    characters[user_id] = Character(**char_data)
                except TypeError as e:
                    logging.error(f"Error initializing character for user {user_id}: {e}")
            logging.info("Characters loaded successfully.")
            return characters
    except FileNotFoundError:
        logging.warning("characters.json not found. Starting with an empty character list.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding characters.json: {e}")
        return {}

def save_characters(characters):
    """
    Saves character data to the characters.json file.
    Args:
        characters (dict): A dictionary mapping user IDs to Character instances.
    """
    data = {
        user_id: {
            'name': char.name,
            'species': char.species,
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
    try:
        with open(CHARACTER_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        logging.info("Characters saved successfully.")
    except Exception as e:
        logging.error(f"Error saving characters: {e}")

characters = load_characters()

# Point-Buy System Configuration
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
    Args:
        score (int): The ability score.
    Returns:
        int: The point cost.
    Raises:
        ValueError: If the score is not between 8 and 15 inclusive.
    """
    if score not in ABILITY_SCORE_COSTS:
        raise ValueError(f"Invalid ability score: {score}. Must be between 8 and 15.")
    return ABILITY_SCORE_COSTS[score]

def is_valid_point_allocation(allocation):
    """
    Validates if the total points spent/gained in the allocation meet the point-buy criteria.
    Args:
        allocation (dict): A dictionary of ability scores.
    Returns:
        tuple: (bool, str) indicating validity and a message.
    """
    try:
        total_cost = sum(calculate_score_cost(score) for score in allocation.values())
    except ValueError as e:
        return False, str(e)
    
    # Calculate the minimum total cost based on possible point gains from lowering scores
    max_points_gained = 2 * list(allocation.values()).count(8) + 1 * list(allocation.values()).count(9)
    min_total_cost = POINT_BUY_TOTAL - max_points_gained
    
    if total_cost > POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) exceed the allowed pool of {POINT_BUY_TOTAL}."
    elif total_cost < POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) are less than the allowed pool of {POINT_BUY_TOTAL}."

    if total_cost < min_total_cost:
        return False, f"Total points spent ({total_cost}) are too low. Ensure you spend exactly {POINT_BUY_TOTAL} points."
        for score in allocation.values():
            if score < 8 or score > 15:
                return False, f"Ability scores must be between 8 and 15. Found {score}."
    return True, "Valid allocation."

# ---------------------------- #
#      UI Component Classes    #
# ---------------------------- #

class GenericDropdown(discord.ui.Select):
    """
    A generic dropdown class that can be reused for various selections.
    """
    def __init__(self, placeholder, options, callback_func, user_id):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.callback_func = callback_func
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(self, interaction, self.user_id)

# Callback functions for dropdowns
async def gender_callback(dropdown, interaction, user_id):
    """
    Callback for gender selection.
    """
    try:
        selected_gender = dropdown.values[0]
        character_creation_sessions[user_id]['gender'] = selected_gender
        logging.info(f"User {user_id} selected gender: {selected_gender}")

        # Proceed to pronouns selection
        await interaction.response.edit_message(
            content=f"Gender set to **{selected_gender}**! Please select your pronouns:",
            view=PronounsSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in gender_callback for user {user_id}: {e}")

async def pronouns_callback(dropdown, interaction, user_id):
    """
    Callback for pronouns selection.
    """
    try:
        selected_pronouns = dropdown.values[0]
        character_creation_sessions[user_id]['pronouns'] = selected_pronouns
        logging.info(f"User {user_id} selected pronouns: {selected_pronouns}")

        # Proceed to description input using a modal
        await interaction.response.send_modal(DescriptionModal(user_id))
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in pronouns_callback for user {user_id}: {e}")

async def species_callback(dropdown, interaction, user_id):
    """
    Callback for species selection.
    """
    try:
        selected_species = dropdown.values[0]
        character_creation_sessions[user_id]['species'] = selected_species
        logging.info(f"User {user_id} selected species: {selected_species}")

        # Proceed to class selection
        await interaction.response.edit_message(
            content=f"Species set to **{selected_species}**! Please select a class:",
            view=ClassSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in species_callback for user {user_id}: {e}")

async def class_callback(dropdown, interaction, user_id):
    """
    Callback for class selection.
    """
    try:
        selected_class = dropdown.values[0]
        character_creation_sessions[user_id]['char_class'] = selected_class
        logging.info(f"User {user_id} selected class: {selected_class}")

        # Proceed to ability score assignment

        # Send the embed with the PhysicalAbilitiesView
        await interaction.response.edit_message(
            content="Let's begin your character creation!\n\n"
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
            "Please assign your **Physical Attributes**:",
            view=PhysicalAbilitiesView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in class_callback for user {user_id}: {e}")

def generate_ability_embed(user_id):
    """
    Generates an embed reflecting the current ability scores and remaining points.
    """
    try:
        remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']
        assignments = character_creation_sessions[user_id]['stats']

        embed = discord.Embed(title="Character Creation - Ability Scores", color=discord.Color.blue())
        embed.add_field(name="Remaining Points", value=f"{remaining_points}/{POINT_BUY_TOTAL}", inline=False)

        # Add assigned scores
        for ability in ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']:
            score = assignments.get(ability, 10)
            embed.add_field(name=ability, value=str(score), inline=True)

        embed.set_footer(text="Assign your ability scores using the dropdowns below.")

        return embed
    except Exception as e:
        logging.error(f"Error generating embed for user {user_id}: {e}")
        return None
    
# Character Creation Views
class CharacterCreationView(discord.ui.View):
    """
    Initial view for character creation with a start button.
    """
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(StartCharacterButton(bot))

class StartCharacterButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)

            # Initialize session
            if not hasattr(self.bot, 'character_creation_sessions'):
                self.bot.character_creation_sessions = {}
            character_creation_sessions[user_id] = {'stats': {}, 'points_spent': 0}

            # Create initial embed
            embed = Embed(title="Character Creation - Ability Scores", color=discord.Color.blue())
            embed.add_field(name="Remaining Points", value=f"{POINT_BUY_TOTAL}/{POINT_BUY_TOTAL}", inline=False)
            embed.set_footer(text="Assign your ability scores using the dropdowns below.")

            # Present the modal to get the character's name
            await interaction.response.send_modal(CharacterNameModal(user_id))
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)
            logging.error(f"Error in StartCharacterButton callback for user {user_id}: {e}")


class CharacterNameModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Name")
        self.user_id = user_id
        self.character_name = discord.ui.TextInput(label="Character Name")
        self.add_item(self.character_name)


    async def on_submit(self, interaction: discord.Interaction):
        character_name = self.children[0].value
        character_creation_sessions[self.user_id]['name'] = character_name
        logging.info(f"User {self.user_id} entered name: {character_name}")

        # Send or edit the message to proceed to gender selection
        await interaction.response.send_message(
            content="Character name set! Please select your gender:",
            view=GenderSelectionView(self.user_id),
            ephemeral=True
        )
        # Store the message object in the session for later editing
        character_creation_sessions[self.user_id]['message'] = await interaction.original_response()

class DescriptionModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Description")
        self.user_id = user_id
        self.description = discord.ui.TextInput(
            label="Character Description",
            style=discord.TextStyle.long,
            max_length=1000  # Optional: Limit input length
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        description = self.children[0].value
        word_count = len(description.split())
        if word_count > 200:
            await interaction.response.send_message(
                f"Description is too long ({word_count} words). Please limit it to 200 words.",
                ephemeral=True
            )
            # Re-show the modal for input
            await interaction.response.send_modal(DescriptionModal(self.user_id))
        else:
            character_creation_sessions[self.user_id]['description'] = description
            logging.info(f"User {self.user_id} provided description with {word_count} words.")

            # Proceed to species selection
            await interaction.response.edit_message(
                content="Description set! Please select a species:",
                view=SpeciesSelectionView(self.user_id)
            )

class GenderSelectionView(discord.ui.View):
    """
    View for gender selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Male", description="Male gender"),
            discord.SelectOption(label="Female", description="Female gender"),
            discord.SelectOption(label="Non-binary", description="Non-binary gender"),
            discord.SelectOption(label="Other", description="Other or unspecified gender"),
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your character's gender...",
            options=options,
            callback_func=gender_callback,
            user_id=user_id
        ))

class PronounsSelectionView(discord.ui.View):
    """
    View for pronouns selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="He/Him", description="He/Him pronouns"),
            discord.SelectOption(label="She/Her", description="She/Her pronouns"),
            discord.SelectOption(label="They/Them", description="They/Them pronouns"),
            discord.SelectOption(label="Other", description="Other pronouns"),
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your character's pronouns...",
            options=options,
            callback_func=pronouns_callback,
            user_id=user_id
        ))

class SpeciesSelectionView(discord.ui.View):
    """
    View for species selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Human", description="A versatile and adaptable species."),
            discord.SelectOption(label="Elf", description="Graceful and attuned to magic."),
            discord.SelectOption(label="Dwarf", description="Sturdy and resilient."),
            discord.SelectOption(label="Orc", description="Strong and fierce."),
            # Add more species as needed
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your species...",
            options=options,
            callback_func=species_callback,
            user_id=user_id
        ))

class ClassSelectionView(discord.ui.View):
    """
    View for class selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Warrior", description="A strong fighter."),
            discord.SelectOption(label="Mage", description="A wielder of magic."),
            discord.SelectOption(label="Rogue", description="A stealthy character."),
            discord.SelectOption(label="Cleric", description="A healer and protector."),
            # Add more classes as needed
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your class...",
            options=options,
            callback_func=class_callback,
            user_id=user_id
        ))

async def update_embed(interaction, user_id):
    """
    Updates the embed in the original message to reflect the current state.
    """
    embed = generate_ability_embed(user_id)
    if embed:
        await interaction.message.edit(embed=embed)
        logging.info(f"Embed updated for user {user_id}.")
    else:
        logging.error(f"Failed to update embed for user {user_id}.")

class PhysicalAbilitiesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.physical_abilities = ['Strength', 'Dexterity', 'Constitution']
        
        for ability in self.physical_abilities:
            current_score = character_creation_sessions[user_id]['stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(NextMentalAbilitiesButton(user_id))
        logging.info(f"PhysicalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class MentalAbilitiesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.mental_abilities = ['Intelligence', 'Wisdom', 'Charisma']
        for ability in self.mental_abilities:
            current_score = character_creation_sessions[user_id]['stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(BackPhysicalAbilitiesButton(user_id))
        self.add_item(FinishAssignmentButton(user_id))
        logging.info(f"MentalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class AbilitySelect(discord.ui.Select):
    """
    Dropdown for selecting an ability score for a specific ability.
    """
    def __init__(self, user_id, ability_name, current_score=None):
        self.user_id = user_id
        self.ability_name = ability_name
        options = [
            discord.SelectOption(label="8", description="Gain 2 points", default=(current_score == 8)),
            discord.SelectOption(label="9", description="Gain 1 point", default=(current_score == 9)),
            discord.SelectOption(label="10", description="0 points", default=(current_score == 10)),
            discord.SelectOption(label="11", description="Spend 1 point", default=(current_score == 11)),
            discord.SelectOption(label="12", description="Spend 2 points", default=(current_score == 12)),
            discord.SelectOption(label="13", description="Spend 3 points", default=(current_score == 13)),
            discord.SelectOption(label="14", description="Spend 5 points", default=(current_score == 14)),
            discord.SelectOption(label="15", description="Spend 7 points", default=(current_score == 15)),
        ]
        # Set the placeholder to show the current score
        if current_score is not None:
            placeholder_text = f"{self.ability_name}: {current_score}"
        else:
            placeholder_text = f"Assign {ability_name} score..."
        super().__init__(
            placeholder=placeholder_text,
            min_values=1,
            max_values=1,
            options=options
        )
        logging.info(f"AbilitySelect initialized for {ability_name} with current_score={current_score}.")

    async def callback(self, interaction: discord.Interaction):
        """
        Callback for ability score selection.
        """
        try:
            selected_score = int(self.values[0])
            cost = calculate_score_cost(selected_score)
            user_id = self.user_id
            cur_view=self.view
            cur_message=interaction.message.content
            
            # Retrieve previous score and cost
            previous_score = character_creation_sessions[user_id]['stats'].get(self.ability_name, 10)
            previous_cost = calculate_score_cost(previous_score)

            # Update the session data
            character_creation_sessions[user_id]['stats'][self.ability_name] = selected_score
            character_creation_sessions[user_id]['points_spent'] += (cost - previous_cost)
            logging.info(f"User {user_id} set {self.ability_name} to {selected_score}. Cost: {cost}. Total points spent: {character_creation_sessions[user_id]['points_spent']}.")

            remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']

            if remaining_points < 0:
                # Revert the assignment
                character_creation_sessions[user_id]['stats'][self.ability_name] = previous_score
                character_creation_sessions[user_id]['points_spent'] -= (cost - previous_cost)
                await interaction.response.send_message(
                    f"Insufficient points to assign **{selected_score}** to **{self.ability_name}**. You have **{remaining_points + (cost - previous_cost)} points** remaining.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points while assigning {self.ability_name}.")
                return

            current_score=character_creation_sessions[user_id]['stats'].get(self.ability_name, 10),

            # Determine which view to recreate
            if isinstance(self.view, PhysicalAbilitiesView):
                new_view = PhysicalAbilitiesView(user_id)
            elif isinstance(self.view, MentalAbilitiesView):
                new_view = MentalAbilitiesView(user_id)
            else:
                # Fallback or error handling
                new_view = self.view
            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                view=new_view,
                embed=embed  
            )
        except ValueError:
            await interaction.followup.send_message(
                f"Invalid input for **{self.ability_name}**. Please select a valid score.",
                ephemeral=True
            )
            logging.error(f"User {self.user_id} selected an invalid score for {self.ability_name}: {self.values[0]}")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in AbilitySelect callback for {self.ability_name}, user {self.user_id}: {e}")


class NextMentalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Next", style=discord.ButtonStyle.blurple)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id

            # Check if points_spent exceeds POINT_BUY_TOTAL
            points_spent = character_creation_sessions[user_id]['points_spent']
            if points_spent > POINT_BUY_TOTAL:
                await interaction.response.send_message(
                    f"You have overspent your points by **{points_spent - POINT_BUY_TOTAL}** points. Please adjust your ability scores.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points before navigating to MentalAbilitiesView.")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                content="Now, please assign your mental abilities:",
                view=MentalAbilitiesView(user_id),
                embed=embed  
            )
            logging.info(f"User {user_id} navigated to MentalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in NextMentalAbilitiesButton callback for user {self.user_id}: {e}")


class BackPhysicalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Back", style=discord.ButtonStyle.gray)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Proceed back to PhysicalAbilitiesView
            await interaction.response.edit_message(
                content="Returning to Physical Abilities assignment:",
                view=PhysicalAbilitiesView(user_id),
                embed=embed 
            )
            logging.info(f"User {user_id} navigated back to PhysicalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in BackPhysicalAbilitiesButton callback for user {self.user_id}: {e}")


class FinishAssignmentButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Finish", style=discord.ButtonStyle.green)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            allocation = character_creation_sessions[user_id]['stats']
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(
                    f"Point allocation error: {message}. Please adjust your scores before finalizing.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} failed point allocation validation: {message}")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            await interaction.response.edit_message(
                content="All ability scores have been assigned correctly. Click the button below to finish.",
                view=FinalizeCharacterView(user_id),
                embed=embed 
            )
            logging.info(f"User {user_id} prepared to finalize character creation.")
        except KeyError:
            await interaction.response.send_message(
                "Character data not found. Please start the character creation process again.",
                ephemeral=True
            )
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinishAssignmentButton callback for user {self.user_id}: {e}")


class FinalizeCharacterView(discord.ui.View):
    """
    View to finalize character creation.
    """
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.add_item(FinalizeCharacterButton(user_id))
        logging.info(f"FinalizeCharacterView created for user {user_id} with {len(self.children)} components.")

class FinalizeCharacterButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            session = character_creation_sessions.get(user_id, {})

            if not session:
                await interaction.response.send_message("No character data found. Please start over.", ephemeral=True)
                logging.error(f"No character data found for user {user_id} during finalization.")
                return

            allocation = session.get('stats', {})
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
                logging.warning(f"User {user_id} failed point allocation validation during finalization: {message}")
                return

            character = await finalize_character(interaction, user_id)
            if character:
                # Save the character data
                characters[user_id] = character
                save_characters(characters)
                del character_creation_sessions[user_id]
                logging.info(f"Character '{character.name}' created successfully for user {user_id}.")

                # Create a final character summary embed
                embed = discord.Embed(title=f"Character '{character.name}' Created!", color=discord.Color.green())
                embed.add_field(name="Species", value=character.species, inline=True)
                embed.add_field(name="Class", value=character.char_class, inline=True)
                embed.add_field(name="Gender", value=character.gender, inline=True)
                embed.add_field(name="Pronouns", value=character.pronouns, inline=True)
                embed.add_field(name="Description", value=character.description, inline=False)
                for stat, value in character.stats.items():
                    embed.add_field(name=stat, value=str(value), inline=True)

                # Confirm creation
                await interaction.response.edit_message(
                    content=f"Your character has been created successfully!",
                    view=None,
                    embed=embed
                )
            else:
                await interaction.response.send_message("Character creation failed. Please start over.", ephemeral=True)
                logging.error(f"Character creation failed for user {user_id}.")
        except KeyError:
            await interaction.response.send_message("Character data not found. Please start over.", ephemeral=True)
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinalizeCharacterButton callback for user {self.user_id}: {e}")

async def finalize_character(interaction: discord.Interaction, user_id):
    """
    Finalizes the character creation by instantiating a Character object.
    Args:
        interaction (discord.Interaction): The interaction object.
        user_id (str): The user's ID.
    Returns:
        Character or None: The created Character object or None if failed.
    """
    session = character_creation_sessions.get(user_id, {})
    if not session:
        await interaction.response.send_message("No character data found.", ephemeral=True)
        logging.error(f"No session data found for user {user_id} during finalization.")
        return None

    allocation = session.get('stats', {})
    is_valid, message = is_valid_point_allocation(allocation)
    if not is_valid:
        await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
        logging.warning(f"User {user_id} failed point allocation validation: {message}")
        return None

    # Create the Character instance
    character = Character(
        name=session.get('name', "Unnamed Character"),
        species=session.get('species', "Unknown Species"),
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

# ---------------------------- #
#          Command Tree         #
# ---------------------------- #

@tree.command(name="create_character", description="Create a new character")
async def create_character(interaction: discord.Interaction):
    """
    Slash command to initiate character creation.
    """
    try:
        await interaction.user.send("Let's create your character!", view=CharacterCreationView(bot))
        await interaction.response.send_message("Check your DMs to start character creation!", ephemeral=True)
        logging.info(f"User {interaction.user.id} initiated character creation.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "Unable to send you a DM. Please check your privacy settings.",
            ephemeral=True
        )
        logging.warning(f"Could not send DM to user {interaction.user.id} for character creation.")
    except Exception as e:
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.",
            ephemeral=True
        )
        logging.error(f"Error in create_character command for user {interaction.user.id}: {e}")

# ---------------------------- #
#           Events              #
# ---------------------------- #

@bot.event
async def on_ready():
    """
    Event handler for when the bot is ready.
    """
    try:
        print(f'Logged in as {bot.user.name}')
        await tree.sync()
        print("Command tree synchronized.")
        logging.info("Bot is ready and command tree synchronized.")
    except Exception as e:
        print(f"An error occurred in on_ready: {e}")
        logging.error(f"Error in on_ready event: {e}")

@bot.event
async def on_message(message: discord.Message):
    """
    Event handler for processing messages to handle in-game actions.
    """
    if message.author == bot.user:
        return

    logging.info(f"on_message triggered for message from {message.author.id}: '{message.content}'")

    # Check for '?listactions' command
    if message.content.strip() == '?listactions':
        if actions:
            action_list = ', '.join(actions.keys())
            await message.channel.send(f"Recognized actions: {action_list}")
            logging.info(f"User {message.author.id} requested action list.")
        else:
            await message.channel.send("No actions are currently recognized.")
            logging.info(f"User {message.author.id} requested action list, but no actions are loaded.")
        return  # Early return to prevent further processing

    user_id = str(message.author.id)

    if user_id not in characters:
        characters[user_id] = Character(name=message.author.name)
        save_characters(characters)
        await message.channel.send(f'Character created for {message.author.name}.')
        logging.info(f"Character created for user {user_id} with name {message.author.name}.")

    character = characters[user_id]
    action, stat = await parse_action(message)
    if action and stat:
        logging.info(f"Processing action '{action}' for user {user_id} associated with stat '{stat}'.")
        roll, total = perform_ability_check(character, stat)
        if roll is None or total is None:
            logging.error(f"Ability check failed for user {user_id}.")
            return  # Ability check failed due to an error

        # Fetch the last 10 messages from the channel, excluding action commands
        channel_history = [msg async for msg in message.channel.history(limit=10) if not msg.content.startswith('?')]
        
        # Get the content of the last 5 non-action messages
        last_messages_content = [msg.content for msg in channel_history[:5]]

        # Construct the prompt for difficulty determination
        difficulty_prompt = (
            f"Player {character.name} attempts to {action}. "
            f"Keeping in mind that player characters are meant to be a cut above the average person in ability and luck, \n"
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

        logging.info("Calling get_chatgpt_response for difficulty determination.")
        difficulty_response = await get_chatgpt_response(
            difficulty_prompt,
            last_messages_content,
            stat,
            total,
            roll,
            character,
            include_roll_info=False
        )
        logging.info("Completed get_chatgpt_response for difficulty determination.")

        try:
            difficulty = int(re.search(r'\d+', difficulty_response).group())
            logging.info(f"Difficulty determined for user {user_id}: {difficulty}")
        except (AttributeError, ValueError):
            COOLDOWN_PERIOD = 5  # Cooldown period in seconds
            current_time = asyncio.get_event_loop().time()
            if last_error_time.get(user_id, 0) is None or current_time - last_error_time.get(user_id, 0) > COOLDOWN_PERIOD:
                await message.channel.send("Sorry, I couldn't determine the difficulty of the task.")
                last_error_time[user_id] = current_time
                logging.error(f"Failed to parse difficulty for user {user_id}.")
            return

        # Determine the result based on the difficulty
        if roll == 20:
            result = "succeed with a critical success, obtaining an unexpected advantage or extraordinary result."
        elif total > difficulty:
            result = "succeed."
        elif total == difficulty:
            result = "succeed, but with a complication that heightens the tension."
        else:
            result = "fail."

        logging.info(f"Player {character.name} (user {user_id}) attempted to {action}. The DC was {difficulty}. It was a {result}.")

        # Construct the final prompt for narrative description
        prompt = (
            f"{character.name} attempted to {action} and they {result}.\n"
            f"Their gender is {character.gender} and their pronouns are {character.pronouns}.\n"
            f"Their species is: {character.species}\nA brief description of their character: {character.description}.\n"
            f"As the game master, describe their action and how the narrative and scene and NPCs react to this action. \n"
            f"Always end with 'What do you do? The DC was: {difficulty}.' \n" 
            f"And a brief explanation on the reasoning behind that number as DC. \n"
            f"Limit responses to 100 words.\n"
        )

        logging.info("Calling get_chatgpt_response for narrative response.")
        response = await get_chatgpt_response(
           prompt,
           last_messages_content,
           stat,
           total,
           roll,
           character,
           include_roll_info=True
        )
        logging.info("Completed get_chatgpt_response for narrative response.")

        logging.info(f"Sending narrative response to channel: {response}")
        await message.channel.send(response)
        logging.info(f"Narrative response sent to user {user_id}.")
        # Uncomment and implement update_world_anvil if needed
        # await update_world_anvil(character, action, response)
    else:
        # Optionally, do not send any message if no action is recognized
        logging.info("No valid action found in the message.")
        pass

    await bot.process_commands(message)

# ---------------------------- #
#          Helper Functions     #
# ---------------------------- #

def perform_ability_check(character, stat):
    """
    Performs an ability check by rolling a die and adding the stat modifier.
    Args:
        character (Character): The character performing the check.
        stat (str): The ability stat being checked.
    Returns:
        tuple: (roll, total) or (None, None) if failed.
    """
    try:
        modifier = character.get_stat_modifier(stat)
        roll = random.randint(1, 20)
        total = roll + modifier
        logging.info(f"Ability check for {character.name}: Rolled {roll} + modifier {modifier} = {total}")
        return roll, total
    except Exception as e:
        logging.error(f"Error in perform_ability_check for {character.name}: {e}")
        return None, None

async def parse_action(message):
    """
    Parses the user's message to identify actions prefixed with '?' and returns the action and associated stat.
    Args:
        message (discord.Message): The message object.
    Returns:
        tuple: (action, stat) or (None, None)
    """
    message_content = message.content.lower()
    logging.info(f"Parsing message from user {message.author.id}: '{message_content}'")

    # Updated regex pattern with negative lookbehind and lookahead
    pattern = r'(?<!\w)\?[A-Za-z]+(?!\w)'
    matches = re.findall(pattern, message_content)
    logging.info(f"Regex matches found: {matches}")

    # Track if multiple actions are found
    if len(matches) > 1:
        logging.warning(f"Multiple actions detected in message: {matches}")
        await message.channel.send("Please specify only one action at a time.")
        return None, None

    for match in matches:
        action = match.lstrip('?')
        logging.info(f"Parsed action: '{action}'")
        if action in actions:
            logging.info(f"Action recognized: '{action}'")
            return action, actions[action]
        else:
            await show_actions(message)
            logging.info(f"Action '{action}' not recognized.")
    
    logging.info("No valid action recognized in the message.")
    return None, None 

async def show_actions(message):
    """
    Sends a message listing recognized actions.
    Args:
        message (discord.Message): The message object.
    """
    if actions:
        action_list = ', '.join(actions.keys())
        await message.channel.send(f"Sorry, I don't recognize that action. Recognized actions: {action_list}")
        logging.info(f"Sent recognized actions list to user {message.author.id}.")
    else:
        await message.channel.send("No actions are currently recognized.")
        logging.info(f"User {message.author.id} requested actions, but no actions are loaded.")

async def get_chatgpt_response(prompt: str, channel_messages: list, stat: str, total: int, roll: int, character: Character, include_roll_info: bool = True) -> str:
    """
    Sends a prompt to OpenAI's GPT-4 using the AsyncOpenAI client and returns the response.
    Args:
        prompt (str): The prompt to send.
        channel_messages (list): The list of recent channel messages.
        stat (str): The ability stat involved in the check.
        total (int): The total check result.
        roll (int): The die roll result.
        character (Character): The character performing the action.
        include_roll_info (bool): Whether to include roll information in the response.
    Returns:
        str: The response from GPT-4.
    """
    try:
        # Prepare the messages for OpenAI
        messages = [
            {"role": "system", "content": "You are a game master for a fantasy role-playing game. Your job is to narrate the settings the players journey through, the results of their actions, and provide a sense of atmosphere through vivid and engaging descriptions."}
        ]

        # Add the last channel messages in chronological order
        for msg_content in reversed(channel_messages):
            messages.append({"role": "user", "content": msg_content})

        messages.append({"role": "user", "content": prompt})

        # Perform the asynchronous API call using the new method
        completion = await openai_client.chat.completions.create(
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

# ---------------------------- #
#         Running the Bot      #
# ---------------------------- #

bot.run(DISCORD_BOT_TOKEN)
