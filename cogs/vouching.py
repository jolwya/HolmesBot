import discord
from discord.ext import commands
import database as db
from utils import is_staff


class Vouching(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="vouch",
        description="Vouch for a trustworthy user (proof attachment required).",
    )
    @discord.app_commands.describe(
        user="The user you want to vouch for",
        reason="Why are you vouching for them (e.g. successful cross-trade, transaction)?",
        proof="Screenshot or image proof of the successful trade/deal",
    )
    async def vouch(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        proof: discord.Attachment,
    ):
        if user.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot vouch for yourself.", ephemeral=True
            )
        if user.bot:
            return await interaction.response.send_message(
                "❌ You cannot vouch for a bot.", ephemeral=True
            )

        if not proof or not proof.url:
            return await interaction.response.send_message(
                "❌ Proof attachment is required to vouch for a member.", ephemeral=True
            )

        success = await db.add_vouch(interaction.user.id, user.id, reason.strip(), proof.url)
        if not success:
            return await interaction.response.send_message(
                f"❌ You have already vouched for {user.mention}. You can only vouch once per user.",
                ephemeral=True,
            )

        total = await db.get_vouch_total(user.id)
        embed = discord.Embed(
            title="✅ Vouch Recorded",
            description=f"{interaction.user.mention} vouched for {user.mention}!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Reason", value=reason.strip(), inline=False)
        embed.add_field(name="Proof", value=f"[Click to View Proof]({proof.url})", inline=False)
        embed.add_field(name=f"{user.display_name}'s Total Vouch Points", value=f"⭐ **{total}**", inline=True)

        if proof.content_type and proof.content_type.startswith("image/"):
            embed.set_image(url=proof.url)

        embed.set_footer(text=f"Voucher ID: {interaction.user.id}")
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="vouches",
        description="View a user's vouch list, total points, and proof.",
    )
    @discord.app_commands.describe(user="The user to look up (leave blank for yourself)")
    async def vouches(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        target = user or interaction.user
        await interaction.response.defer()

        vouch_list = await db.get_vouches(target.id)
        total = await db.get_vouch_total(target.id)

        embed = discord.Embed(
            title=f"🏅 Vouches for {target.display_name}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Total Vouch Points", value=f"⭐ **{total}**", inline=False)

        if not vouch_list:
            embed.description = "No vouches recorded yet."
        else:
            lines = []
            for v in vouch_list[:15]:
                voucher = interaction.guild.get_member(v["voucher_id"]) if interaction.guild else None
                voucher_str = voucher.mention if voucher else f"<@{v['voucher_id']}>"
                reason_str = f" — *{v['reason']}*" if v.get("reason") else ""
                proof_str = f" ([Proof]({v['proof_url']}))" if v.get("proof_url") else ""
                lines.append(f"• {voucher_str}{reason_str}{proof_str}")
            
            embed.description = "\n".join(lines)
            if len(vouch_list) > 15:
                embed.set_footer(text=f"Showing 15 of {len(vouch_list)} vouches")

        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="remove_vouch",
        description="Remove a vouch (Staff can remove any member's vouch).",
    )
    @discord.app_commands.describe(
        user="The user whose vouch should be removed",
        voucher="Staff only: The member whose vouch should be deleted (leave blank for your own)"
    )
    async def remove_vouch(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        voucher: discord.Member = None,
    ):
        await interaction.response.defer(ephemeral=True)
        staff = await is_staff(interaction)

        # If a voucher is specified and it's not the command caller, require staff permission
        if voucher and voucher.id != interaction.user.id:
            if not staff:
                return await interaction.followup.send(
                    "🔒 Only staff can remove other members' vouches.", ephemeral=True
                )
            target_voucher_id = voucher.id
            voucher_display = f"{voucher.mention}'s"
        else:
            target_voucher_id = interaction.user.id
            voucher_display = "Your"

        removed = await db.remove_vouch(vouched_for_id=user.id, voucher_id=target_voucher_id)
        if not removed:
            return await interaction.followup.send(
                f"❌ No vouch found from {voucher_display} for {user.mention}.", ephemeral=True
            )

        total = await db.get_vouch_total(user.id)
        await interaction.followup.send(
            f"✅ Successfully removed {voucher_display} vouch for {user.mention}. (New total points: **{total}**)",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="clear_all_vouches",
        description="Wipe all vouches from a user (Staff only).",
    )
    @discord.app_commands.describe(user="The user whose vouches should be completely cleared")
    async def clear_all_vouches(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not await is_staff(interaction):
            return await interaction.followup.send("🔒 Staff only.", ephemeral=True)

        count = await db.clear_all_vouches(user.id)
        if count == 0:
            return await interaction.followup.send(f"ℹ️ {user.mention} has no vouches to remove.", ephemeral=True)

        await interaction.followup.send(
            f"🧹 Successfully cleared all **{count}** vouch(es) from {user.mention}.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Vouching(bot))
