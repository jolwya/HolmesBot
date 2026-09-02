import discord
from discord.ext import commands
import database as db


class Vouching(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="vouch",
        description="Vouch for a trustworthy user.",
    )
    @discord.app_commands.describe(
        user="The user you want to vouch for",
        reason="Why are you vouching for them?",
    )
    async def vouch(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ):
        if user.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You can't vouch for yourself.", ephemeral=True
            )
        if user.bot:
            return await interaction.response.send_message(
                "❌ You can't vouch for a bot.", ephemeral=True
            )

        success = await db.add_vouch(interaction.user.id, user.id, reason)
        if not success:
            return await interaction.response.send_message(
                f"❌ You've already vouched for {user.mention}. You can only vouch once per user.",
                ephemeral=True,
            )

        total = await db.get_vouch_total(user.id)
        embed = discord.Embed(
            title="✅ Vouch Recorded",
            description=f"{interaction.user.mention} vouched for {user.mention}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name=f"{user.display_name}'s Total Points", value=str(total), inline=True)
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="vouches",
        description="View a user's vouch list and total points.",
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
        embed.add_field(name="Total Vouch Points", value=str(total), inline=False)

        if not vouch_list:
            embed.description = "No vouches yet."
        else:
            lines = []
            for v in vouch_list[:15]:  # cap at 15 for embed length
                voucher = interaction.guild.get_member(v["voucher_id"])
                voucher_str = voucher.mention if voucher else f"<@{v['voucher_id']}>"
                reason_str = f" — *{v['reason']}*" if v["reason"] else ""
                lines.append(f"• {voucher_str}{reason_str}")
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
