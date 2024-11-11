class StartCharacterButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        global character_creation_sessions
        try:
            user_id = str(interaction.user.id)
            
            # Initialize session if it doesn't exist
            if character_creation_sessions is None:
                character_creation_sessions = {}
            
            if user_id not in character_creation_sessions:
                character_creation_sessions[user_id] = {'Stats': {}, 'points_spent': 0}

            # Create initial embed
            embed = discord.Embed(
                title="Character Creation - Ability Scores",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Remaining Points",
                value=f"{POINT_BUY_TOTAL}/{POINT_BUY_TOTAL}",
                inline=False
            )
            embed.set_footer(text="Assign your ability scores using the dropdowns below.")

            # Present the modal to get the character's name
            await interaction.response.send_modal(CharacterNameModal(user_id))
            
        except Exception as e:
            logging.error(f"Error in StartCharacterButton callback for user {user_id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )

class NextMentalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Next", style=discord.ButtonStyle.blurple)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            global character_creation_sessions
            # Check if points_spent exceeds POINT_BUY_TOTAL
            points_spent = character_creation_sessions[user_id]['points_spent']
            if points_spent > POINT_BUY_TOTAL:
                await interaction.response.send_message(
                    f"You have overspent your points by **{points_spent - POINT_BUY_TOTAL}** points. Please adjust your ability scores.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points before navigating to MentalAbilitiesView.")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                content="Now, please assign your mental abilities:",
                view=MentalAbilitiesView(user_id, self.area_lookup),
                embed=embed  
            )
            logging.info(f"User {user_id} navigated to MentalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in NextMentalAbilitiesButton callback for user {self.user_id}: {e}")

class BackPhysicalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Back", style=discord.ButtonStyle.gray)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Proceed back to PhysicalAbilitiesView
            await interaction.response.edit_message(
                content="Returning to Physical Abilities assignment:",
                view=PhysicalAbilitiesView(user_id, area_lookup),
                embed=embed 
            )
            logging.info(f"User {user_id} navigated back to PhysicalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in BackPhysicalAbilitiesButton callback for user {self.user_id}: {e}")

class FinishAssignmentButton(discord.ui.Button):
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Finish", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction):
        try:
            global character_creation_sessions
            user_id = self.user_id
            allocation = character_creation_sessions[user_id]['Stats']
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(
                    f"Point allocation error: {message}. Please adjust your scores before finalizing.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} failed point allocation validation: {message}")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            await interaction.response.edit_message(
                content="All ability scores have been assigned correctly. Click the button below to finish.",
                view=FinalizeCharacterView(user_id, self.area_lookup),
                embed=embed 
            )
            logging.info(f"User {user_id} prepared to finalize character creation.")
        except KeyError:
            await interaction.response.send_message(
                "Character data not found. Please start the character creation process again.",
                ephemeral=True
            )
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinishAssignmentButton callback for user {self.user_id}: {e}")

class FinalizeCharacterButton(discord.ui.Button):
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    def _get_item_indicators(self, item):
        """Get indicator symbols for an item's effects"""
        indicators = []
        if hasattr(item, 'Effect') and item.Effect:
            if any(k.startswith('on_') for k in item.Effect.keys()):
                indicators.append("📜")
            if 'AC' in item.Effect:
                ac_bonus = item.get_ac_bonus()
                if ac_bonus:
                    indicators.append(f"+{ac_bonus} AC")
            if 'Damage' in item.Effect:
                damage = item.get_damage()
                if damage:
                    indicators.append(f"{damage['dice']}")
        if hasattr(item, 'Is_Magical') and item.Is_Magical:
            indicators.append("✨")
            
        return f" {' '.join(indicators)}" if indicators else ""

    async def callback(self, interaction: discord.Interaction):
        try:
            global character_creation_sessions
            user_id = self.user_id
            session = self.bot.session_manager.create_session(user_id)

            if not session:
                await interaction.response.send_message("No character data found. Please start over.", ephemeral=True)
                logging.error(f"No character data found for user {user_id} during finalization.")
                return

            allocation = session.get('Stats', {})
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
                logging.warning(f"User {user_id} failed point allocation validation during finalization: {message}")
                return

            # Use self.area_lookup instead of area_lookup
            character = await finalize_character(interaction, user_id, self.area_lookup)
            if character:
                # Save the character data
                characters[user_id] = character
                save_characters(characters)
                del character_creation_sessions[user_id]
                logging.info(f"Character '{character.name}' created successfully for user {user_id}.")

                # Create a final character summary embed
                embed = discord.Embed(title=f"Character '{character.name}' Created!", color=discord.Color.green())
                embed.add_field(name="Species", value=character.species, inline=True)
                embed.add_field(name="Class", value=character.char_class, inline=True)
                embed.add_field(name="Gender", value=character.gender, inline=True)
                embed.add_field(name="Pronouns", value=character.pronouns, inline=True)
                embed.add_field(name="Description", value=character.description, inline=False)
                
                # Add stats
                stats_text = "\n".join(f"{stat}: {value}" for stat, value in character.stats.items())
                embed.add_field(name="Stats", value=stats_text, inline=True)
                
                # Add equipment
                equipment_text = []
                for slot, item in character.equipment.items():
                    if isinstance(item, list):
                        # Handle belt slots and magic slots
                        items = [i.Name if hasattr(i, 'Name') else 'Empty' for i in item if i is not None]
                        equipment_text.append(f"{slot}: {', '.join(items) if items else 'Empty'}")
                    else:
                        # Handle regular equipment slots
                        item_name = item.Name if item and hasattr(item, 'Name') else 'Empty'
                        equipment_text.append(f"{slot}: {item_name}")
                embed.add_field(name="Equipment", value="\n".join(equipment_text), inline=True)
                
                # Add inventory
                if character.inventory:
                    inventory_text = []
                    for item_key, item in character.inventory.items():
                        if hasattr(item, 'Name'):
                            inventory_text.append(item.Name)
                        elif isinstance(item, dict) and 'Name' in item:
                            inventory_text.append(item['Name'])
                    inventory_display = "\n".join(inventory_text) if inventory_text else "Empty"
                else:
                    inventory_display = "Empty"
                embed.add_field(name="Inventory", value=inventory_display, inline=True)

                # Confirm creation
                await interaction.response.edit_message(
                    content=f"Your character has been created successfully!",
                    view=None,
                    embed=embed
                )
            else:
                await interaction.response.send_message("Character creation failed. Please start over.", ephemeral=True)
                logging.error(f"Character creation failed for user {user_id}.")
        except KeyError:
            await interaction.response.send_message("Character data not found. Please start over.", ephemeral=True)
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinalizeCharacterButton callback for user {self.user_id}: {e}")