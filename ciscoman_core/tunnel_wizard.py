"""DMVPN tunnel wizard — guided hub vs spoke setup mapped to Action Cards."""

from __future__ import annotations

from dataclasses import dataclass

import actions


@dataclass
class TunnelRole:
    id: str
    label: str
    explanation: str
    action_id: str


ROLES: list[TunnelRole] = [
    TunnelRole(
        "hub",
        "DMVPN Hub",
        "Central router with GRE multipoint tunnel, NHRP, and IPsec. Spokes register "
        "dynamically — configure this first, then deploy spokes with matching crypto.",
        "dmvpn_hub",
    ),
    TunnelRole(
        "spoke",
        "DMVPN Spoke",
        "Remote site router: GRE multipoint tunnel to the hub's public IP, protected "
        "by IPsec. Must use the same PSK, transform-set, and NHRP network-id as the hub.",
        "dmvpn_spoke",
    ),
]

ROLES_BY_ID = {r.id: r for r in ROLES}


def action_for_role(role_id: str) -> actions.Action:
    return actions.get_action(ROLES_BY_ID[role_id].action_id)


def compatible_roles(device_types: set[str]) -> list[TunnelRole]:
    """Hub/spoke actions are IOS-only."""
    if not device_types:
        return ROLES
    return [
        r for r in ROLES
        if actions.action_visible(actions.get_action(r.action_id), device_types)
    ]


def build_cli(role_id: str, values: dict) -> tuple[actions.Action, list[str]]:
    action = action_for_role(role_id)
    return action, action.render(values)
