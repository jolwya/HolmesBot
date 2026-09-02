import discord
import database as db
import aiohttp
from config import MOD_ROLE_ID


def build_scammer_embed(entry: dict, reports: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"⛔ Scammer: {entry['roblox_username']} / {entry['discord_username']}",
        color=discord.Color.red(),
    )
    embed.add_field(name="Total Reports", value=str(entry["report_count"]), inline=True)
    embed.add_field(name="Last Updated", value=entry["last_updated"], inline=True)

    for i, r in enumerate(reports[-3:], 1):  # show last 3 reports
        embed.add_field(
            name=f"Report #{i}",
            value=(
                f"**Roblox:** {r['roblox_username']}\n"
                f"**Discord:** {r['discord_username']} ({r['discord_id']})\n"
                f"**Proof:** {r['proof_link']}"
            ),
            inline=False,
        )
    embed.set_footer(text="Scammer Database | Use /lookup to search")
    return embed


async def archive_ticket(interaction: discord.Interaction, ticket_id: int, reason: str):
    import aiosqlite
    ticket_channel_id = None
    async with aiosqlite.connect("scambot.db") as db_conn:
        async with db_conn.execute("SELECT channel_id FROM tickets WHERE id = ?", (ticket_id,)) as cur:
            row = await cur.fetchone()
            if row:
                ticket_channel_id = row[0]
            
    if not ticket_channel_id:
        return
        
    channel = interaction.guild.get_channel(ticket_channel_id)
    if not channel:
        return

    config = await db.get_guild_config(interaction.guild.id)
    archive_channel_id = config.get("archive_channel_id") if config else None
    archive_channel = interaction.guild.get_channel(archive_channel_id) if archive_channel_id else None

    # Fetch history for transcript
    history = []
    async for msg in channel.history(limit=100, oldest_first=True):
        author = msg.author.name
        content = msg.content or "[No Text]"
        atts = [a.url for a in msg.attachments]
        if atts: content += " " + " ".join(atts)
        history.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {author}: {content}")
    
    transcript_text = "\n".join(history)
    
    try:
        if archive_channel:
            import io
            file = discord.File(io.BytesIO(transcript_text.encode('utf-8')), filename=f"transcript-{channel.name}.txt")
            embed = discord.Embed(
                title=f"📁 Ticket Closed: #{channel.name}",
                description=f"Status: **{reason}**",
                color=discord.Color.light_grey()
            )
            await archive_channel.send(embed=embed, file=file)
        
        # Delete the channel regardless of whether archive channel is set
        await channel.delete(reason=reason)
    except discord.Forbidden:
        pass


class ReviewView(discord.ui.View):
    """Persistent Approve / Reject buttons posted in the mod review channel."""

    def __init__(self, report_id: int, ticket_id: int):
        super().__init__(timeout=None)
        self.report_id = report_id
        self.ticket_id = ticket_id

    def _is_mod(self, interaction: discord.Interaction) -> bool:
        return any(r.id == MOD_ROLE_ID for r in interaction.user.roles)

    @discord.ui.button(
        label="✅ Approve",
        style=discord.ButtonStyle.success,
        custom_id="approve_report_btn",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_mod(interaction):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        await interaction.response.defer()

        report = await db.get_report(self.report_id)
        if not report:
            return await interaction.followup.send("Report not found.", ephemeral=True)

        await db.approve_report(self.report_id, interaction.user.id)
        await db.update_ticket_status(self.ticket_id, "approved")

        # Upsert scammer entry
        entry = await db.upsert_scammer(report["roblox_username"], report["discord_username"])

        # Get all reports for this scammer to build embed
        all_reports = []
        import aiosqlite
        async with aiosqlite.connect("scambot.db") as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM reports WHERE roblox_username = ? OR discord_username = ?", 
                (report["roblox_username"], report["discord_username"])
            ) as cur:
                all_reports = [dict(r) for r in await cur.fetchall()]

        embed = build_scammer_embed(entry, all_reports)
        
        # Post to webhook
        config = await db.get_guild_config(interaction.guild.id)
        webhook_url = config.get("database_webhook_url") if config else None

        if webhook_url:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "embeds": [embed.to_dict()], 
                    "username": "Scammer Database", 
                    "avatar_url": interaction.client.user.display_avatar.url if interaction.client.user.display_avatar else None
                }
                try:
                    await session.post(webhook_url, json=payload)
                except Exception as e:
                    await interaction.channel.send(f"⚠️ Failed to post to database webhook: {e}")
        else:
            await interaction.channel.send("⚠️ No database webhook configured! Use `/set_database_channel`.")

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(
            content=f"✅ Approved by {interaction.user.mention}",
            view=self,
        )

        await interaction.channel.send("✅ Report approved and published. Archiving ticket...")
        await archive_ticket(interaction, self.ticket_id, f"Approved by {interaction.user.name}")

    @discord.ui.button(
        label="❌ Reject",
        style=discord.ButtonStyle.danger,
        custom_id="reject_report_btn",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_mod(interaction):
            return await interaction.response.send_message("🔒 Mods only.", ephemeral=True)

        await interaction.response.defer()
        await db.update_ticket_status(self.ticket_id, "rejected")

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(
            content=f"❌ Rejected by {interaction.user.mention}",
            view=self,
        )

        await interaction.channel.send("❌ Report rejected. Archiving ticket...")
        await archive_ticket(interaction, self.ticket_id, f"Rejected by {interaction.user.name}")
