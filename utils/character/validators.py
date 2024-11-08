def calculate_score_cost(score):
    """
    Returns the point cost for a given ability score based on the point-buy system.
    Args:
        score (int): The ability score.
    Returns:
        int: The point cost.
    Raises:
        ValueError: If the score is not between 8 and 15 inclusive.
    """
    if score not in ABILITY_SCORE_COSTS:
        raise ValueError(f"Invalid ability score: {score}. Must be between 8 and 15.")
    return ABILITY_SCORE_COSTS[score]

def is_valid_point_allocation(allocation):
    """
    Validates if the total points spent/gained in the allocation meet the point-buy criteria.
    Args:
        allocation (dict): A dictionary of ability scores.
    Returns:
        tuple: (bool, str) indicating validity and a message.
    """
    try:
        total_cost = sum(calculate_score_cost(score) for score in allocation.values())
    except ValueError as e:
        return False, str(e)
    
    # Calculate the minimum total cost based on possible point gains from lowering scores
    max_points_gained = 2 * list(allocation.values()).count(8) + 1 * list(allocation.values()).count(9)
    min_total_cost = POINT_BUY_TOTAL - max_points_gained
    
    if total_cost > POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) exceed the allowed pool of {POINT_BUY_TOTAL}."
    elif total_cost < POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) are less than the allowed pool of {POINT_BUY_TOTAL}."

    if total_cost < min_total_cost:
        return False, f"Total points spent ({total_cost}) are too low. Ensure you spend exactly {POINT_BUY_TOTAL} points."
        for score in allocation.values():
            if score < 8 or score > 15:
                return False, f"Ability scores must be between 8 and 15. Found {score}."
    return True, "Valid allocation."