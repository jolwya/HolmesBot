import discord
from config import TICKETS_CATEGORY_ID, MOD_ROLE_ID
import database as db


class ReportButtonView(discord.ui.View):
    """Persistent 'Report a Scam' button. Re-registered on every startup."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🚨 Report a Scam",
        style=discord.ButtonStyle.danger,
        custom_id="report_scam_btn",
    )
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKETS_CATEGORY_ID)
        mod_role = guild.get_role(MOD_ROLE_ID)

        if not category:
            return await interaction.response.send_message(
                "⚠️ Ticket category not configured. Ask an admin to check `TICKETS_CATEGORY_ID`.",
                ephemeral=True,
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True
            ),
        }
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )

        ticket_channel = await guild.create_text_channel(
            name=f"report-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Scam report by {interaction.user} ({interaction.user.id})",
        )

        ticket_id = await db.create_ticket(ticket_channel.id, interaction.user.id)

        from views.report_modal import TemplateButtonView

        embed = discord.Embed(
            title="📋 Scam Report Ticket",
            description=(
                f"Hi {interaction.user.mention}! Click **Fill Out Template** below to submit your report.\n\n"
                "You can also **attach screenshots or evidence** directly in this channel."
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        await ticket_channel.send(embed=embed, view=TemplateButtonView(ticket_id))
        await interaction.response.send_message(
            f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True
        )
