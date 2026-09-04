import discord
import database as db
import aiohttp
import asyncio
import re
from utils import is_staff


def extract_first_image_url(text: str) -> str | None:
    """Find the first image url in a text string to display on the embed."""
    if not text:
        return None
    # Look for common image URLs or Discord CDN image attachments
    pattern = r'(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp)[^\s]*)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Also check discord cdn links
    cdn_pattern = r'(https?://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/[^\s]+)'
    cdn_match = re.search(cdn_pattern, text, re.IGNORECASE)
    if cdn_match:
        return cdn_match.group(1)
    
    return None


def build_scammer_embed(entry: dict, reports: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"⛔ Scammer Entry: {entry['roblox_username']} | {entry['discord_username']}",
        description="This user has been reported and verified by server staff.",
        color=discord.Color.red(),
    )

    embed.add_field(name="Roblox Username", value=entry.get("roblox_username") or "N/A", inline=True)
    embed.add_field(name="Discord / Social", value=entry.get("discord_username") or "N/A", inline=True)
    embed.add_field(name="Total Verified Reports", value=str(entry.get("report_count", 1)), inline=True)

    created_at_str = entry.get("created_at") or "Recently"
    last_updated_str = entry.get("last_updated") or "Recently"

    embed.add_field(name="📅 Added to Database", value=str(created_at_str)[:19], inline=True)
    embed.add_field(name="🔄 Last Updated", value=str(last_updated_str)[:19], inline=True)

    first_image = None

    # Show reports details (up to the last 3)
    for i, r in enumerate(reports[-3:], 1):
        reporter_display = f"<@{r['reporter_id']}>" if r.get("reporter_id") else "Anonymous"
        reason_text = r.get("reason") or "No description provided."
        proof_text = r.get("proof_link") or "None"
        report_date = str(r.get("created_at") or "")[:19]

        if not first_image:
            first_image = extract_first_image_url(proof_text)

        report_value = (
            f"**Reported By:** {reporter_display}\n"
            f"**Date:** {report_date}\n"
            f"**Reason:** {reason_text[:300]}\n"
            f"**Evidence / Proof:**\n{proof_text[:400]}"
        )
        embed.add_field(
            name=f"📝 Report #{i}",
            value=report_value[:1024],
            inline=False,
        )

    if first_image:
        embed.set_image(url=first_image)

    embed.set_footer(text="Scammer Database | Use /lookup to verify users")
    return embed


async def archive_ticket(interaction: discord.Interaction, ticket_id: int, reason: str, status: str):
    ticket_channel_id = None
    import aiosqlite
    async with aiosqlite.connect("scambot.db") as db_conn:
        async with db_conn.execute("SELECT channel_id FROM tickets WHERE id = ?", (ticket_id,)) as cur:
            row = await cur.fetchone()
            if row:
                ticket_channel_id = row[0]

    if not ticket_channel_id:
        return

    channel = interaction.guild.get_channel(ticket_channel_id) if interaction.guild else None
    if not channel:
        return

    config = await db.get_guild_config(interaction.guild.id)
    archive_channel_id = config.get("archive_channel_id") if config else None
    archive_channel = interaction.guild.get_channel(archive_channel_id) if archive_channel_id else None

    # Fetch history for transcript
    history = []
    async for msg in channel.history(limit=200, oldest_first=True):
        author = f"{msg.author.name}#{msg.author.discriminator}" if msg.author.discriminator != "0" else msg.author.name
        content = msg.content or "[No Text]"
        atts = [a.url for a in msg.attachments]
        if atts:
            content += " " + " ".join(atts)
        history.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {author}: {content}")

    transcript_text = "\n".join(history)

    try:
        if archive_channel:
            import io
            file = discord.File(io.BytesIO(transcript_text.encode("utf-8")), filename=f"transcript-{channel.name}.txt")
            embed = discord.Embed(
                title=f"📁 Ticket Closed & Archived: #{channel.name}",
                description=f"**Status:** {status}\n**Handled By:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.green() if status == "Approved" else discord.Color.red()
            )
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            await archive_channel.send(embed=embed, file=file)

        # Notify channel and delete
        await channel.send("🗑️ **Ticket closed.** This channel will be deleted in **5 seconds**...")
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket closed ({status}) by {interaction.user.name}")
    except discord.Forbidden:
        await channel.send("⚠️ Bot lacks permission to manage/delete this channel or send messages to archive channel.")
    except Exception as e:
        print(f"Error archiving ticket: {e}")


class ReviewView(discord.ui.View):
    """Approve / Reject buttons posted in the ticket channel for staff."""

    def __init__(self, report_id: int, ticket_id: int):
        super().__init__(timeout=None)
        self.report_id = report_id
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="✅ Approve & Add to Database",
        style=discord.ButtonStyle.success,
        custom_id="approve_report_btn",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_staff(interaction):
            return await interaction.response.send_message("🔒 Staff only.", ephemeral=True)

        await interaction.response.defer()

        report = await db.get_report(self.report_id)
        if not report:
            return await interaction.followup.send("Report not found.", ephemeral=True)

        await db.approve_report(self.report_id, interaction.user.id)
        await db.update_ticket_status(self.ticket_id, "approved")

        # Upsert scammer entry
        entry = await db.upsert_scammer(report["roblox_username"], report["discord_username"])

        # Fetch all verified reports for this scammer
        all_reports = []
        import aiosqlite
        async with aiosqlite.connect("scambot.db") as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM reports WHERE (roblox_username = ? OR discord_username = ?) AND reviewed_by IS NOT NULL", 
                (report["roblox_username"], report["discord_username"])
            ) as cur:
                all_reports = [dict(r) for r in await cur.fetchall()]

        embed = build_scammer_embed(entry, all_reports)

        # Post to database channel via webhook or direct channel send
        config = await db.get_guild_config(interaction.guild.id)
        webhook_url = config.get("database_webhook_url") if config else None
        db_channel_id = config.get("database_channel_id") if config else None

        posted = False
        if webhook_url:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "embeds": [embed.to_dict()],
                    "username": "Scammer Database",
                    "avatar_url": interaction.client.user.display_avatar.url if interaction.client.user.display_avatar else None
                }
                try:
                    async with session.post(webhook_url, json=payload) as resp:
                        if resp.status in (200, 204):
                            posted = True
                except Exception as e:
                    print(f"Webhook send error: {e}")

        # Fallback to direct channel send if webhook didn't work
        if not posted and db_channel_id:
            db_channel = interaction.guild.get_channel(db_channel_id)
            if db_channel:
                try:
                    await db_channel.send(embed=embed)
                    posted = True
                except Exception as e:
                    print(f"Direct channel send error: {e}")

        if not posted:
            await interaction.channel.send("⚠️ No database channel/webhook configured! Use `/set_database_channel` to configure where reports are posted.")

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(
            content=f"✅ **Report Approved** by {interaction.user.mention}.",
            view=self,
        )

        await archive_ticket(interaction, self.ticket_id, f"Approved by {interaction.user.name}", "Approved")

    @discord.ui.button(
        label="❌ Reject Report",
        style=discord.ButtonStyle.danger,
        custom_id="reject_report_btn",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_staff(interaction):
            return await interaction.response.send_message("🔒 Staff only.", ephemeral=True)

        await interaction.response.defer()
        await db.update_ticket_status(self.ticket_id, "rejected")

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(
            content=f"❌ **Report Rejected** by {interaction.user.mention}.",
            view=self,
        )

        await archive_ticket(interaction, self.ticket_id, f"Rejected by {interaction.user.name}", "Rejected")
