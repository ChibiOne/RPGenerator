class ExamineView(discord.ui.View):
    def __init__(self, item, character):
        super().__init__(timeout=180)  # 3 minute timeout
        self.item = item
        self.character = character
        self.current_view = "general"
        
        # Add view selection buttons based on item type
        self.add_item(ViewButton("General", "general", "📜", discord.ButtonStyle.blurple))
        
        if hasattr(item, 'Effect') and item.Effect:
            self.add_item(ViewButton("Effects", "effects", "✨", discord.ButtonStyle.blurple))
            
        if item.Type in ["Weapon", "Armor", "Shield"]:
            self.add_item(ViewButton("Combat", "combat", "⚔️", discord.ButtonStyle.blurple))
            
        if item.Is_Magical:
            self.add_item(ViewButton("Magical", "magic", "🔮", discord.ButtonStyle.blurple))

    def _format_effect(self, effect_type, value):
        """Format effect description based on type"""
        if effect_type == 'on_equip' or effect_type == 'on_unequip' or effect_type == 'on_use':
            return "📜 Custom effect (via code)"
        elif effect_type == 'Heal':
            return f"Restores {value} hit points"
        elif effect_type == 'Damage':
            return f"Deals {value} damage"
        elif effect_type == 'AC':
            return f"Provides +{value} to Armor Class"
        elif effect_type == 'Buff':
            return f"Grants {value}"
        return f"{effect_type}: {value}"

    def get_embed(self):
        if self.current_view == "general":
            embed = discord.Embed(
                title=self.item.Name,
                description=self.item.Description,
                color=self._get_rarity_color()
            )
            
            # Basic info
            embed.add_field(
                name="Basic Information",
                value=f"**Type:** {self.item.Type}\n"
                    f"**Weight:** {self.item.Weight} lbs\n"
                    f"**Value:** {self.item.Average_Cost} gold\n"
                    f"**Rarity:** {self.item.Rarity}",
                inline=False
            )
            
            if self.item.Proficiency_Needed:
                embed.add_field(
                    name="Required Proficiency",
                    value=self.item.Proficiency_Needed,
                    inline=False
                )
            self._add_contextual_footer(embed)
            return embed
            
        elif self.current_view == "effects":
            embed = discord.Embed(
                title=f"{self.item.Name} - Effects",
                color=self._get_rarity_color()
                )
                
            if isinstance(self.item.Effect, dict):
                for effect_name, effect in self.item.Effect.items():
                    if isinstance(effect, dict):
                        if effect['type'] == 'code':
                            # For code effects, show a simplified description
                            effect_desc = "📜 Custom effect (via code)"
                        else:
                            effect_desc = self._format_effect(effect_name, effect['value'])
                    else:
                        effect_desc = self._format_effect(effect_name, effect)
                    
                    embed.add_field(
                        name=effect_name.replace('_', ' ').title(),
                        value=effect_desc,
                        inline=False
                    )
            else:
                embed.description = str(self.item.Effect)


        elif self.current_view == "combat":
            embed = discord.Embed(
                title=f"{self.item.Name} - Combat Statistics",
                color=self._get_rarity_color()
            )
            
            if self.item.Type == "Weapon":
                # Extract the actual values from the effect dictionaries
                damage_info = self.item.Effect.get('Damage', {})
                damage_type = self.item.Effect.get('Damage_Type', {})
                
                # Get the actual values, handling both direct values and dict formats
                if isinstance(damage_info, dict):
                    damage_value = damage_info.get('value', 'None')
                else:
                    damage_value = damage_info

                if isinstance(damage_type, dict):
                    damage_type_value = damage_type.get('value', 'Unknown')
                else:
                    damage_type_value = damage_type

                embed.add_field(
                    name="Damage",
                    value=f"**Base Damage:** {damage_value}\n**Damage Type:** {damage_type_value}",
                    inline=False
                )
                    
            elif self.item.Type in ["Armor", "Shield"]:
                ac_bonus = self.item.Effect.get('AC', {})
                if isinstance(ac_bonus, dict):
                    ac_value = ac_bonus.get('value', 0)
                else:
                    ac_value = ac_bonus

                embed.add_field(
                    name="Defense",
                    value=f"**AC Bonus:** +{ac_value}",
                    inline=False
                )
                    
            # Add comparison with currently equipped items
            if self.character:
                embed.add_field(
                    name="Comparison",
                    value=self._get_comparison_text(),
                    inline=False
                )


        elif self.current_view == "magic":
            embed = discord.Embed(
                title=f"{self.item.Name} - Magical Properties",
                color=self._get_rarity_color()
            )
            
            if isinstance(self.item.Effect, dict):
                magical_effects = []
                for effect_type, value in self.item.Effect.items():
                    if effect_type not in ['Damage', 'Damage_Type', 'AC']:  # Skip basic combat effects
                        # Extract the actual value if it's in a dictionary
                        if isinstance(value, dict):
                            effect_value = value.get('value', value)
                        else:
                            effect_value = value
                        
                        magical_effects.append(self._format_effect(effect_type, effect_value))
                    
                if magical_effects:
                    embed.add_field(
                        name="Magical Effects",
                        value="\n".join(magical_effects),
                        inline=False
                    )
                    
            # Add any magical lore or special properties
            if hasattr(self.item, 'magical_lore'):
                embed.add_field(
                    name="Magical Lore",
                    value=self.item.magical_lore,
                    inline=False
                )

        # Add footer based on context
        self._add_contextual_footer(embed)
        return embed

    def _get_rarity_color(self):
        """Return color based on item rarity"""
        rarity_colors = {
            'Common': discord.Color.light_grey(),
            'Uncommon': discord.Color.green(),
            'Rare': discord.Color.blue(),
            'Very Rare': discord.Color.purple(),
            'Legendary': discord.Color.gold(),
            'Artifact': discord.Color.red()
        }
        return rarity_colors.get(self.item.Rarity, discord.Color.default())

    def _format_effect(self, effect_type, value):
        """Format effect description based on type"""
        if effect_type == 'Heal':
            return f"Restores {value} hit points"
        elif effect_type == 'Damage':
            return f"Deals {value} damage"
        elif effect_type == 'AC':
            return f"Provides +{value} to Armor Class"
        elif effect_type == 'Buff':
            return f"Grants {value}"
        return f"{effect_type}: {value}"

    def _get_comparison_text(self):
        """Generate comparison text with equipped items"""
        if not self.character:
            return "No comparison available"
            
        comparison_text = []
        if self.item.Type == "Weapon":
            equipped_weapon = None
            if self.character.equipment.get('Right_Hand') and hasattr(self.character.equipment['Right_Hand'], 'Type'):
                if self.character.equipment['Right_Hand'].Type == "Weapon":
                    equipped_weapon = self.character.equipment['Right_Hand']
            
            if equipped_weapon:
                comparison_text.append(f"Currently equipped: {equipped_weapon.Name}")
                if hasattr(equipped_weapon, 'Effect') and hasattr(self.item, 'Effect'):
                    current_damage = equipped_weapon.Effect.get('Damage', {})
                    new_damage = self.item.Effect.get('Damage', {})
                    
                    # Extract actual values
                    if isinstance(current_damage, dict):
                        current_damage = current_damage.get('value', '0')
                    if isinstance(new_damage, dict):
                        new_damage = new_damage.get('value', '0')
                    
                    comparison_text.append(f"Damage comparison: {current_damage} → {new_damage}")
                    
        elif self.item.Type in ["Armor", "Shield"]:
            equipped_item = self.character.equipment.get(self.item.Type)
            if equipped_item:
                comparison_text.append(f"Currently equipped: {equipped_item.Name}")
                if hasattr(equipped_item, 'Effect') and hasattr(self.item, 'Effect'):
                    current_ac = equipped_item.Effect.get('AC', {})
                    new_ac = self.item.Effect.get('AC', {})
                    
                    # Extract actual values
                    if isinstance(current_ac, dict):
                        current_ac = current_ac.get('value', 0)
                    if isinstance(new_ac, dict):
                        new_ac = new_ac.get('value', 0)
                    
                    comparison_text.append(f"AC comparison: +{current_ac} → +{new_ac}")      
        return "\n".join(comparison_text) if comparison_text else "No similar item equipped"

    def _add_contextual_footer(self, embed):
        """Add contextual footer text based on item type and view"""
        footer_text = []
        
        if self.item.Type == "Consumable":
            footer_text.append("Use /use <item> to consume this item")
        elif self.item.Type in ["Weapon", "Armor", "Shield"]:
            footer_text.append("Use /equip <item> to equip this item")
            
        if self.item.Is_Magical and self.current_view != "magic":
            footer_text.append("Click the 🔮 button to view magical properties")
            
        embed.set_footer(text=" • ".join(footer_text) if footer_text else "")