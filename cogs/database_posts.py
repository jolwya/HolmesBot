import discord
from discord.ext import commands
import database as db
from views.review_view import build_scammer_embed
from utils import is_staff


class DatabasePosts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="set_database_channel", 
        description="Set the channel where approved reports are posted via webhook (staff only)."
    )
    @discord.app_commands.describe(channel="The channel where the scammer database will post")
    async def set_database_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not await is_staff(interaction):
            return await interaction.followup.send("🔒 Staff only.", ephemeral=True)

        try:
            webhook = await channel.create_webhook(name="Scammer Database")
            await db.set_database_config(interaction.guild.id, channel.id, webhook.url)
            await interaction.followup.send(
                f"✅ Database channel set to {channel.mention}. Approved scammer reports will be published there via webhook.",
                ephemeral=True
            )
        except discord.Forbidden:
            # Fallback if bot lacks webhook permission
            await db.set_database_config(interaction.guild.id, channel.id, "")
            await interaction.followup.send(
                f"⚠️ Saved {channel.mention} as the database channel! (Note: Bot lacks 'Manage Webhooks' permission, so reports will be posted as standard bot embeds).",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error setting database channel: {e}", ephemeral=True)

    @discord.app_commands.command(
        name="lookup",
        description="Search the scammer database by Roblox or Discord username.",
    )
    @discord.app_commands.describe(query="Roblox username, Discord username, or part of a name")
    async def lookup(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        entry = await db.lookup_scammer(query.strip())
        if not entry:
            return await interaction.followup.send(
                f"✅ No scammer records found matching **{query}**.", ephemeral=True
            )

        import aiosqlite
        async with aiosqlite.connect("scambot.db") as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM reports WHERE (roblox_username = ? OR discord_username = ?) AND reviewed_by IS NOT NULL", 
                (entry["roblox_username"], entry["discord_username"])
            ) as cur:
                reports = [dict(r) for r in await cur.fetchall()]

        embed = build_scammer_embed(entry, reports)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DatabasePosts(bot))
