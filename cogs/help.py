import discord
from discord.ext import commands
from utils import is_staff, is_auction_manager

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Show all available bot commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        staff_access = await is_staff(interaction)
        auction_access = await is_auction_manager(interaction)

        embed = discord.Embed(
            title="🤖 Scammer Database & Auction Bot Help",
            description="Here are the commands available on this server:",
            color=discord.Color.blurple()
        )

        # Public Commands
        embed.add_field(
            name="👤 Public Member Commands",
            value=(
                "**`/lookup <query>`** - Search the database for a scammer by Roblox or Discord tag\n"
                "**`/reputation [user]`** - View a user's total reputation and vouch breakdown\n"
                "**`/leaderboard [category]`** - View top vouched users (Total, Middleman, Normal)\n"
                "**`/vouch <user> <reason> <proof>`** - Vouch for a trustworthy trader with image proof\n"
                "**`/vouches [user]`** - View a user's total vouches, history, and proofs\n"
                "**`/remove_vouch <user>`** - Remove a vouch you previously gave"
            ),
            inline=False
        )

        # Auction Commands
        if auction_access:
            embed.add_field(
                name="🔨 Auction Manager Commands",
                value=(
                    "**`/auction_create`** - Create a new Robux auction with interactive bidding & countdown\n"
                    "**`/auction_blacklist_add <user> [reason]`** - Blacklist a user from bidding\n"
                    "**`/auction_blacklist_remove <user>`** - Remove a user from auction blacklist\n"
                    "**`/set_auction_manager_role <@role>`** - Authorize an Auction Manager role (Admin only)"
                ),
                inline=False
            )

        # Staff Commands
        if staff_access:
            embed.add_field(
                name="🛡️ Staff Ticket & Moderation Commands",
                value=(
                    "**`/setup_report_button`** - Post the 'Report a Scam' button in the current channel\n"
                    "**`/set_database_channel <#channel>`** - Set channel where approved reports are published\n"
                    "**`/set_archive_channel <#channel>`** - Set channel where closed ticket transcripts are saved\n"
                    "**`/add_staff_role <@role>`** - Authorize a role to review tickets & manage bot (Admin only)\n"
                    "**`/remove_staff_role <@role>`** - Remove staff authorization from a role (Admin only)\n"
                    "**`/list_staff_roles`** - View all currently authorized staff roles\n"
                    "**`/remove_vouch <user> [voucher]`** - Delete a specific fake or illegitimate vouch\n"
                    "**`/clear_all_vouches <user>`** - Wipe all vouches from an account"
                ),
                inline=False
            )

        embed.set_footer(text="Use buttons in channels to interact with tickets and auctions.")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
