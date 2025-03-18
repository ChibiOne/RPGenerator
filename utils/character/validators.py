import re
from typing import Tuple, Dict
from .constants import ABILITY_SCORE_COSTS, POINT_BUY_TOTAL

def validate_character_name(name: str) -> Tuple[bool, str]:
    """Validates a character name.
    
    Args:
        name (str): The character name to validate
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not name:
        return False, "Name cannot be empty"
    if len(name) < 2:
        return False, "Name must be at least 2 characters long"
    if len(name) > 32:
        return False, "Name must be no longer than 32 characters"
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9 -]*$', name):
        return False, "Name must start with a letter and contain only letters, numbers, spaces, and hyphens"
    return True, ""

def calculate_score_cost(score: int) -> int:
    """Returns the point cost for a given ability score based on the point-buy system.
    
    Args:
        score (int): The ability score
        
    Returns:
        int: The point cost
        
    Raises:
        ValueError: If the score is not between 8 and 15 inclusive
    """
    if score not in ABILITY_SCORE_COSTS:
        raise ValueError(f"Invalid ability score: {score}. Must be between 8 and 15.")
    return ABILITY_SCORE_COSTS[score]

def is_valid_point_allocation(allocation: Dict[str, int]) -> Tuple[bool, str]:
    """Validates if the total points spent/gained in the allocation meet the point-buy criteria.
    
    Args:
        allocation (Dict[str, int]): A dictionary of ability scores
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
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

def validate_ability_scores(scores: Dict[str, int]) -> Tuple[bool, str]:
    """Validates ability scores based on point-buy rules.
    
    Args:
        scores (Dict[str, int]): Dictionary of ability scores
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not all(isinstance(score, int) for score in scores.values()):
        return False, "All ability scores must be integers"
    
    for ability, score in scores.items():
        if score < 8 or score > 15:
            return False, f"{ability} score must be between 8 and 15"
    
    valid, message = is_valid_point_allocation(scores)
    return valid, message