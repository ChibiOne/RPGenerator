def create_character_progress_embed(user_id: str, current_step: int) -> discord.Embed:
    """
    Creates a progress embed for character creation.
    Args:
        user_id (str): The user's ID
        current_step (int): Current step in character creation (1-7)
    Returns:
        discord.Embed: The formatted embed
    """
    session = character_creation_sessions.get(user_id, {})
    name = session.get('Name', 'Unknown')
    
    embed = discord.Embed(
        title="Character Creation",
        description=f"Creating character: **{name}**",
        color=discord.Color.blue()
    )
    
    # Add character info fields if they exist
    if session.get('Gender'):
        embed.add_field(name="Gender", value=session['Gender'], inline=True)
    if session.get('Pronouns'):
        embed.add_field(name="Pronouns", value=session['Pronouns'], inline=True)
    if session.get('Species'):
        embed.add_field(name="Species", value=session['Species'], inline=True)
    if session.get('Char_Class'):
        embed.add_field(name="Class", value=session['Char_Class'], inline=True)
    
    # Add description in a collapsible field if it exists
    if session.get('Description'):
        desc = session['Description']
        if len(desc) > 100:
            desc = desc[:97] + "..."
        embed.add_field(name="Description", value=desc, inline=False)
    
    # Create progress indicator
    steps = [
        ("Name", True if current_step > 1 else False),
        ("Gender", True if current_step > 2 else False),
        ("Pronouns", True if current_step > 3 else False),
        ("Description", True if current_step > 4 else False),
        ("Species", True if current_step > 5 else False),
        ("Class", True if current_step > 6 else False),
        ("Abilities", True if current_step > 7 else False)
    ]
    
    progress = "\n".join(
        f"Step {i+1}/7: {step[0]} {'✓' if step[1] else '⏳' if i == current_step-1 else ''}"
        for i, step in enumerate(steps)
    )
    
    embed.add_field(name="Progress", value=progress, inline=False)
    return embed

def update_character_embed(session_data, current_step):
    """Creates a consistent embed for character creation progress"""
    embed = discord.Embed(
        title="Character Creation",
        description=f"Creating character: **{session_data.get('Name', 'Unknown')}**",
        color=discord.Color.blue()
    )
    
    # Basic info fields
    if session_data.get('Gender'):
        embed.add_field(name="Gender", value=session_data['Gender'], inline=True)
    if session_data.get('Pronouns'):
        embed.add_field(name="Pronouns", value=session_data['Pronouns'], inline=True)
    if session_data.get('Species'):
        embed.add_field(name="Species", value=session_data['Species'], inline=True)
    if session_data.get('Char_Class'):
        embed.add_field(name="Class", value=session_data['Char_Class'], inline=True)
    
    # Progress bar
    steps = ["Name", "Gender", "Pronouns", "Description", "Species", "Class", "Abilities"]
    progress = ""
    for i, step in enumerate(steps):
        if i < current_step:
            progress += f"Step {i+1}/7: {step} ✓\n"
        elif i == current_step:
            progress += f"Step {i+1}/7: {step} ⏳\n"
        else:
            progress += f"Step {i+1}/7: {step}\n"
    
    embed.add_field(name="Progress", value=progress, inline=False)
    return embed