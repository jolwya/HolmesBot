import discord
from discord.ext import commands
from utils import is_staff

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Show all available bot commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        staff_access = await is_staff(interaction)

        embed = discord.Embed(
            title="🤖 Scammer Database Bot Help",
            description="Here are the commands available on this server:",
            color=discord.Color.blurple()
        )

        # Public Commands
        embed.add_field(
            name="👤 Public Member Commands",
            value=(
                "**`/lookup <query>`** - Search the database for a scammer by Roblox or Discord tag\n"
                "**`/vouch <user> <reason>`** - Vouch for a trustworthy trader/member\n"
                "**`/vouches [user]`** - View a user's total vouches and vouch history\n"
                "**`/remove_vouch <user>`** - Remove a vouch you previously gave"
            ),
            inline=False
        )

        # Staff Commands
        if staff_access:
            embed.add_field(
                name="🛡️ Staff Ticket & Setup Commands",
                value=(
                    "**`/setup_report_button`** - Post the 'Report a Scam' button in the current channel\n"
                    "**`/set_database_channel <#channel>`** - Set channel where approved reports are published\n"
                    "**`/set_archive_channel <#channel>`** - Set channel where closed ticket transcripts are saved\n"
                    "**`/add_staff_role <@role>`** - Authorize a role to review tickets & manage bot (Admin only)\n"
                    "**`/remove_staff_role <@role>`** - Remove staff authorization from a role (Admin only)\n"
                    "**`/list_staff_roles`** - View all currently authorized staff roles"
                ),
                inline=False
            )
        else:
            embed.set_footer(text="Staff commands are hidden because you do not have staff permissions.")

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
