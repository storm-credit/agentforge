from dataclasses import dataclass

from fastapi import Header


@dataclass(frozen=True)
class Principal:
    user_id: str
    department: str
    roles: tuple[str, ...]


def get_principal(
    user_id: str = Header(default="local-user", alias="X-Agent-Forge-User"),
    department: str = Header(default="Sandbox", alias="X-Agent-Forge-Department"),
    roles: str = Header(default="developer", alias="X-Agent-Forge-Roles"),
) -> Principal:
    parsed_roles = tuple(role.strip() for role in roles.split(",") if role.strip())
    return Principal(user_id=user_id, department=department, roles=parsed_roles)

