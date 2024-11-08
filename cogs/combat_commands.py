@bot.slash_command(name="attack", description="Attack an NPC in your current area.")
@discord.option(name="npc_name", description="The name of the NPC to attack.")
async def attack(ctx: discord.ApplicationContext, npc_name: str):
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
            # Implement combat logic here
            # For simplicity, we'll assume the NPC is defeated
            area.remove_npc(npc.name)
            # Optionally, transfer NPC's inventory to the area or player
            area.inventory.extend(npc.inventory)
            await ctx.respond(f"You have defeated **{npc.name}**!", ephemeral=False)
            return

    await ctx.respond(f"**{npc_name}** is not in **{area.name}**.", ephemeral=True)
