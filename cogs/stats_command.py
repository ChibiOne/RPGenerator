@bot.slash_command(name="stats", description="View your character's complete stats and abilities")
async def stats(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        debug_cache_state()
        character = load_or_get_character(user_id)
        debug_cache_state()
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return

        def _format_equipped_item(item):
            """Format equipped item name with indicators"""
            try:
                indicators = []
                if item.Effect:
                    if any(k.startswith('on_') for k in item.Effect.keys()):
                        indicators.append("📜")  # Custom effects
                    if 'AC' in item.Effect:
                        indicators.append(f"+{item.get_ac_bonus()} AC")
                    if 'Damage' in item.Effect:
                        damage = item.get_damage()
                        if damage:
                            indicators.append(f"{damage['dice']} {damage['type']}")
                if item.Is_Magical:
                    indicators.append("✨")
                
                return f"{item.Name} {' '.join(indicators)}".strip()
            except Exception as e:
                logging.error(f"Error formatting equipped item: {e}")
                return "Error formatting item"

        # Create the main character sheet embed
        embed = discord.Embed(
            title=f"{character.name}'s Character Sheet",
            description=f"Level {character.level} {character.species} {character.char_class}",
            color=discord.Color.blue()
        )

        # Basic Info Field
        basic_info = (
            f"**Gender:** {character.gender}\n"
            f"**Pronouns:** {character.pronouns}\n"
            f"**XP:** {character.xp}"
        )
        embed.add_field(name="Basic Info", value=basic_info, inline=False)

        # Health and Defense
        hp_bar = create_progress_bar(character.curr_hp, character.max_hp)
        defense_info = (
            f"**HP:** {character.curr_hp}/{character.max_hp} {hp_bar}\n"
            f"**AC:** {character.ac}\n"
            f"**Movement Speed:** {character.movement_speed} ft"
        )
        embed.add_field(name="Health & Defense", value=defense_info, inline=False)

        # Core Stats with Modifiers
        stats_info = ""
        for stat, value in character.stats.items():
            modifier = character.get_stat_modifier(stat)
            sign = "+" if modifier >= 0 else ""
            stats_info += f"**{stat}:** {value} ({sign}{modifier})\n"
        embed.add_field(name="Ability Scores", value=stats_info, inline=True)

        # Skills
        if character.skills:
            skills_info = "\n".join(f"**{skill}:** {value}" for skill, value in character.skills.items())
            embed.add_field(name="Skills", value=skills_info or "None", inline=True)

        # Equipment
        equipment_info = []
        if character.equipment:
            # Handle regular equipment slots
            for slot in ['Armor', 'Left_Hand', 'Right_Hand', 'Back']:
                item = character.equipment.get(slot)
                if item and hasattr(item, 'Name'):
                    equipment_info.append(f"**{slot}:** {_format_equipped_item(item)}")
                else:
                    equipment_info.append(f"**{slot}:** Empty")
            
            # Handle Belt Slots
            belt_items = []
            for i, item in enumerate(character.equipment.get('Belt_Slots', [])):
                if item and hasattr(item, 'Name'):
                    belt_items.append(f"Slot {i+1}: {_format_equipped_item(item)}")
            if belt_items:
                equipment_info.append("**Belt Slots:**\n" + "\n".join(belt_items))
            else:
                equipment_info.append("**Belt Slots:** Empty")
            
            # Handle Magic Slots
            magic_items = []
            for i, item in enumerate(character.equipment.get('Magic_Slots', [])):
                if item and hasattr(item, 'Name'):
                    magic_items.append(f"Slot {i+1}: {_format_equipped_item(item)}")
            if magic_items:
                equipment_info.append("**Magic Slots:**\n" + "\n".join(magic_items))
            else:
                equipment_info.append("**Magic Slots:** Empty")

        embed.add_field(
            name="Equipment",
            value="\n".join(equipment_info) if equipment_info else "No equipment",
            inline=False
        )

        # Spells and Spell Slots
        if character.spells or character.spellslots:
            spells_info = "**Spell Slots:**\n"
            if character.spellslots:
                for level, slots in character.spellslots.items():
                    if isinstance(slots, dict):
                        available = slots.get('available', 0)
                        maximum = slots.get('max', 0)
                        slot_bar = create_progress_bar(available, maximum)
                        spells_info += f"Level {level}: {available}/{maximum} {slot_bar}\n"
            
            if character.spells:
                spells_info += "\n**Known Spells:**\n"
                for level, spells in character.spells.items():
                    spell_list = ", ".join(spells) if isinstance(spells, list) else spells
                    spells_info += f"Level {level}: {spell_list}\n"
            
            embed.add_field(name="Spellcasting", value=spells_info or "No spells", inline=False)

        # Abilities
        if character.abilities:
            abilities_info = "\n".join(f"**{ability}:** {desc}" 
                                     for ability, desc in character.abilities.items())
            embed.add_field(name="Abilities", value=abilities_info or "No abilities", inline=False)

        # Currency
        if character.currency:
            currency_info = "\n".join(f"**{currency}:** {amount}" 
                                    for currency, amount in character.currency.items())
            embed.add_field(name="Currency", value=currency_info or "No currency", inline=True)

        # Add footer with character creation date or last updated
        embed.set_footer(text="Use /scene to view your surroundings")

        try:
            # Send the embed as a DM
            await interaction.user.send(embed=embed)
            # Acknowledge the command in the channel
            await interaction.response.send_message(
                "I've sent your character sheet to your DMs!", 
                ephemeral=True
            )
        except discord.Forbidden:
            # If DMs are disabled
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", 
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error sending character sheet DM: {e}")
            await interaction.response.send_message(
                "An error occurred while sending your character sheet.", 
                ephemeral=True
            )

        logging.info(f"Character sheet displayed for user {user_id}")

    except Exception as e:
        logging.error(f"Error displaying character sheet: {e}", exc_info=True)
        await interaction.response.send_message(
            "An error occurred while displaying your character sheet. Please try again.",
            ephemeral=True
        )