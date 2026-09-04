import discord
import database as db

class TemplateButtonView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="📝 Fill Out Template", style=discord.ButtonStyle.primary, custom_id="open_report_modal_btn")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal(self.ticket_id))


class ReportModal(discord.ui.Modal, title="Scam Report"):
    roblox = discord.ui.TextInput(
        label="Roblox Username",
        placeholder="e.g. BadActor123",
        max_length=100,
        required=True,
    )
    discord_user = discord.ui.TextInput(
        label="Discord / Social Media Username",
        placeholder="e.g. BadActor#1234 or @badactor",
        max_length=100,
        required=True,
    )
    discord_id = discord.ui.TextInput(
        label="Discord User ID (Optional)",
        placeholder="e.g. 123456789012345678",
        required=False,
        max_length=100,
    )
    reason = discord.ui.TextInput(
        label="Reason for Report",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the scam in detail (what happened, trade details, etc.)",
        required=True,
        max_length=1000,
    )
    proof = discord.ui.TextInput(
        label="Proof (Link or upload in channel first)",
        style=discord.TextStyle.paragraph,
        placeholder="Paste links here, or leave blank if you attached files in this channel.",
        required=False,
        max_length=1000,
    )

    def __init__(self, ticket_id: int):
        super().__init__()
        self.ticket_id = ticket_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Scrape channel for attachments
        attachments = []
        if interaction.channel:
            async for msg in interaction.channel.history(limit=50):
                for att in msg.attachments:
                    attachments.append(att.url)

        proof_text = self.proof.value.strip()
        if attachments:
            attachment_lines = "\n".join(attachments)
            if proof_text:
                proof_text = f"{proof_text}\n\n**Uploaded Attachments:**\n{attachment_lines}"
            else:
                proof_text = f"**Uploaded Attachments:**\n{attachment_lines}"

        if not proof_text.strip():
            return await interaction.followup.send(
                "❌ Please provide proof: either paste links in the modal or upload images/videos into this channel first.",
                ephemeral=True
            )

        report_id = await db.save_report(
            ticket_id=self.ticket_id,
            reporter_id=interaction.user.id,
            roblox=self.roblox.value.strip(),
            discord_user=self.discord_user.value.strip(),
            discord_id=self.discord_id.value.strip() or "Not provided",
            reason=self.reason.value.strip(),
            proof=proof_text,
        )
        await db.update_ticket_status(self.ticket_id, "awaiting_review")

        # Post review embed WITH approve/reject buttons directly in the ticket channel
        from views.review_view import ReviewView

        embed = discord.Embed(
            title="🔍 Scam Report — Pending Staff Review",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Reported By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Roblox Username", value=self.roblox.value.strip(), inline=True)
        embed.add_field(name="Discord Username", value=self.discord_user.value.strip(), inline=True)
        embed.add_field(name="Discord ID", value=self.discord_id.value.strip() or "N/A", inline=True)
        embed.add_field(name="Reason", value=self.reason.value.strip(), inline=False)
        embed.add_field(name="Proof", value=proof_text[:1024], inline=False)
        embed.set_footer(text=f"Report ID: {report_id} | Ticket ID: {self.ticket_id} — Staff will review below.")

        if interaction.channel:
            await interaction.channel.send(
                "📋 **Template submitted!** Staff will review and approve or reject below.",
                embed=embed,
                view=ReviewView(report_id, self.ticket_id),
            )
