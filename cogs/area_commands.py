@bot.slash_command(name="npc_list", description="List all NPCs in your current area.")
async def npc_list(ctx: discord.ApplicationContext):
    user_id = str(ctx.author.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await ctx.respond(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    area = character.current_area
    if area.npcs:
        npc_names = ', '.join(npc.name for npc in area.npcs)
        await ctx.respond(f"NPCs in **{area.name}**: {npc_names}", ephemeral=False)
    else:
        await ctx.respond(f"There are no NPCs in **{area.name}**.", ephemeral=False)

@bot.slash_command(name="talk", description="Talk to an NPC in your current area.")
@discord.option(name="npc_name", description="The name of the NPC to talk to.")
async def talk(ctx: discord.ApplicationContext, npc_name: str):
    user_id = str(ctx.author.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await ctx.respond(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    area = character.current_area
    for npc in area.npcs:
        if npc.name.lower() == npc_name.lower():
            # For simplicity, send the first dialogue line
            dialogue = npc.get_dialogue if npc.dialogue else f"{npc.name} has nothing to say."
            await ctx.respond(f"**{npc.name}** says: \"{dialogue}\"", ephemeral=False)
            return

    await ctx.respond(f"**{npc_name}** is not in **{area.name}**.", ephemeral=True)

@bot.slash_command(name="scene", description="View your current surroundings")
async def scene(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        character = load_or_get_character(user_id)
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return

        if not character.current_area:
            await interaction.response.send_message(
                "You seem to be... nowhere? Please contact an administrator.",
                ephemeral=True
            )
            return

        # Create the view and initial embed
        view = SceneView(character)
        embed = view.get_embed()
        
        # Send the interactive scene description
        await interaction.response.send_message(embed=embed, view=view)
        logging.info(f"Scene information sent for user {user_id} in area {character.current_area.name}")

    except Exception as e:
        logging.error(f"Error in scene command: {e}", exc_info=True)
        await interaction.response.send_message(
            "An error occurred while displaying the scene. Please try again.",
            ephemeral=True
        )

@bot.slash_command(name="location", description="View your current location.")
async def location(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)

    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    area = character.current_area
    if not area:
        await interaction.response.send_message(
            "Your current area could not be found. Please contact the administrator.",
            ephemeral=True
        )
        return

    location = character.current_location
    region = character.current_region
    continent = character.current_continent
    world = character.current_world

    # Ensure 'area' is an Area object
    if area and not isinstance(area, Area):
        logging.error(f"current_area for user '{user_id}' is not an Area object.")
        await interaction.response.send_message("Your character's area data is corrupted.", ephemeral=True)
        return

    # Construct the response message
    response_message = (
        f"You are in **{area.name}**, located in **{location}**, "
        "in the region of f **{region}**, on the continent of **{continent}**, on the planet **{world}**."
    )

    await interaction.response.send_message(
        response_message,
        ephemeral=False
    )