import discord
import database as db
from config import MOD_ROLE_ID

async def is_staff(interaction: discord.Interaction) -> bool:
    """Check if the user is a staff member or administrator."""
    if not interaction.guild:
        return False

    # Server owner is always staff
    if interaction.user.id == interaction.guild.owner_id:
        return True

    # Anyone with Administrator permission is always staff
    if getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator:
        return True

    user_role_ids = [r.id for r in getattr(interaction.user, "roles", [])]

    # Check configured staff roles in database
    staff_role_ids = await db.get_staff_roles(interaction.guild.id)
    if any(r_id in user_role_ids for r_id in staff_role_ids):
        return True

    # Fallback to MOD_ROLE_ID from env if configured
    if MOD_ROLE_ID and MOD_ROLE_ID in user_role_ids:
        return True

    return False
