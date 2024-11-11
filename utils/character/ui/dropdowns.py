class AbilitySelect(discord.ui.Select):
    """
    Dropdown for selecting an ability score for a specific ability.
    """
    def __init__(self, user_id, ability_name, current_score=None):
        self.user_id = user_id
        self.ability_name = ability_name
        options = [
            discord.SelectOption(label="8", description="Gain 2 points", default=(current_score == 8)),
            discord.SelectOption(label="9", description="Gain 1 point", default=(current_score == 9)),
            discord.SelectOption(label="10", description="0 points", default=(current_score == 10)),
            discord.SelectOption(label="11", description="Spend 1 point", default=(current_score == 11)),
            discord.SelectOption(label="12", description="Spend 2 points", default=(current_score == 12)),
            discord.SelectOption(label="13", description="Spend 3 points", default=(current_score == 13)),
            discord.SelectOption(label="14", description="Spend 5 points", default=(current_score == 14)),
            discord.SelectOption(label="15", description="Spend 7 points", default=(current_score == 15)),
        ]
        # Set the placeholder to show the current score
        if current_score is not None:
            placeholder_text = f"{self.ability_name}: {current_score}"
        else:
            placeholder_text = f"Assign {ability_name} score..."
        super().__init__(
            placeholder=placeholder_text,
            min_values=1,
            max_values=1,
            options=options
        )
        logging.info(f"AbilitySelect initialized for {ability_name} with current_score={current_score}.")

    async def callback(self, interaction: discord.Interaction):
        """
        Callback for ability score selection.
        """
        try:
            global character_creation_sessions
            selected_score = int(self.values[0])
            cost = calculate_score_cost(selected_score)
            user_id = self.user_id
            cur_view=self.view
            cur_message=interaction.message.content
            
            # Retrieve previous score and cost
            previous_score = character_creation_sessions[user_id]['Stats'].get(self.ability_name, 10)
            previous_cost = calculate_score_cost(previous_score)

            # Update the session data
            character_creation_sessions[user_id]['Stats'][self.ability_name] = selected_score
            character_creation_sessions[user_id]['points_spent'] += (cost - previous_cost)
            logging.info(f"User {user_id} set {self.ability_name} to {selected_score}. Cost: {cost}. Total points spent: {character_creation_sessions[user_id]['points_spent']}.")

            remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']

            if remaining_points < 0:
                # Revert the assignment
                character_creation_sessions[user_id]['Stats'][self.ability_name] = previous_score
                character_creation_sessions[user_id]['points_spent'] -= (cost - previous_cost)
                await interaction.response.send_message(
                    f"Insufficient points to assign **{selected_score}** to **{self.ability_name}**. You have **{remaining_points + (cost - previous_cost)} points** remaining.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points while assigning {self.ability_name}.")
                return

            current_score=character_creation_sessions[user_id]['Stats'].get(self.ability_name, 10),

            # Determine which view to recreate
            if isinstance(self.view, PhysicalAbilitiesView):
                new_view = PhysicalAbilitiesView(user_id, area_lookup)
            elif isinstance(self.view, MentalAbilitiesView):
                new_view = MentalAbilitiesView(user_id, area_lookup)
            else:
                # Fallback or error handling
                new_view = self.view
            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                view=new_view,
                embed=embed  
            )
        except ValueError:
            await interaction.followup.send_message(
                f"Invalid input for **{self.ability_name}**. Please select a valid score.",
                ephemeral=True
            )
            logging.error(f"User {self.user_id} selected an invalid score for {self.ability_name}: {self.values[0]}")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in AbilitySelect callback for {self.ability_name}, user {self.user_id}: {e}")