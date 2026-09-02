import discord
from discord.ext import commands
import database as db
from config import MOD_ROLE_ID


class Webhooks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="webhook_subscribe",
        description="Subscribe this server to the scammer database feed (mods only).",
    )
    @discord.app_commands.describe(webhook_url="The Discord webhook URL for your database channel")
    async def webhook_subscribe(self, interaction: discord.Interaction, webhook_url: str):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            return await interaction.response.send_message(
                "❌ That doesn't look like a valid Discord webhook URL.", ephemeral=True
            )

        await db.add_webhook(interaction.guild.id, webhook_url)
        await interaction.response.send_message(
            "✅ This server is now subscribed. New approved scammer entries will be synced here.",
            ephemeral=True,
        )

    @discord.app_commands.command(
        name="webhook_unsubscribe",
        description="Remove this server from the scammer database feed (mods only).",
    )
    async def webhook_unsubscribe(self, interaction: discord.Interaction):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        await db.remove_webhook(interaction.guild.id)
        await interaction.response.send_message(
            "✅ Unsubscribed from the scammer database feed.", ephemeral=True
        )

    @discord.app_commands.command(
        name="webhook_audit",
        description="List all webhooks in this server (mods only — useful for spotting spoofed webhooks).",
    )
    async def webhook_audit(self, interaction: discord.Interaction):
        if not any(r.id == MOD_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        all_webhooks = []
        for channel in interaction.guild.text_channels:
            try:
                channel_webhooks = await channel.webhooks()
                for wh in channel_webhooks:
                    all_webhooks.append((channel, wh))
            except discord.Forbidden:
                pass

        if not all_webhooks:
            return await interaction.followup.send("No webhooks found in this server.", ephemeral=True)

        embed = discord.Embed(
            title="🔗 Webhook Audit",
            color=discord.Color.blurple(),
            description=f"Found **{len(all_webhooks)}** webhook(s):",
        )
        for channel, wh in all_webhooks[:20]:
            creator = f"<@{wh.user.id}>" if wh.user else "Unknown"
            embed.add_field(
                name=f"#{channel.name}",
                value=f"**Name:** {wh.name}\n**Created by:** {creator}\n**ID:** `{wh.id}`",
                inline=True,
            )
        embed.set_footer(text="⚠️ Delete any webhooks you don't recognize.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Webhooks(bot))
