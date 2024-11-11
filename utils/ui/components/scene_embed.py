# Helper function to create scene embed
def create_scene_embed(area):
    """Creates an embed for scene description"""
    try:
        embed = discord.Embed(
            title=area.name,
            description=area.description,
            color=discord.Color.green()
        )

        # Connected Areas
        if hasattr(area, 'connected_areas') and area.connected_areas:
            connected_area_names = ', '.join(f"**{connected_area.name}**" 
                                           for connected_area in area.connected_areas)
            embed.add_field(
                name="Connected Areas",
                value=connected_area_names,
                inline=False
            )
        else:
            embed.add_field(name="Connected Areas", value="None", inline=False)

        # NPCs
        if hasattr(area, 'npcs') and area.npcs:
            npc_names = ', '.join(f"**{npc.name}**" for npc in area.npcs)
            embed.add_field(name="NPCs Present", value=npc_names, inline=False)
        else:
            embed.add_field(name="NPCs Present", value="None", inline=False)

        # Items
        if hasattr(area, 'inventory') and area.inventory:
            item_names = ', '.join(f"**{item.name}**" 
                                 for item in area.inventory if hasattr(item, 'name'))
            embed.add_field(
                name="Items Available",
                value=item_names if item_names else "None",
                inline=False
            )
        else:
            embed.add_field(name="Items Available", value="None", inline=False)

        return embed
    except Exception as e:
        logging.error(f"Error creating scene embed: {e}", exc_info=True)
        return None