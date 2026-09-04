import discord
from discord.ext import commands
import database as db
from views.report_button import ReportButtonView
from utils import is_staff


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="setup_report_button",
        description="Post the 'Report a Scam' button in this channel (staff only).",
    )
    async def setup_report_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_staff(interaction):
            return await interaction.followup.send("🔒 Staff only.", ephemeral=True)

        embed = discord.Embed(
            title="🛑 Scammer Database & Report System",
            description=(
                "Spotted a scammer? Click the button below to open a private report ticket.\n\n"
                "**Before reporting:**\n"
                "• Have your evidence ready (screenshots, transaction links, chat logs).\n"
                "• All reports are reviewed and verified by staff before being published."
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text="Only verified reports are published to the database.")
        
        if interaction.channel:
            await interaction.channel.send(embed=embed, view=ReportButtonView())
            await interaction.followup.send("✅ Report button posted.", ephemeral=True)

    @discord.app_commands.command(
        name="set_archive_channel", 
        description="Set the channel where closed ticket transcripts are saved (staff only)."
    )
    async def set_archive_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not await is_staff(interaction):
            return await interaction.followup.send("🔒 Staff only.", ephemeral=True)

        try:
            await db.set_archive_channel(interaction.guild.id, channel.id)
            await interaction.followup.send(
                f"✅ Ticket archive channel set to {channel.mention}. When tickets are closed, their transcripts will be saved there and the ticket channels will be deleted.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error setting archive channel: {e}", ephemeral=True)

    @discord.app_commands.command(
        name="add_staff_role",
        description="Authorize a role to handle report tickets and configure the bot (Admin only)."
    )
    @discord.app_commands.describe(role="The role to authorize as staff")
    async def add_staff_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        # Only server admins or owner can configure staff roles
        if not (interaction.user.id == interaction.guild.owner_id or (getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator)):
            return await interaction.followup.send("🔒 Only server Administrators can add staff roles.", ephemeral=True)

        await db.add_staff_role(interaction.guild.id, role.id)
        await interaction.followup.send(f"✅ Role {role.mention} is now authorized as staff.", ephemeral=True)

    @discord.app_commands.command(
        name="remove_staff_role",
        description="Remove a role from authorized staff (Admin only)."
    )
    @discord.app_commands.describe(role="The role to remove")
    async def remove_staff_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        if not (interaction.user.id == interaction.guild.owner_id or (getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator)):
            return await interaction.followup.send("🔒 Only server Administrators can remove staff roles.", ephemeral=True)

        await db.remove_staff_role(interaction.guild.id, role.id)
        await interaction.followup.send(f"✅ Role {role.mention} has been removed from staff roles.", ephemeral=True)

    @discord.app_commands.command(
        name="list_staff_roles",
        description="View all roles authorized to handle tickets and moderation."
    )
    async def list_staff_roles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_ids = await db.get_staff_roles(interaction.guild.id)
        if not role_ids:
            return await interaction.followup.send("ℹ️ No custom staff roles configured yet. Anyone with Administrator permission has full access.", ephemeral=True)

        lines = []
        for rid in role_ids:
            role = interaction.guild.get_role(rid)
            lines.append(role.mention if role else f"`{rid}` (Deleted Role)")

        embed = discord.Embed(
            title="🛡️ Authorized Staff Roles",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
