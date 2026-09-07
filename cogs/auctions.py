import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import database as db
from utils import is_staff, is_auction_manager


class AuctionBidModal(discord.ui.Modal, title="Place Auction Bid"):
    bid_amount = discord.ui.TextInput(
        label="Bid Amount (Robux R$)",
        placeholder="Enter integer amount (e.g. 500)",
        required=True,
        max_length=20
    )
    anonymous = discord.ui.TextInput(
        label="Bid Anonymously? (Type 'yes' or leave blank)",
        placeholder="yes / no",
        required=False,
        max_length=10
    )

    def __init__(self, auction_id: int, min_required: int, allow_anonymous: bool):
        super().__init__()
        self.auction_id = auction_id
        self.min_required = min_required
        self.allow_anonymous = allow_anonymous
        self.bid_amount.placeholder = f"Minimum bid: R$ {min_required:,}"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check blacklist
        if await db.is_auction_blacklisted(interaction.guild.id, interaction.user.id):
            return await interaction.followup.send("❌ You are blacklisted from bidding in auctions.", ephemeral=True)

        # Validate number
        val_str = self.bid_amount.value.replace(",", "").replace("R$", "").strip()
        if not val_str.isdigit():
            return await interaction.followup.send("❌ Please enter a valid positive number for Robux.", ephemeral=True)

        amount = int(val_str)
        is_anon = self.anonymous.value.strip().lower() in ["yes", "y", "true", "1"] if self.allow_anonymous else False

        success, msg = await db.place_auction_bid(self.auction_id, interaction.user.id, amount, is_anon)
        if not success:
            return await interaction.followup.send(f"❌ {msg}", ephemeral=True)

        # Refresh auction embed in channel
        auction = await db.get_auction(self.auction_id)
        if auction and interaction.guild:
            channel = interaction.guild.get_channel(auction["channel_id"])
            if channel:
                try:
                    msg_obj = await channel.fetch_message(auction["message_id"])
                    embed = build_auction_embed(auction, interaction.guild)
                    await msg_obj.edit(embed=embed, view=AuctionView(self.auction_id))
                except Exception as e:
                    print(f"Failed to edit auction msg: {e}")

        anon_note = " (Anonymously)" if is_anon else ""
        await interaction.followup.send(f"✅ Your bid of **R$ {amount:,}**{anon_note} has been placed!", ephemeral=True)


def build_auction_embed(auction: dict, guild: discord.Guild) -> discord.Embed:
    status = auction["status"].upper()
    is_active = auction["status"] == "active"
    color = discord.Color.gold() if is_active else (discord.Color.green() if status == "ENDED" else discord.Color.red())

    title_prefix = "🔨 ACTIVE AUCTION" if is_active else f"🏁 AUCTION {status}"
    embed = discord.Embed(
        title=f"{title_prefix}: {auction['item_name']}",
        description=auction.get("description") or "No description provided.",
        color=color
    )

    embed.add_field(name="Starting Bid", value=f"R$ {auction['starting_bid']:,}", inline=True)
    embed.add_field(name="Min Increment", value=f"R$ {auction['min_increment']:,}", inline=True)
    
    # Highest bidder display
    highest_bid = auction["highest_bid"]
    bidder_id = auction.get("highest_bidder_id")
    is_anon = bool(auction.get("is_highest_anonymous"))

    if not bidder_id:
        bidder_str = "No bids yet"
    elif is_anon:
        bidder_str = "🕵️ Anonymous Bidder"
    else:
        member = guild.get_member(bidder_id)
        bidder_str = member.mention if member else f"<@{bidder_id}>"

    embed.add_field(name="Current Highest Bid", value=f"**R$ {highest_bid:,}** by {bidder_str}", inline=False)

    # Countdown timestamp
    try:
        dt = datetime.strptime(auction["end_time"], "%Y-%m-%d %H:%M:%S")
        ts = int(dt.timestamp())
        embed.add_field(name="End Time", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
    except Exception:
        embed.add_field(name="End Time", value=auction["end_time"], inline=False)

    embed.set_footer(text=f"Auction ID: {auction['id']} | Robux Bidding")
    return embed


class AuctionView(discord.ui.View):
    def __init__(self, auction_id: int):
        super().__init__(timeout=None)
        self.auction_id = auction_id

    @discord.ui.button(label="💰 Place Bid", style=discord.ButtonStyle.success, custom_id="bid_auction_btn")
    async def place_bid(self, interaction: discord.Interaction, button: discord.ui.Button):
        auction = await db.get_auction(self.auction_id)
        if not auction:
            return await interaction.response.send_message("❌ Auction not found.", ephemeral=True)
        if auction["status"] != "active":
            return await interaction.response.send_message("❌ This auction has already ended.", ephemeral=True)

        if await db.is_auction_blacklisted(interaction.guild.id, interaction.user.id):
            return await interaction.response.send_message("❌ You are blacklisted from participating in auctions.", ephemeral=True)

        min_required = auction["highest_bid"] + (auction["min_increment"] if auction["highest_bidder_id"] else 0)
        await interaction.response.send_modal(
            AuctionBidModal(self.auction_id, min_required, bool(auction["allow_anonymous"]))
        )

    @discord.ui.button(label="📜 Bid History", style=discord.ButtonStyle.secondary, custom_id="history_auction_btn")
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        bids = await db.get_auction_bid_history(self.auction_id, limit=10)
        if not bids:
            return await interaction.followup.send("ℹ️ No bids have been placed yet for this auction.", ephemeral=True)

        is_mgr = await is_auction_manager(interaction)
        lines = []
        for idx, b in enumerate(bids, 1):
            if b["is_anonymous"] and not is_mgr:
                bidder = "🕵️ Anonymous Bidder"
            else:
                mb = interaction.guild.get_member(b["bidder_id"])
                bidder = mb.mention if mb else f"<@{b['bidder_id']}>"
                if b["is_anonymous"] and is_mgr:
                    bidder += " *(Anon to public)*"

            lines.append(f"`#{idx}` {bidder} — **R$ {b['amount']:,}**")

        embed = discord.Embed(
            title=f"📜 Bid History — Auction #{self.auction_id}",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class Auctions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auction_check_loop.start()

    def cog_unload(self):
        self.auction_check_loop.cancel()

    @tasks.loop(seconds=15)
    async def auction_check_loop(self):
        active_auctions = await db.get_active_auctions()
        now = datetime.utcnow()

        for auc in active_auctions:
            try:
                dt = datetime.strptime(auc["end_time"], "%Y-%m-%d %H:%M:%S")
                if now >= dt:
                    # Mark ended
                    await db.set_auction_status(auc["id"], "ended")
                    guild = self.bot.get_guild(auc["guild_id"])
                    if guild:
                        channel = guild.get_channel(auc["channel_id"])
                        if channel:
                            try:
                                msg = await channel.fetch_message(auc["message_id"])
                                auc["status"] = "ended"
                                embed = build_auction_embed(auc, guild)
                                await msg.edit(embed=embed, view=None)

                                # Announce winner
                                if auc["highest_bidder_id"]:
                                    is_anon = bool(auc["is_highest_anonymous"])
                                    winner_str = "🕵️ Anonymous Bidder" if is_anon else f"<@{auc['highest_bidder_id']}>"
                                    announce_embed = discord.Embed(
                                        title="🎉 AUCTION CONCLUDED!",
                                        description=f"The auction for **{auc['item_name']}** has ended!\n\n"
                                                    f"🏆 **Winner:** {winner_str}\n"
                                                    f"💰 **Winning Bid:** R$ {auc['highest_bid']:,}\n"
                                                    f"👤 **Host:** <@{auc['created_by']}>",
                                        color=discord.Color.green()
                                    )
                                    await channel.send(embed=announce_embed)
                                else:
                                    await channel.send(f"🏁 Auction for **{auc['item_name']}** ended with no bids.")
                            except Exception as e:
                                print(f"Error concluding auction #{auc['id']}: {e}")
            except Exception as e:
                print(f"Error parsing auction time: {e}")

    @auction_check_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    # ── Commands ───────────────────────────────────────────────────────────────

    @discord.app_commands.command(
        name="auction_create",
        description="Create and start a new Robux auction (Auction Manager only)."
    )
    @discord.app_commands.describe(
        item_name="Name of the item or Roblox asset being auctioned",
        starting_bid="Starting Robux amount (e.g. 100)",
        min_increment="Minimum bid increment (e.g. 50)",
        duration_minutes="Duration in minutes (e.g. 60 for 1 hour, 1440 for 1 day)",
        description="Optional description/details of the item",
        allow_anonymous="Allow bidders to bid anonymously? (True/False)"
    )
    async def auction_create(
        self,
        interaction: discord.Interaction,
        item_name: str,
        starting_bid: int,
        min_increment: int,
        duration_minutes: int,
        description: str = None,
        allow_anonymous: bool = True
    ):
        await interaction.response.defer(ephemeral=True)
        if not await is_auction_manager(interaction):
            return await interaction.followup.send("🔒 Only Auction Managers or Staff can create auctions.", ephemeral=True)

        if starting_bid < 0 or min_increment < 1 or duration_minutes < 1:
            return await interaction.followup.send("❌ Invalid parameters. Starting bid >= 0, min increment >= 1, duration >= 1.", ephemeral=True)

        # Send placeholder message to get message_id
        placeholder_embed = discord.Embed(title="🔨 Creating Auction...", color=discord.Color.gold())
        msg = await interaction.channel.send(embed=placeholder_embed)

        duration_sec = duration_minutes * 60
        auction_id = await db.create_auction(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=msg.id,
            item_name=item_name.strip(),
            description=description.strip() if description else None,
            starting_bid=starting_bid,
            min_increment=min_increment,
            allow_anonymous=allow_anonymous,
            duration_seconds=duration_sec,
            created_by=interaction.user.id
        )

        auction = await db.get_auction(auction_id)
        embed = build_auction_embed(auction, interaction.guild)
        await msg.edit(embed=embed, view=AuctionView(auction_id))

        await interaction.followup.send(f"✅ Auction for **{item_name}** created in {interaction.channel.mention}!", ephemeral=True)

    @discord.app_commands.command(
        name="set_auction_manager_role",
        description="Authorize a role to manage auctions (Admin only)."
    )
    @discord.app_commands.describe(role="The role to set as Auction Manager")
    async def set_auction_manager_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        if not await is_staff(interaction):
            return await interaction.followup.send("🔒 Staff/Admin only.", ephemeral=True)

        await db.add_auction_manager_role(interaction.guild.id, role.id)
        await interaction.followup.send(f"✅ Role {role.mention} added as an Auction Manager.", ephemeral=True)

    @discord.app_commands.command(
        name="auction_blacklist_add",
        description="Blacklist a user from bidding in auctions (Auction Manager only)."
    )
    @discord.app_commands.describe(user="User to blacklist", reason="Reason for blacklist")
    async def auction_blacklist_add(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        if not await is_auction_manager(interaction):
            return await interaction.followup.send("🔒 Auction Manager only.", ephemeral=True)

        await db.add_auction_blacklist(interaction.guild.id, user.id, reason, interaction.user.id)
        await interaction.followup.send(f"🚫 {user.mention} has been blacklisted from bidding.", ephemeral=True)

    @discord.app_commands.command(
        name="auction_blacklist_remove",
        description="Remove a user from the auction blacklist (Auction Manager only)."
    )
    @discord.app_commands.describe(user="User to un-blacklist")
    async def auction_blacklist_remove(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not await is_auction_manager(interaction):
            return await interaction.followup.send("🔒 Auction Manager only.", ephemeral=True)

        removed = await db.remove_auction_blacklist(interaction.guild.id, user.id)
        if not removed:
            return await interaction.followup.send(f"ℹ️ {user.mention} is not blacklisted.", ephemeral=True)

        await interaction.followup.send(f"✅ Removed {user.mention} from the auction blacklist.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Auctions(bot))
