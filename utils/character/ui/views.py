# utils/character/ui/views.py
from ..constants import POINT_BUY_TOTAL
from .buttons import StartCharacterButton
from .dropdowns import AbilitySelect
from ..session import session_manager
from .buttons import NextMentalAbilitiesButton, BackPhysicalAbilitiesButton, FinishAssignmentButton
from .dropdowns import GenericDropdown
from .buttons import FinalizeCharacterButton
from .modals import Modal, InputText

class CharacterCreationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(StartCharacterButton(bot))

class PhysicalAbilitiesView(discord.ui.View):
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.physical_abilities = ['Strength', 'Dexterity', 'Constitution']
        
        for ability in self.physical_abilities:
            global character_creation_sessions
            current_score = character_creation_sessions[user_id]['Stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(NextMentalAbilitiesButton(user_id, area_lookup))
        logging.info(f"PhysicalAbilitiesView created for user {user_id} with {len(self.children)} components.")


class MentalAbilitiesView(discord.ui.View):
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.mental_abilities = ['Intelligence', 'Wisdom', 'Charisma']
        for ability in self.mental_abilities:
            global character_creation_sessions
            current_score = character_creation_sessions[user_id]['Stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(BackPhysicalAbilitiesButton(user_id))
        self.add_item(FinishAssignmentButton(user_id, self.area_lookup))
        logging.info(f"MentalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class DescriptionModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Description")
        self.user_id = user_id
        self.description = InputText(
            label="Character Description",
            placeholder="Describe your character's appearance, personality, and background...",
            style=InputTextStyle.paragraph,
            max_length=1000,
            min_length=20
        )
        self.add_item(self.description)

    async def callback(self, interaction: discord.Interaction):
        description = self.description.value
        word_count = len(description.split())
        
        if word_count > 200:
            await interaction.response.send_message(
                f"Description is too long ({word_count} words). Please limit it to 200 words.",
                ephemeral=True
            )
            await interaction.followup.send_modal(DescriptionModal(self.user_id))
            return
            
        # Save description using capitalized key
        character_creation_sessions[self.user_id]['Description'] = description
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(self.user_id, 4)
        
        # Proceed to species selection
        await interaction.response.edit_message(
            content="Description set! Please select a species:",
            embed=embed,
            view=SpeciesSelectionView(self.user_id)
        )
        logging.info(f"User {self.user_id} provided description with {word_count} words.")

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

class ConfirmationView(discord.ui.View):
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.add_item(discord.ui.Button(
            label="Confirm", 
            style=discord.ButtonStyle.green,
            custom_id="confirm"
        ))
        self.add_item(discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.red,
            custom_id="cancel"
        ))

    async def callback(self, interaction: discord.Interaction):
        if interaction.custom_id == "confirm":
            # Proceed with character creation
            await finalize_character(interaction, self.user_id, self.area_lookup)
        else:
            # Return to ability scores
            await interaction.response.edit_message(
                content="Returning to ability scores...",
                view=MentalAbilitiesView(self.user_id, self.area_lookup)
            )

class FinalizeCharacterView(discord.ui.View):
    """
    View to finalize character creation.
    """
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.add_item(FinalizeCharacterButton(user_id, area_lookup))
        logging.info(f"FinalizeCharacterView created for user {user_id} with {len(self.children)} components.")
