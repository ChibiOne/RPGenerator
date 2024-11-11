# cogs/events/message_handler.py
import discord
from discord.ext import commands
import logging

class MessageHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Event handler for processing messages to handle in-game actions."""
        if message.author == bot.user:
                return

        if message.guild:
            shard_id = (message.guild.id >> 22) % bot.shard_count if bot.shard_count else None
            if shard_id is not None and shard_id not in bot.shards:
                return

        logging.info(f"on_message triggered for message from {message.author.id}: '{message.content}'")

        # Check for '?listactions' command
        if message.content.strip() == '?listactions':
            if actions:
                action_list = ', '.join(actions.keys())
                await message.channel.send(f"Recognized actions: {action_list}")
                logging.info(f"User {message.author.id} requested action list.")
            else:
                await message.channel.send("No actions are currently recognized.")
                logging.info(f"User {message.author.id} requested action list, but no actions are loaded.")
            return  # Early return to prevent further processing

        user_id = str(message.author.id)

        if user_id not in characters:
            characters[user_id] = Character(user_id=user_id, name=message.author.name)
            save_characters(characters)
            await message.channel.send(f'Character created for {message.author.name}.')
            logging.info(f"Character created for user {user_id} with name {message.author.name}.")

        character = load_or_get_character(user_id)
    
        action, stat = await parse_action(message)
        if action and stat:
            logging.info(f"Processing action '{action}' for user {user_id} associated with stat '{stat}'.")
            roll, total = perform_ability_check(character, stat)
            if roll is None or total is None:
                logging.error(f"Ability check failed for user {user_id}.")
                return  # Ability check failed due to an error

            # Fetch the last 10 messages from the channel, excluding action commands
            channel_history = [msg async for msg in message.channel.history(limit=10) if not msg.content.startswith('?')]

            # Get the content of the last 5 non-action messages
            last_messages_content = [msg.content for msg in channel_history[:5]]

            # Construct the prompt for difficulty determination
            difficulty_prompt = (
                f"Player {character.name} attempts to {action}. "
                f"Keeping in mind that player characters are meant to be a cut above the average person in ability and luck, \n"
                f"based on the context of the action and the surrounding \n"
                f"circumstances contained in previous messages, talk yourself through the nuances of the \n"
                f"scene, the action, and what else is happening around them, and determine the difficulty (DC) of the task. "
                f"This should be represented with a number between 5 and 30, \n"
                f"with 5 being trivial (something like climbing a tree to escape a pursuing creature), 10 being very easy (something like recalling what you know about defeating an enemy), 12 being easy (something like tossing a rock at a close target), "
                f"15 being challenging (actions like identifying rare mushrooms and their unique properties), 17 being difficult (actions like breaking down a heavy wooden door), 20 being extremely \n"
                f"difficult (something like using rope to grapple onto an object while falling). \n"
                f"Above 20 should be reserved for actions that are increasingly \n"
                f"impossible. For example, 25 might be something like interpreting words in a language you don't understand \n"
                f"No difficulty should ever go above 30, which should be reserved \n"
                f"for actions that are almost certainly impossible, but a freak \n"
                f"chance of luck exists, something like convincing the main villain to abandon their plan and be their friend.\n"
                f"Just provide the number."
            )

            logging.info("Calling get_chatgpt_response for difficulty determination.")
            difficulty_response = await get_chatgpt_response(
                difficulty_prompt,
                last_messages_content,
                stat,
                total,
                roll,
                character,
                include_roll_info=False
            )
            logging.info("Completed get_chatgpt_response for difficulty determination.")

            try:
                difficulty = int(re.search(r'\d+', difficulty_response).group())
                logging.info(f"Difficulty determined for user {user_id}: {difficulty}")
            except (AttributeError, ValueError):
                COOLDOWN_PERIOD = 5  # Cooldown period in seconds
                current_time = asyncio.get_event_loop().time()
                if last_error_time.get(user_id, 0) is None or current_time - last_error_time.get(user_id, 0) > COOLDOWN_PERIOD:
                    await message.channel.send("Sorry, I couldn't determine the difficulty of the task.")
                    last_error_time[user_id] = current_time
                    logging.error(f"Failed to parse difficulty for user {user_id}.")
                return

            # Determine the result based on the difficulty
            if roll == 20:
                result = "succeed with a critical success, obtaining an unexpected advantage or extraordinary result."
            elif total > difficulty:
                result = "succeed."
            elif total == difficulty:
                result = "succeed, but with a complication that heightens the tension."
            else:
                result = "fail."

            logging.info(f"Player {character.name} (user {user_id}) attempted to {action}. The DC was {difficulty}. It was a {result}.")

            # Construct the final prompt for narrative description
            prompt = (
                f"{character.name} attempted to {action} and they {result}.\n"
                f"Their gender is {character.gender} and their pronouns are {character.pronouns}.\n"
                f"Their species is: {character.species}\nA brief description of their character: {character.description}.\n"
                f"As the game master, describe their action and how the narrative and scene and NPCs react to this action. \n"
                f"Always end with 'What do you do? The DC was: {difficulty}.' \n" 
                f"And a brief explanation on the reasoning behind that number as DC. \n"
                f"Limit responses to 100 words.\n"
            )

            logging.info("Calling get_chatgpt_response for narrative response.")
            response = await get_chatgpt_response(
            prompt,
            last_messages_content,
            stat,
            total,
            roll,
            character,
            include_roll_info=True
            )
            logging.info("Completed get_chatgpt_response for narrative response.")

            logging.info(f"Sending narrative response to channel: {response}")
            await message.channel.send(response)
            logging.info(f"Narrative response sent to user {user_id}.")
            # Uncomment and implement update_world_anvil if needed
            # await update_world_anvil(character, action, response)
        else:
            # Optionally, do not send any message if no action is recognized
            logging.info("No valid action found in the message.")
            pass

        await bot.process_commands(message)

def setup(bot):
    bot.add_cog(MessageHandler(bot))