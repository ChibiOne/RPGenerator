# cogs/character/creation.py
from ...utils.character.session import session_manager
from ...utils.character.equipment import EquipmentManager

class CharacterCreation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.equipment_manager = EquipmentManager(bot.equipment_manager)
        self.item_manager = bot.item_manager

    @bot.slash_command(name="create_character", description="Create a new character")
    async def create_character(ctx: discord.ApplicationContext):
        global character_creation_sessions
        try:
            # Respond to the interaction first
            await ctx.defer(ephemeral=True)
            
            try:
                # Initialize character creation session
                user_id = str(ctx.author.id)
                if character_creation_sessions is None:
                    character_creation_sessions = {}
                character_creation_sessions[user_id] = {'Stats': {}, 'points_spent': 0}
                
                # Send DM with character creation view
                await ctx.author.send(
                    "Let's create your character!", 
                    view=CharacterCreationView(bot)
                )
                
                # Follow up to the original interaction
                await ctx.respond(
                    "Check your DMs to start character creation!",
                    ephemeral=True
                )
                
                logging.info(f"User {ctx.author.id} initiated character creation.")
                
            except discord.Forbidden:
                await ctx.respond(
                    "Unable to send you a DM. Please check your privacy settings.",
                    ephemeral=True
                )
                
        except Exception as e:
            logging.error(f"Error in create_character: {e}")
            await ctx.respond(
                "An error occurred while creating your character.",
                ephemeral=True
            )
            
    def cog_unload(self):
        """Clean up any existing sessions when cog is unloaded"""
        self.bot.session_manager.sessions.clear()

    @commands.Cog.listener()
    async def on_interaction_timeout(self, interaction: discord.Interaction):
        """Clean up sessions that have timed out"""
        user_id = str(interaction.user.id)
        if session := self.bot.session_manager.get_session(user_id):
            self.bot.session_manager.end_session(user_id)
            try:
                await interaction.response.send_message(
                    "Character creation session expired.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                pass

async def handle_class_selection(self, interaction: discord.Interaction, class_name: str):
    user_id = str(interaction.user.id)
    session = session_manager.get_session(user_id)
    
    if not session:
        await interaction.response.send_message(
            "Session expired. Please start character creation again.",
            ephemeral=True
        )
        return

    # Get starting equipment for class
    equipment, inventory_items = self.equipment_manager.get_starting_equipment(class_name)
    
    # Update session
    session.char_class = class_name
    session.equipment = equipment
    session.inventory = {str(i): item for i, item in enumerate(inventory_items)}