from dataclasses import dataclass

from fastapi import Header


@dataclass(frozen=True)
class Principal:
    user_id: str
    department: str
    roles: tuple[str, ...]
    groups: tuple[str, ...]
    clearance_level: str


def get_principal(
    user_id: str = Header(default="local-user", alias="X-Agent-Forge-User"),
    department: str = Header(default="Sandbox", alias="X-Agent-Forge-Department"),
    roles: str = Header(default="developer", alias="X-Agent-Forge-Roles"),
    groups: str = Header(default="all-employees", alias="X-Agent-Forge-Groups"),
    clearance_level: str = Header(default="internal", alias="X-Agent-Forge-Clearance"),
) -> Principal:
    parsed_roles = tuple(role.strip() for role in roles.split(",") if role.strip())
    parsed_groups = tuple(group.strip() for group in groups.split(",") if group.strip())
    return Principal(
        user_id=user_id,
        department=department,
        roles=parsed_roles,
        groups=parsed_groups,
        clearance_level=clearance_level,
    )
