async def start_ability_score_assignment(interaction: discord.Interaction, user_id: str):
    """
    Start the ability score assignment process for a character.
    """
    try:
        await interaction.response.edit_message(
            content="Let's begin your character creation!\n\n"
            f"You have **{POINT_BUY_TOTAL} points** to distribute among your abilities using the point-buy system.\n\n"
            "Here's how the costs work:\n"
            "- **8:** Gain 2 points\n"
            "- **9:** Gain 1 point\n"
            "- **10:** 0 points\n"
            "- **11:** Spend 1 point\n"
            "- **12:** Spend 2 points\n"
            "- **13:** Spend 3 points\n"
            "- **14:** Spend 5 points\n"
            "- **15:** Spend 7 points\n\n"
            "No ability score can be raised above **15**, and none can be lowered below **8**.\n\n"
            "Please assign your **Physical Attributes**:",
            view=PhysicalAbilitiesView(user_id, area_lookup)
        )
        logging.info(f"Started ability score assignment for user {user_id}")
    except Exception as e:
        logging.error(f"Error starting ability score assignment for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while starting ability score assignment. Please try again.",
            ephemeral=True
        )