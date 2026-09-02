import discord
from discord.ext import commands
import database as db
from config import MOD_ROLE_ID
from views.report_button import ReportButtonView

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="setup_report_button",
        description="Post the 'Report a Scam' button in this channel (mods only).",
    )
    async def setup_report_button(self, interaction: discord.Interaction):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        embed = discord.Embed(
            title="🛑 Scammer Database",
            description=(
                "Spotted a scammer? Click the button below to open a private report ticket.\n\n"
                "Your report will be reviewed by a moderator before being added to the database."
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text="Only verified reports are published.")
        await interaction.channel.send(embed=embed, view=ReportButtonView())
        await interaction.response.send_message("✅ Report button posted.", ephemeral=True)

    @discord.app_commands.command(
        name="set_archive_channel", 
        description="Set the channel where closed ticket transcripts are saved (mods only)."
    )
    async def set_archive_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        await db.set_archive_channel(interaction.guild.id, channel.id)
        
        await interaction.response.send_message(
            f"✅ When a ticket is closed, its transcript will now be saved to {channel.mention} and the ticket channel will be completely deleted.", 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
