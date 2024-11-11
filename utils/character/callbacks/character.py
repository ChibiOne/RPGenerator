async def gender_callback(dropdown, interaction, user_id):
    """
    Callback for gender selection.
    """
    try:
        session = interaction.client.session_manager.get_session(user_id)
        selected_gender = dropdown.values[0]
        character_creation_sessions[user_id]['Gender'] = selected_gender
        logging.info(f"User {user_id} selected gender: {selected_gender}")

        if not session:
            await interaction.response.send_message(
                "Session expired. Please start character creation again.",
                ephemeral=True
            )
            return

        # Get starting equipment
        equipment, inventory_items = interaction.client.equipment_manager.get_starting_equipment(selected_class)

        if not equipment:
            await interaction.response.send_message(
                "Error loading class equipment. Please try again.",
                ephemeral=True
            )
            return

        # Proceed to pronouns selection
        await interaction.response.edit_message(
            content=f"Gender set to **{selected_gender}**! Please select your pronouns:",
            view=PronounsSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in gender_callback for user {user_id}: {e}")

async def pronouns_callback(dropdown, interaction, user_id):
    """
    Callback for pronouns selection.
    """
    try:
        session = interaction.client.session_manager.get_session(user_id)
        selected_pronouns = dropdown.values[0]
        session.pronouns = selected_pronouns
        logging.info(f"User {user_id} selected pronouns: {selected_pronouns}")

        # Proceed to description input using a modal
        await interaction.response.send_modal(DescriptionModal(user_id))
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in pronouns_callback for user {user_id}: {e}")

async def species_callback(dropdown, interaction, user_id):
    """
    Callback for species selection.
    """
    try:
        session = interaction.client.session_manager.get_session(user_id)
        selected_species = dropdown.values[0]
        session.species = selected_species
        logging.info(f"User {user_id} selected species: {selected_species}")

        # Proceed to class selection
        await interaction.response.edit_message(
            content=f"Species set to **{selected_species}**! Please select a class:",
            view=ClassSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in species_callback for user {user_id}: {e}")

async def class_callback(dropdown, interaction, user_id):
    try:
        session = interaction.client.session_manager.get_session(user_id)
        selected_class = dropdown.values[0]
        session.char_class = selected_class
       
        # Initialize equipment as a complete dictionary with all slots
        equipment = {
            'Armor': None,
            'Left_Hand': None,
            'Right_Hand': None,
            'Belt_Slots': [None] * 4,
            'Back': None,
            'Magic_Slots': [None] * 3
        }
       
        def get_item_safely(item_name):
            """Helper function to safely get and convert items"""
            logging.info(f"Attempting to get item: {item_name}")
            item = items.get(item_name)
            if not item:
                logging.warning(f"Could not find item: {item_name}")
                return None
            try:
                logging.info(f"Retrieved item type: {type(item)}")
                if isinstance(item, dict):
                    logging.info(f"Converting dict to Item: {item}")
                    return Item.from_dict(item)
                if hasattr(item, 'to_dict'):
                    logging.info("Item already has to_dict method")
                    return item
                logging.warning(f"Unknown item type for {item_name}: {type(item)}")
                return None
            except Exception as e:
                logging.error(f"Error converting item {item_name}: {e}")
                return None
            
        # Add class-specific equipment using loaded items
        if selected_class == "Warrior":
            equipment.update({
                'Right_Hand': get_item_safely("Longsword"),
                'Left_Hand': get_item_safely("Wooden Shield"),
                'Armor': get_item_safely("Ringmail Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch")
            ]
        elif selected_class == "Mage":
            equipment.update({
                'Right_Hand': get_item_safely("Staff"),
                'Left_Hand': get_item_safely("Dagger"),
                'Armor': get_item_safely("Robes")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Component Pouch")
            ]
        elif selected_class == "Rogue":
            equipment.update({
                'Right_Hand': get_item_safely("Dagger"),
                'Left_Hand': get_item_safely("Dagger"),
                'Armor': get_item_safely("Leather Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Thieves Tools")
            ]
        elif selected_class == "Cleric":
            equipment.update({
                'Right_Hand': get_item_safely("Mace"),
                'Left_Hand': get_item_safely("Wooden Shield"),
                'Armor': get_item_safely("Studded Leather Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Holy Symbol")
            ]

        # Log any missing items
        for slot, item in equipment.items():
            if item is None and slot not in ['Belt_Slots', 'Back', 'Magic_Slots']:
                logging.warning(f"Missing equipment item for slot {slot} in class {selected_class}")
       
        # Convert inventory list to dictionary and validate
        inventory = {}
        for i, item in enumerate(inventory_items):
            if item is not None:
                if isinstance(item, Item):
                    inventory[str(i)] = item
                    logging.info(f"Added inventory item {i}: {type(item)}")
                else:
                    logging.warning(f"Invalid inventory item type at index {i}: {type(item)}")

        # Validate before updating session
        logging.info(f"Final equipment structure: {equipment}")
        logging.info(f"Final inventory structure: {inventory}")
        
        # Update the session data
        character_creation_sessions[user_id]['Equipment'] = equipment
        session.equipment = equipment = inventory if isinstance(inventory, dict) else {}
        
        # Verify the session data
        session.equipment = equipment
        session_inventory = character_creation_sessions[user_id].get('Inventory', {})
        
        logging.info(f"Session equipment type: {type(session_equipment)}")
        logging.info(f"Session inventory type: {type(session_inventory)}")
        
        logging.info(f"User {user_id} selected class: {selected_class} and received starting equipment")

        await start_ability_score_assignment(interaction, user_id)

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in class_callback for user {user_id}: {e}", exc_info=True)

async def gender_callback(dropdown, interaction, user_id):
    try:
        session = interaction.client.session_manager.get_session(user_id)
        selected_gender = dropdown.values[0]
        session.gender = selected_gender
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(user_id, 2)
        
        await interaction.response.edit_message(
            content=f"Please select your pronouns:",
            embed=embed,
            view=PronounsSelectionView(user_id)
        )
        
        logging.info(f"User {user_id} selected gender: {selected_gender}")
    except Exception as e:
        logging.error(f"Error in gender_callback for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred. Please try again.",
            ephemeral=True
        )
