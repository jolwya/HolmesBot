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
    )
    discord_user = discord.ui.TextInput(
        label="Discord / Social Media Username",
        placeholder="e.g. BadActor#1234",
        max_length=100,
    )
    discord_id = discord.ui.TextInput(
        label="Discord User ID (Optional)",
        placeholder="e.g. 123456789012345678",
        required=False,
        max_length=100,
    )
    proof = discord.ui.TextInput(
        label="Proof (Link or upload in channel first)",
        style=discord.TextStyle.paragraph,
        placeholder="Link, or leave empty if you attached images in the channel.",
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
        async for msg in interaction.channel.history(limit=50):
            for att in msg.attachments:
                attachments.append(att.url)

        proof_text = self.proof.value.strip()
        if attachments:
            proof_text += "\n\n**Attachments found in ticket:**\n" + "\n".join(attachments)

        if not proof_text.strip():
            return await interaction.followup.send(
                "❌ You must either provide a link or upload an image in the channel first.",
                ephemeral=True
            )

        report_id = await db.save_report(
            ticket_id=self.ticket_id,
            roblox=self.roblox.value,
            discord_user=self.discord_user.value,
            discord_id=self.discord_id.value or "Not provided",
            proof=self.proof.value,
        )
        await db.update_ticket_status(self.ticket_id, "awaiting_review")

        # Post review embed WITH approve/reject buttons directly in the ticket channel
        from views.review_view import ReviewView

        embed = discord.Embed(
            title="🔍 Scam Report — Pending Mod Review",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Reported by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Roblox Username", value=self.roblox.value, inline=True)
        embed.add_field(name="Discord Username", value=self.discord_user.value, inline=True)
        embed.add_field(name="Discord ID", value=self.discord_id.value or "N/A", inline=True)
        embed.add_field(name="Proof", value=self.proof.value, inline=False)
        embed.set_footer(text=f"Report ID: {report_id} | Ticket ID: {self.ticket_id} — A mod will review and close this ticket.")

        await interaction.channel.send(
            "📋 **Template submitted!** A moderator will review and approve or reject below.",
            embed=embed,
            view=ReviewView(report_id, self.ticket_id),
        )
