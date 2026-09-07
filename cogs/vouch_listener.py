import discord
from discord.ext import commands
import asyncio
import database as db
import re

def contains_vouch_keyword(text: str) -> bool:
    return bool(re.search(r'\bvouch(?:es|ed|ing)?\b', text, re.IGNORECASE))

class VouchListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild or not message.channel:
            return

        channel_name = message.channel.name.lower()

        # Determine vouch channel type
        is_mm_channel = any(kw in channel_name for kw in ["middleman-vouches", "middleman_vouches", "mm-vouches", "mm_vouches", "mm-vouch", "middleman-vouch"])
        is_normal_channel = any(kw in channel_name for kw in ["vouches", "vouch"]) and not is_mm_channel

        if not (is_mm_channel or is_normal_channel):
            return

        vouch_type = "middleman" if is_mm_channel else "normal"
        reasons = []

        # Rule 1: Must contain keyword 'vouch'
        if not contains_vouch_keyword(message.content):
            reasons.append("Message must contain the keyword **vouch**.")

        # Rule 2: Must mention exactly 1 non-bot user
        user_mentions = [m for m in message.mentions if not m.bot]
        if len(user_mentions) == 0:
            reasons.append("You must **@mention** the user you are vouching for.")
        elif len(user_mentions) > 1:
            reasons.append("You can only mention **exactly 1 person** per vouch (no multi-vouching).")
        elif user_mentions[0].id == message.author.id:
            reasons.append("You cannot vouch for **yourself**.")

        # Rule 3: Normal vouches channel requires an image/attachment or image link
        if is_normal_channel:
            has_attachment = len(message.attachments) > 0
            has_image_url = bool(re.search(r'https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp)', message.content, re.IGNORECASE))
            if not (has_attachment or has_image_url):
                reasons.append("Normal vouches require an **image/screenshot proof** attachment.")

        # If any validation failed -> Delete message & send auto-deleting warning
        if reasons:
            try:
                await message.delete()
                warn = await message.channel.send(
                    f"⚠️ {message.author.mention}, your vouch message was removed:\n" +
                    "\n".join(f"• {r}" for r in reasons)
                )
                await asyncio.sleep(6)
                await warn.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            return

        # Valid vouch! Record reputation
        vouched_user = user_mentions[0]
        proof_url = message.attachments[0].url if message.attachments else None

        saved = await db.add_channel_vouch(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            voucher_id=message.author.id,
            vouched_for_id=vouched_user.id,
            vouch_type=vouch_type,
            proof_url=proof_url
        )

        if saved:
            try:
                await message.add_reaction("✅")
            except (discord.Forbidden, discord.NotFound):
                pass

    # ── Slash Commands ─────────────────────────────────────────────────────────

    @discord.app_commands.command(
        name="reputation",
        description="View a user's total reputation and vouch breakdown."
    )
    @discord.app_commands.describe(user="The user to check reputation for (default: yourself)")
    async def reputation(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        await interaction.response.defer()

        rep = await db.get_user_reputation(interaction.guild.id, target.id)

        embed = discord.Embed(
            title=f"⭐ Reputation for {target.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else None)
        embed.add_field(name="🏆 Total Reputation", value=f"**{rep['total']:,}** points", inline=False)
        embed.add_field(name="📝 Normal Channel Vouches", value=str(rep['normal']), inline=True)
        embed.add_field(name="🛡️ Middleman Vouches", value=str(rep['middleman']), inline=True)
        embed.add_field(name="⭐ Command Vouches", value=str(rep['slash']), inline=True)

        embed.set_footer(text=f"User ID: {target.id} | Scammer Database")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="leaderboard",
        description="View the reputation leaderboard for top vouched users."
    )
    @discord.app_commands.describe(
        category="Filter leaderboard type (Total, Middleman, Normal, or Command)"
    )
    @discord.app_commands.choices(category=[
        discord.app_commands.Choice(name="🏆 Total Reputation", value="total"),
        discord.app_commands.Choice(name="🛡️ Middleman Vouches", value="middleman"),
        discord.app_commands.Choice(name="📝 Normal Channel Vouches", value="normal"),
        discord.app_commands.Choice(name="⭐ Command Vouches", value="slash"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str = "total"):
        await interaction.response.defer()

        board = await db.get_reputation_leaderboard(interaction.guild.id, leaderboard_type=category, limit=10)

        category_titles = {
            "total": "🏆 Total Reputation Leaderboard",
            "middleman": "🛡️ Middleman Vouches Leaderboard",
            "normal": "📝 Normal Channel Vouches Leaderboard",
            "slash": "⭐ Command Vouches Leaderboard"
        }

        embed = discord.Embed(
            title=category_titles.get(category, "Reputation Leaderboard"),
            color=discord.Color.purple()
        )

        if not board:
            embed.description = "No vouches recorded yet for this category."
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for idx, entry in enumerate(board, 1):
                member = interaction.guild.get_member(entry["user_id"])
                user_str = member.mention if member else f"<@{entry['user_id']}>"
                prefix = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
                lines.append(f"{prefix} {user_str} — **{entry['score']:,}** points")

            embed.description = "\n".join(lines)

        embed.set_footer(text="Keep trading safely!")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(VouchListener(bot))
