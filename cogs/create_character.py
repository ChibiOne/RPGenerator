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