import discord
from discord.ext import commands
from config import MOD_ROLE_ID

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Show all available bot commands.")
    async def help_command(self, interaction: discord.Interaction):
        is_mod = any(r.id == MOD_ROLE_ID for r in interaction.user.roles)
        
        embed = discord.Embed(
            title="🤖 Scammer Database Bot Help",
            description="Here are the commands you can use:",
            color=discord.Color.blurple()
        )

        # Public Commands
        embed.add_field(
            name="👤 Public Commands",
            value=(
                "**`/lookup`** - Search the database for a scammer\n"
                "**`/vouch`** - Vouch for a trustworthy user\n"
                "**`/vouches`** - View a user's vouches\n"
                "**`/remove_vouch`** - Remove your vouch from a user"
            ),
            inline=False
        )

        # Mod Commands
        if is_mod:
            embed.add_field(
                name="🛡️ Moderator Setup Commands",
                value=(
                    "**`/setup_report_button`** - Post the 'Report a Scam' button\n"
                    "**`/set_database_channel`** - Set where verified reports post\n"
                    "**`/set_archive_channel`** - Set where ticket transcripts are saved\n"
                ),
                inline=False
            )
            embed.add_field(
                name="🔗 Webhook Syncing (Cross-Server)",
                value=(
                    "**`/webhook_subscribe`** - Sync the database to another server's webhook\n"
                    "**`/webhook_unsubscribe`** - Stop syncing to that webhook\n"
                    "**`/webhook_audit`** - Check server webhooks for spoofing attempts"
                ),
                inline=False
            )
        else:
            embed.set_footer(text="Only showing commands you have permission to use.")

        # Send ephemerally so it doesn't clog the channel
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
