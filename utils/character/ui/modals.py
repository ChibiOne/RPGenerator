class CharacterNameModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Name")
        self.user_id = user_id
        self.character_name = InputText(
            label="Character Name",
            placeholder="Enter your character's name...",
            min_length=2,
            max_length=32,
            style=InputTextStyle.short
        )
        self.add_item(self.character_name)

    async def callback(self, interaction: discord.Interaction):
        character_name = self.character_name.value
        character_creation_sessions[self.user_id]['Name'] = character_name
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(self.user_id, 1)
        
        await interaction.response.send_message(
            content="Please select your gender:",
            embed=embed,
            view=GenderSelectionView(self.user_id),
            ephemeral=True
        )
        
        logging.info(f"User {self.user_id} entered name: {character_name}")
