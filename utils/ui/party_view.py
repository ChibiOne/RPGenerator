class PartyView(View):
    def __init__(self, party: TravelParty):
        super().__init__(timeout=180)  # 3 minute timeout
        self.party = party

    @button(label="Accept Invite", style=discord.ButtonStyle.green, custom_id="accept_invite")
    async def accept_invite(self, button: Button, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        if not self.party.has_invite(user_id):
            await interaction.response.send_message(
                "This invitation wasn't for you!",
                ephemeral=True
            )
            return

        try:
            character = await load_or_get_character_redis(interaction.client, user_id, guild_id)
            if not character:
                await interaction.response.send_message(
                    "You need a character to join a party! Use `/create_character` first.",
                    ephemeral=True
                )
                return

            success, msg = self.party.add_member(character)
            if success:
                # Save party to Redis
                party_key = f"party:{guild_id}:{self.party.leader.user_id}"
                await interaction.client.redis_player.set(
                    party_key,
                    pickle.dumps(self.party.to_dict())
                )
                
                # Update UI
                embed = self.get_party_embed()
                await interaction.message.edit(embed=embed)
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            logging.error(f"Error accepting party invite: {e}")
            await interaction.response.send_message(
                "An error occurred while joining the party.",
                ephemeral=True
            )

    def get_party_embed(self) -> discord.Embed:
        """Create an embed showing party information"""
        embed = discord.Embed(
            title="🎭 Adventure Party",
            description=f"Led by {self.party.leader.name}",
            color=discord.Color.blue()
        )

        # Add member list
        members_text = ""
        for member in self.party.members.values():
            members_text += f"• **{member.name}** (Level {member.level} {member.char_class})\n"
        embed.add_field(
            name=f"Members ({self.party.size}/{self.party.max_size})",
            value=members_text or "No members yet",
            inline=False
        )

        # Add party stats
        embed.add_field(
            name="Party Stats",
            value=f"Average Level: {self.party.get_average_level():.1f}\n"
                  f"Movement Speed: {self.party.get_slowest_member().movement_speed}",
            inline=False
        )

        return embed