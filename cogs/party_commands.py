@bot.slash_command(
    name="create_party",
    description="Create a new adventure party"
)
async def create_party(ctx: discord.ApplicationContext):
    try:
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild_id)

        # Check if user already has a party
        existing_party_key = f"party:{guild_id}:{user_id}"
        if await bot.redis_player.exists(existing_party_key):
            await ctx.respond(
                "You're already in a party! Leave your current party first.",
                ephemeral=True
            )
            return

        # Load character
        character = await load_or_get_character_redis(bot, user_id, guild_id)
        if not character:
            await ctx.respond(
                "You need a character to create a party! Use `/create_character` first.",
                ephemeral=True
            )
            return

        # Create new party
        party = TravelParty(character)
        
        # Save to Redis
        await bot.redis_player.set(
            existing_party_key,
            pickle.dumps(party.to_dict())
        )

        # Create and send party view
        view = PartyView(party)
        embed = view.get_party_embed()
        await ctx.respond(
            "Created a new party!",
            embed=embed,
            view=view
        )

    except Exception as e:
        logging.error(f"Error creating party: {e}")
        await ctx.respond(
            "An error occurred while creating the party.",
            ephemeral=True
        )

@bot.slash_command(
    name="invite_to_party",
    description="Invite a player to your party"
)
async def invite_to_party(
    ctx: discord.ApplicationContext,
    player: discord.Option(
        discord.Member,
        description="The player to invite"
    )
):
    try:
        if player.bot:
            await ctx.respond("You can't invite bots to your party!", ephemeral=True)
            return

        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild_id)
        target_id = str(player.id)

        # Load party
        party_key = f"party:{guild_id}:{user_id}"
        party_data = await bot.redis_player.get(party_key)
        
        if not party_data:
            await ctx.respond(
                "You need to create a party first! Use `/create_party`",
                ephemeral=True
            )
            return

        party = await TravelParty.from_dict(pickle.loads(party_data), bot)
        
        if str(ctx.author.id) != str(party.leader.user_id):
            await ctx.respond(
                "Only the party leader can invite new members!",
                ephemeral=True
            )
            return

        if party.is_full:
            await ctx.respond(
                f"Your party is full! Maximum size is {party.max_size}",
                ephemeral=True
            )
            return

        if target_id in party.members:
            await ctx.respond(
                f"{player.display_name} is already in your party!",
                ephemeral=True
            )
            return

        # Send invite
        if party.invite_player(target_id):
            # Save updated party
            await bot.redis_player.set(
                party_key,
                pickle.dumps(party.to_dict())
            )

            view = PartyView(party)
            embed = view.get_party_embed()
            
            # Send invite message
            try:
                await player.send(
                    f"{ctx.author.display_name} has invited you to join their party!",
                    embed=embed,
                    view=view
                )
                await ctx.respond(
                    f"Sent party invitation to {player.display_name}!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await ctx.respond(
                    f"I couldn't send a DM to {player.display_name}. They need to enable DMs from server members.",
                    ephemeral=True
                )
        else:
            await ctx.respond(
                f"{player.display_name} has already been invited!",
                ephemeral=True
            )

    except Exception as e:
        logging.error(f"Error inviting to party: {e}")
        await ctx.respond(
            "An error occurred while sending the invitation.",
            ephemeral=True
        )

@bot.slash_command(
    name="leave_party",
    description="Leave your current party"
)
async def leave_party(ctx: discord.ApplicationContext):
    try:
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild_id)

        # Find party
        async for key in bot.redis_player.scan_iter(f"party:{guild_id}:*"):
            party_data = await bot.redis_player.get(key)
            if not party_data:
                continue

            party = await TravelParty.from_dict(pickle.loads(party_data), bot)
            if user_id in party.members:
                success, msg = party.remove_member(user_id)
                if success:
                    if party.members:  # If party still has members
                        # Save updated party
                        await bot.redis_player.set(
                            key,
                            pickle.dumps(party.to_dict())
                        )
                    else:  # If party is empty
                        await bot.redis_player.delete(key)

                    await ctx.respond(msg, ephemeral=True)
                    return

        await ctx.respond(
            "You're not in a party!",
            ephemeral=True
        )

    except Exception as e:
        logging.error(f"Error leaving party: {e}")
        await ctx.respond(
            "An error occurred while leaving the party.",
            ephemeral=True
        )

@bot.slash_command(
    name="disband_party",
    description="Disband your party (leader only)"
)
async def disband_party(ctx: discord.ApplicationContext):
    try:
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild_id)

        # Load party
        party_key = f"party:{guild_id}:{user_id}"
        party_data = await bot.redis_player.get(party_key)
        
        if not party_data:
            await ctx.respond(
                "You don't have a party to disband!",
                ephemeral=True
            )
            return

        party = await TravelParty.from_dict(pickle.loads(party_data), bot)
        
        if str(ctx.author.id) != str(party.leader.user_id):
            await ctx.respond(
                "Only the party leader can disband the party!",
                ephemeral=True
            )
            return

        # Delete party from Redis
        await bot.redis_player.delete(party_key)

        # Notify all members
        for member_id in party.members:
            try:
                user = await bot.fetch_user(int(member_id))
                await user.send(f"The party has been disbanded by {ctx.author.display_name}.")
            except (discord.NotFound, discord.Forbidden):
                continue

        await ctx.respond(
            "Party disbanded!",
            ephemeral=True
        )

    except Exception as e:
        logging.error(f"Error disbanding party: {e}")
        await ctx.respond(
            "An error occurred while disbanding the party.",
            ephemeral=True
        )
