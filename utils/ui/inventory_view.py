class InventoryView(discord.ui.View):
    def __init__(self, character):
        super().__init__(timeout=180)  # 3 minute timeout
        self.character = character
        self.current_page = 0
        self.items_per_page = 10
        self.current_category = "All"
        
        # Define categories
        self.categories = ["All", "Equipment", "Consumable", "Tool", "Weapon", "Armor", "Other"]
        
        # Add category select menu
        self.add_item(CategorySelect(self.categories))

        # Initialize button states
        self.update_button_states()

    def update_button_states(self):
        """Update navigation button states based on current page and total pages"""
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        # Update prev button state
        if hasattr(self, 'prev_button'):
            self.prev_button.disabled = (self.current_page <= 0 or total_pages <= 1)
            
        # Update next button state
        if hasattr(self, 'next_button'):
            self.next_button.disabled = (self.current_page >= total_pages - 1 or total_pages <= 1)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey)
    async def prev_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        if total_pages <= 1:
            await interaction.response.defer()
            return
            
        if self.current_page > 0:
            self.current_page -= 1
            self.update_button_states()
            await interaction.response.edit_message(
                embed=self.get_page_embed(),
                view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        if total_pages <= 1:
            await interaction.response.defer()
            return
            
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_button_states()
            await interaction.response.edit_message(
                embed=self.get_page_embed(),
                view=self
            )
        else:
            await interaction.response.defer()

    def get_filtered_items(self):
        """Get items for current category"""
        if self.current_category == "All":
            equipment_items = [(slot, item) for slot, item in self.character.equipment.items() 
                             if item is not None and not isinstance(item, list)]
            inventory_items = [(None, item) for item in self.character.inventory.values()]
            return equipment_items + inventory_items
            
        items = []
        # Add equipped items of matching category
        for slot, item in self.character.equipment.items():
            if not isinstance(item, list) and item is not None:
                if (hasattr(item, 'Type') and item.Type == self.current_category) or \
                   (isinstance(item, dict) and item.get('Type') == self.current_category):
                    items.append((slot, item))
        
        # Add inventory items of matching category
        for item in self.character.inventory.values():
            if (hasattr(item, 'Type') and item.Type == self.current_category) or \
               (isinstance(item, dict) and item.get('Type') == self.current_category):
                items.append((None, item))
        
        return items

    def get_page_embed(self):
        """Generate embed for current page and category"""
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        embed = discord.Embed(
            title=f"{self.character.name}'s Equipment & Inventory",
            description=f"Category: **{self.current_category}** (Page {self.current_page + 1}/{total_pages})",
            color=discord.Color.blue()
        )

        start_idx = self.current_page * self.items_per_page
        page_items = items[start_idx:start_idx + self.items_per_page]

        if page_items:
            items_text = []
            for slot, item in page_items:
                if hasattr(item, 'Name'):
                    # Build item description with indicators
                    indicators = []
                    if hasattr(item, 'Effect') and item.Effect:
                        if any(k.startswith('on_') for k in item.Effect.keys()):
                            indicators.append("📜")  # Custom effects
                        if 'AC' in item.Effect:
                            indicators.append(f"+{item.get_ac_bonus()} AC")
                        if 'Damage' in item.Effect:
                            damage = item.get_damage()
                            if damage:
                                indicators.append(f"{damage['dice']} {damage['type']}")
                    if hasattr(item, 'Is_Magical') and item.Is_Magical:
                        indicators.append("✨")
                    
                    indicator_text = f" {' '.join(indicators)}" if indicators else ""
                    
                    if slot:
                        items_text.append(f"**{slot}**: {item.Name}{indicator_text} ({item.Type})")
                    else:
                        items_text.append(f"- {item.Name}{indicator_text} ({item.Type})")
                elif isinstance(item, dict):
                    if slot:
                        items_text.append(f"**{slot}**: {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
                    else:
                        items_text.append(f"- {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
            
            embed.add_field(
                name="Items",
                value='\n'.join(items_text),
                inline=False
            )
        else:
            embed.add_field(
                name="Items",
                value=f"No items in category: {self.current_category}",
                inline=False
            )

        # Add carrying capacity
        stats_text = (
            f"**Capacity**: {self.character.capacity} lbs\n"
            f"**Current Load**: {sum(item.Weight for item in self.character.inventory.values() if hasattr(item, 'Weight'))} lbs"
        )
        embed.add_field(name="Carrying Capacity", value=stats_text, inline=False)
        
        # Add legend if there are items with special indicators
        legend_lines = [
            "📜 Special Effect",
            "✨ Magical Item",
            "+X AC: Armor Class Bonus",
            "XdY: Weapon Damage"
        ]
        embed.set_footer(text=" • ".join(legend_lines))
        
        return embed

    def _format_item_name(self, item):
        """Format item name with effect indicators"""
        name = item.Name
        if item.Effect:
            if any(k.startswith('on_') for k in item.Effect.keys()):
                name += " 📜"  # Indicate custom effects
            if item.Is_Magical:
                name += " ✨"  # Indicate magical item
        return name

class CategorySelect(discord.ui.Select):
    def __init__(self, categories):
        options = [
            discord.SelectOption(
                label=category,
                description=f"View {category.lower()} items"
            ) for category in categories
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        view.current_category = self.values[0]
        view.current_page = 0  # Reset to first page when changing categories
        view.update_button_states()  # Update button states for new category
        await interaction.response.edit_message(
            embed=view.get_page_embed(),
            view=view
        )