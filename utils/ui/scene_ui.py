class SceneView(discord.ui.View):
    def __init__(self, character, current_view="general"):
        super().__init__(timeout=180)  # 3 minute timeout
        self.character = character
        self.current_view = current_view
        
        # Add view selection buttons
        self.add_item(ViewButton("General", "general", "🌍", discord.ButtonStyle.blurple))
        self.add_item(ViewButton("NPCs", "npcs", "👥", discord.ButtonStyle.blurple))
        self.add_item(ViewButton("Items", "items", "💎", discord.ButtonStyle.blurple))
        if character.current_area.connected_areas:
            self.add_item(ViewButton("Exits", "exits", "🚪", discord.ButtonStyle.blurple))

    def get_embed(self):
        """Generate the appropriate embed based on current view"""
        area = self.character.current_area
        
        if self.current_view == "general":
            embed = discord.Embed(
                title=f"📍 {area.name}",
                description=area.description,
                color=discord.Color.green()
            )
            
            # Quick overview sections
            if area.npcs:
                npc_list = ", ".join(f"**{npc.name}**" for npc in area.npcs)
                embed.add_field(
                    name="Present NPCs",
                    value=npc_list,
                    inline=False
                )
            
            if area.inventory:
                item_list = ", ".join(f"**{item.Name}**" for item in area.inventory if hasattr(item, 'Name'))
                embed.add_field(
                    name="Visible Items",
                    value=item_list if item_list else "None",
                    inline=False
                )
            
            if area.connected_areas:
                exits = ", ".join(f"**{connected.name}**" for connected in area.connected_areas)
                embed.add_field(
                    name="Exits",
                    value=exits,
                    inline=False
                )
            
        elif self.current_view == "npcs":
            embed = discord.Embed(
                title=f"👥 People in {area.name}",
                color=discord.Color.blue()
            )
            
            if area.npcs:
                for npc in area.npcs:
                    # Create detailed NPC description
                    npc_details = []
                    if hasattr(npc, 'description'):
                        npc_details.append(npc.description)
                    if hasattr(npc, 'attitude'):
                        npc_details.append(f"*{npc.attitude}*")
                        
                    embed.add_field(
                        name=npc.name,
                        value="\n".join(npc_details) if npc_details else "A mysterious figure.",
                        inline=False
                    )
            else:
                embed.description = "There is no one else here."
            
        elif self.current_view == "items":
            embed = discord.Embed(
                title=f"💎 Items in {area.name}",
                color=discord.Color.gold()
            )
            
            if area.inventory:
                for item in area.inventory:
                    if hasattr(item, 'Name') and hasattr(item, 'Description'):
                        embed.add_field(
                            name=item.Name,
                            value=item.Description[:100] + "..." if len(item.Description) > 100 else item.Description,
                            inline=False
                        )
            else:
                embed.description = "There are no items of note here."
            
        elif self.current_view == "exits":
            embed = discord.Embed(
                title=f"🚪 Exits from {area.name}",
                color=discord.Color.purple()
            )
            
            if area.connected_areas:
                for connected in area.connected_areas:
                    # You might want to add more details about each exit
                    # like distance, difficulty, or special requirements
                    embed.add_field(
                        name=connected.name,
                        value=connected.description[:100] + "..." if len(connected.description) > 100 else connected.description,
                        inline=False
                    )
            else:
                embed.description = "There appear to be no exits from this area."
        
        # Add footer with helpful command hints based on current view
        if self.current_view == "npcs":
            embed.set_footer(text="Use /talk <name> to interact with NPCs")
        elif self.current_view == "items":
            embed.set_footer(text="Use /pickup <item> to collect items • /examine <item> for details")
        elif self.current_view == "exits":
            embed.set_footer(text="Use /travel <location> to move to a new area")
        else:
            embed.set_footer(text="Click the buttons below to focus on specific aspects of the area")
            
        return embed

class ViewButton(discord.ui.Button):
    def __init__(self, label, view_type, emoji, style):
        super().__init__(label=label, emoji=emoji, style=style)
        self.view_type = view_type

    async def callback(self, interaction: discord.Interaction):
        view: SceneView = self.view
        view.current_view = self.view_type
        
        # Update button styles
        for item in view.children:
            if isinstance(item, ViewButton):
                item.style = (
                    discord.ButtonStyle.green 
                    if item.view_type == self.view_type 
                    else discord.ButtonStyle.blurple
                )
        
        await interaction.response.edit_message(
            embed=view.get_embed(),
            view=view
        )