import discord
from discord.ext import commands
import database as db
from views.review_view import build_scammer_embed
from config import MOD_ROLE_ID

class DatabasePosts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="set_database_channel", 
        description="Set the channel where approved reports are posted via webhook (mods only)."
    )
    async def set_database_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        try:
            webhook = await channel.create_webhook(name="Scammer Database")
            await db.set_database_config(interaction.guild.id, channel.id, webhook.url)
            await interaction.followup.send(
                f"✅ Database channel set to {channel.mention}. Approved reports will be posted there automatically."
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have 'Manage Webhooks' permission in that channel.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    @discord.app_commands.command(
        name="lookup",
        description="Look up a user in the scammer database.",
    )
    @discord.app_commands.describe(query="Roblox username, Discord username, or part of a name")
    async def lookup(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        entry = await db.lookup_scammer(query)
        if not entry:
            return await interaction.followup.send(
                f"✅ No records found for **{query}**.", ephemeral=True
            )

        import aiosqlite
        async with aiosqlite.connect("scambot.db") as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM reports WHERE roblox_username = ? OR discord_username = ?", 
                (entry["roblox_username"], entry["discord_username"])
            ) as cur:
                reports = [dict(r) for r in await cur.fetchall()]

        embed = build_scammer_embed(entry, reports)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DatabasePosts(bot))
