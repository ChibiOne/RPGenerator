# utils/character/ui/embeds.py
import discord

def generate_ability_embed(user_id: str) -> discord.Embed:
    """Generates an embed reflecting the current ability scores and remaining points."""
    try:
        remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']
        assignments = character_creation_sessions[user_id]['Stats']

        embed = discord.Embed(title="Character Creation - Ability Scores", 
                            color=discord.Color.blue())
        embed.add_field(name="Remaining Points", 
                       value=f"{remaining_points}/{POINT_BUY_TOTAL}", 
                       inline=False)

        for ability in ['Strength', 'Dexterity', 'Constitution', 
                       'Intelligence', 'Wisdom', 'Charisma']:
            score = assignments.get(ability, 10)
            embed.add_field(name=ability, value=str(score), inline=True)

        embed.set_footer(text="Assign your ability scores using the dropdowns below.")

        return embed
    except Exception as e:
        logging.error(f"Error generating embed for user {user_id}: {e}")
        return None

async def update_embed(interaction, user_id):
    """
    Updates the embed in the original message to reflect the current state.
    """
    embed = generate_ability_embed(user_id)
    if embed:
        await interaction.message.edit(embed=embed)
        logging.info(f"Embed updated for user {user_id}.")
    else:
        logging.error(f"Failed to update embed for user {user_id}.")

