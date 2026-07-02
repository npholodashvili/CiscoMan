"""Action Cards - Unified entry point that delegates to platform-specific actions."""

# Import base classes
from actions.base import Action, Param

# Import platform-specific actions
from actions.cisco import CISCO_ACTIONS
from actions.fiberstore_fsosv2 import FSOS_ACTIONS
from actions.fiberstore_networkos import NETWORKOS_ACTIONS

# Combine all actions for backward compatibility
ACTIONS = CISCO_ACTIONS + FSOS_ACTIONS + NETWORKOS_ACTIONS

# Build lookup dictionaries
ACTIONS_BY_ID = {a.id: a for a in ACTIONS}
CATEGORIES = list(dict.fromkeys(a.category for a in ACTIONS))


def get_action(action_id: str):
    """Get an action by its ID."""
    return ACTIONS_BY_ID[action_id]


def platform_family(device_type: str) -> str:
    """Map device_type to platform family."""
    mapping = {
        "cisco_ios": "ios",
        "cisco_xe": "ios",
        "cisco_nxos": "nxos",
        "cisco_xr": "xr",
        "cisco_asa": "asa",
        "cisco_s300": "ios",
        "fiberstore_fsosv2": "fiberstore_fsosv2",
        "fiberstore_networkos": "fiberstore_networkos",
    }
    return mapping.get(device_type, "ios")


def action_visible(action: Action, device_types: set[str]) -> bool:
    """Check if an action is visible for the given device types."""
    if "all" in action.platforms:
        return True
    families = {platform_family(dt) for dt in device_types}
    return bool(families & set(action.platforms))


def filter_actions(action_list: list[Action], device_types: set[str]) -> list[Action]:
    """Filter actions to only those visible for the given device types."""
    if not device_types:
        return action_list
    return [a for a in action_list if action_visible(a, device_types)]


# Export everything needed by app.py
__all__ = [
    "Action",
    "Param",
    "ACTIONS",
    "ACTIONS_BY_ID",
    "CATEGORIES",
    "get_action",
    "platform_family",
    "action_visible",
    "filter_actions",
]