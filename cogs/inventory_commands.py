@bot.slash_command(
    name="inventory",
    description="View your character's inventory and equipment"
)
async def inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)

    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    view = InventoryView(character)
    try:
        # Send the initial embed with view as a DM
        await interaction.user.send(embed=view.get_page_embed(), view=view)
        # Acknowledge the command in the channel
        await interaction.response.send_message(
            "I've sent your inventory details to your DMs!", 
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I couldn't send you a DM. Please check your privacy settings.", 
            ephemeral=True
        )
    except Exception as e:
        logging.error(f"Error sending inventory DM: {e}")
        await interaction.response.send_message(
            "An error occurred while sending your inventory details.", 
            ephemeral=True
        )

@bot.slash_command(name="pickup", description="Pick up an item from the area.")
@discord.option(name="item_name", description="The name of the item to pick up.")
async def pickup(ctx: discord.ApplicationContext, item_name: str):
    user_id = str(ctx.author.id)
    character = load_or_get_character(user_id)
    channel_id = get_guild_game_channel(character.last_interaction_guild)
        
    if not character:
        await ctx.respond(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return
   
    area_inventory = get_area_inventory(channel_id)
    # Find the item in the area inventory
    for item in area_inventory:
        if item.name.lower() == item_name.lower():
            if character.can_carry_more(item.weight):
                character.add_item_to_inventory(item)
                area_inventory.remove(item)
                save_characters(characters)
                await ctx.respond(f"You picked up **{item.name}**.", ephemeral=False)
                return
            else:
                await ctx.respond("You can't carry any more weight.", ephemeral=True)
                return

    await ctx.respond(f"The item **{item_name}** is not available in this area.", ephemeral=True)

@bot.slash_command(name="drop", description="Drop an item from your inventory into the area.")
@discord.option(name="item_name", description="The name of the item to drop.")
async def drop(ctx: discord.ApplicationContext, item_name: str):
    user_id = str(ctx.author.id)
    character = load_or_get_character(user_id)
    channel_id = get_guild_game_channel(character.last_interaction_guild)
        
    if not character:
        await ctx.respond(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            character.remove_item_from_inventory(item.name)
            area_inventory = get_area_inventory(channel_id)
            area_inventory.append(item)
            save_characters(characters)
            await ctx.respond(f"You dropped **{item.name}** into the area.", ephemeral=False)
            return

    await ctx.respond(f"You don't have an item named **{item_name}** in your inventory.", ephemeral=True)

@bot.slash_command(name="equip", description="Equip an item from your inventory.")
@discord.option(name="item_name", description="The name of the item to equip.")
@discord.option(
    name="slot",
    description="The equipment slot.",
    choices=['armor', 'left_hand', 'right_hand', 'back'] + 
            [f'belt_slot_{i+1}' for i in range(4)] + 
            [f'magic_slot_{i+1}' for i in range(3)]
)
async def equip(ctx: discord.ApplicationContext, item_name: str, slot: str):
    user_id = str(ctx.author.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await ctx.respond(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    slot = slot.lower()
    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            try:
                character.equip_item(item, slot)
                save_characters(characters)
                await ctx.respond(f"You have equipped **{item.name}** to **{slot}**.", ephemeral=False)
                return
            except ValueError as e:
                await ctx.respond(str(e), ephemeral=True)
                return

    await ctx.respond(f"You don't have an item named **{item_name}** in your inventory.", ephemeral=True)

@bot.slash_command(
    name="examine",
    description="Examine an item in detail"
)
@discord.option(name="item_name", description="The name of the item to examine")
async def examine(interaction: discord.Interaction, item_name: str):
    try:
        user_id = str(interaction.user.id)
        character = load_or_get_character(user_id)
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return  

        # Find item in inventory, equipment, or current area
        item = None
        location = None
        
        # Check inventory
        if character.inventory:
            for inv_key, inv_item in character.inventory.items():
                if (hasattr(inv_item, 'Name') and inv_item.Name.lower() == item_name.lower()) or \
                   (isinstance(inv_item, dict) and inv_item.get('Name', '').lower() == item_name.lower()):
                    item = inv_item
                    location = "inventory"
                    break
        
        # Check equipment if not found
        if not item and character.equipment:
            for slot, equip_item in character.equipment.items():
                if isinstance(equip_item, list):  # Handle belt/magic slots
                    for slot_item in equip_item:
                        if slot_item and \
                           ((hasattr(slot_item, 'Name') and slot_item.Name.lower() == item_name.lower()) or \
                            (isinstance(slot_item, dict) and slot_item.get('Name', '').lower() == item_name.lower())):
                            item = slot_item
                            location = f"equipped ({slot})"
                            break
                elif equip_item and \
                     ((hasattr(equip_item, 'Name') and equip_item.Name.lower() == item_name.lower()) or \
                      (isinstance(equip_item, dict) and equip_item.get('Name', '').lower() == item_name.lower())):
                    item = equip_item
                    location = f"equipped ({slot})"
                    break
        
        # Check current area if not found
        if not item and character.current_area and character.current_area.inventory:
            for area_item in character.current_area.inventory:
                if (hasattr(area_item, 'Name') and area_item.Name.lower() == item_name.lower()) or \
                   (isinstance(area_item, dict) and area_item.get('Name', '').lower() == item_name.lower()):
                    item = area_item
                    location = "in the area"
                    break

        if not item:
            await interaction.response.send_message(
                f"Could not find an item named '{item_name}'.",
                ephemeral=True
            )
            return

        # Convert dictionary to Item object if necessary
        if isinstance(item, dict):
            item = Item.from_dict(item)

        # Create the view and initial embed
        view = ExamineView(item, character)
        embed = view.get_embed()

        # Send the response
        await interaction.response.send_message(embed=embed, view=view)
        
    except Exception as e:
        logging.error(f"Error in examine command: {e}")
        await interaction.response.send_message(
            "An error occurred while examining the item.",
            ephemeral=True
        )