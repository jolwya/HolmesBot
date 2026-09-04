import discord
from discord.ext import commands
import database as db


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

        # Check that attachment exists
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

        # Preview image if it's an image file
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
            for v in vouch_list[:15]:  # show up to 15 vouches
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
        description="Remove your vouch from a user.",
    )
    @discord.app_commands.describe(user="The user to remove your vouch from")
    async def remove_vouch(self, interaction: discord.Interaction, user: discord.Member):
        import aiosqlite
        async with aiosqlite.connect("scambot.db") as conn:
            result = await conn.execute(
                "DELETE FROM vouches WHERE voucher_id = ? AND vouched_for_id = ?",
                (interaction.user.id, user.id),
            )
            await conn.commit()
            if result.rowcount == 0:
                return await interaction.response.send_message(
                    f"❌ You haven't vouched for {user.mention}.", ephemeral=True
                )
        await interaction.response.send_message(
            f"✅ Your vouch for {user.mention} has been removed.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Vouching(bot))
