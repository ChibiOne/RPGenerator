class GenericDropdown(discord.ui.Select):
    """
    A generic dropdown class that can be reused for various selections.
    """
    def __init__(self, placeholder, options, callback_func, user_id):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.callback_func = callback_func
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(self, interaction, self.user_id)