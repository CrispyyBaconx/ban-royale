import discord
import os
import json
import asyncio
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "bot_master": int(os.getenv('BOT_MASTER_ROLE', '1400583988783091803')),
    "ban_logs": int(os.getenv('BAN_LOGS_CHANNEL', '1400615174737498132')),
    "ban_channel": int(os.getenv('BAN_CHANNEL', '1400583337176862732')),
    "ban_chance": float(os.getenv('BAN_CHANCE', '0.99')),
    "ban_delay": float(os.getenv('BAN_DELAY', '2.0')),
    "decay_mode": os.getenv('DECAY_MODE', 'false').lower() == 'true',
    "min_decay_chance": float(os.getenv('MIN_DECAY_CHANCE', '0.01')),
    "max_decay_chance": float(os.getenv('MAX_DECAY_CHANCE', '0.99')),
    "react_emoji": os.getenv('REACT_EMOJI', '✅'),
    "spectator_role": os.getenv('SPECTATOR_ROLE_NAME', 'Ban Royale Spectator')
}

class NitroButtonView(discord.ui.View):
    """Button view for claiming nitro on main game win"""
    
    def __init__(self, winner_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.winner_id = winner_id
    
    @discord.ui.button(label='🎁 Claim Nitro', style=discord.ButtonStyle.primary, emoji='🎁')
    async def claim_nitro(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only the winner can claim the nitro
        if interaction.user.id != self.winner_id:
            await interaction.response.send_message("❌ Only the winner can claim this nitro!", ephemeral=True)
            return
        
        # Load nitro link from environment variable
        nitro_link = os.getenv('MAIN_NITRO_LINK', '').strip()
        if nitro_link:
            await interaction.response.send_message(f"🎉 Congratulations! Here's your nitro: {nitro_link}", ephemeral=True)
            # Disable the button after claiming
            button.disabled = True
            button.label = "✅ Claimed!"
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.send_message("hehe u got tricked theres no nitro", ephemeral=True)

class BotRoyaleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(
                users=True, 
                roles=False,
                everyone=False
            ),
            intents=intents
        )
        
        self.remove_command('help')
        self.config = CONFIG

    async def setup_hook(self):
        """Called when the bot is starting up"""
        await self.add_cog(Main(self))
        
        command_modules = [
            'commands.basic_commands',
            'commands.utility_commands', 
            'commands.decay_commands',
            'commands.unban_commands',
            'commands.misc_commands'
        ]
        
        for module in command_modules:
            try:
                await self.load_extension(module)
                print(f"Loaded {module}")
            except Exception as e:
                print(f"Failed to load {module}: {e}")
        
        print(f"Loaded cogs successfully!")

    async def on_ready(self):
        """Called when the bot is ready"""
        print(f'{self.user} has connected to Discord!')

# Create bot instance
bot = BotRoyaleBot()

class Main(commands.Cog):
    """Main cog for Ban Royale functionality"""

    def __init__(self, bot: BotRoyaleBot) -> None:
        self.bot = bot
        self.config = self.bot.config
        self.enabled = False
        self.banned_users_file = "event_banned_users.json"
        self.session_ban_counts = {}  # Track ban counts per user per session
        self.initial_participants = {}  # Track who was in the game when it started {guild_id: set(user_ids)}

    def load_all_banned_data(self) -> dict:
        """Load all banned users data from the file"""
        try:
            with open(self.banned_users_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def load_banned_users(self, guild_id: int) -> dict:
        """Load the list of users banned during the event for a specific server"""
        all_data = self.load_all_banned_data()
        return all_data.get(str(guild_id), {})
    
    def save_banned_user(self, guild_id: int, user_id: int, username: str, banned_by: str):
        """Save a banned user to the tracking file for a specific server"""
        all_data = self.load_all_banned_data()
        guild_id_str = str(guild_id)
        user_id_str = str(user_id)
        
        if guild_id_str not in all_data:
            all_data[guild_id_str] = {}
        
        all_data[guild_id_str][user_id_str] = {
            "username": username,
            "banned_by": banned_by,
            "banned_at": datetime.now().isoformat(),
            "ban_reason": f"Ban Royale: Banned by {banned_by}"
        }
        
        with open(self.banned_users_file, 'w') as f:
            json.dump(all_data, f, indent=2)
    
    def remove_banned_user(self, guild_id: int, user_id: int):
        """Remove a user from the banned users tracking file for a specific server"""
        all_data = self.load_all_banned_data()
        guild_id_str = str(guild_id)
        user_id_str = str(user_id)
        
        if guild_id_str in all_data and user_id_str in all_data[guild_id_str]:
            del all_data[guild_id_str][user_id_str]
            
            # Clean up empty server entries
            if not all_data[guild_id_str]:
                del all_data[guild_id_str]
            
            with open(self.banned_users_file, 'w') as f:
                json.dump(all_data, f, indent=2)
            return True
        return False

    def get_effective_member_count(self, guild: discord.Guild) -> int:
        """Get the effective member count for decay calculations (excluding bots, bot masters, and those above bot role)"""
        if not guild:
            return 0
        
        effective_count = 0
        bot_master_role_id = self.config['bot_master']
        bot_member = guild.get_member(self.bot.user.id)
        bot_top_role_position = bot_member.top_role.position if bot_member else 0
        
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue
            
            # Skip users with bot master role
            if any(role.id == bot_master_role_id for role in member.roles):
                continue
            
            # Skip users with roles above the bot
            if member.top_role.position >= bot_top_role_position:
                continue
            
            effective_count += 1
        
        return effective_count
    
    def get_remaining_members(self, guild: discord.Guild) -> list[discord.Member]:
        """Get list of members who are still in the game (not banned, not bots, not bot masters, not above bot role)"""
        if not guild:
            return []
        
        banned_users = self.load_banned_users(guild.id)
        banned_user_ids = set([int(user_id) for user_id in banned_users.keys() if not user_id.startswith('_')])
        bot_master_role_id = self.config['bot_master']
        bot_member = guild.get_member(self.bot.user.id)
        bot_top_role_position = bot_member.top_role.position if bot_member else 0
        
        remaining_members = []
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue
            
            # Skip users with bot master role
            if any(role.id == bot_master_role_id for role in member.roles):
                continue
            
            # Skip users with roles above the bot
            if member.top_role.position >= bot_top_role_position:
                continue
            
            # Skip banned users
            if member.id in banned_user_ids:
                continue
                
            remaining_members.append(member)
        
        return remaining_members
    
    def get_logged_checkpoints(self, guild_id: int) -> list[int]:
        """Get the list of checkpoints already logged for a server"""
        all_data = self.load_all_banned_data()
        guild_data = all_data.get(str(guild_id), {})
        return guild_data.get("_logged_checkpoints", [])
    
    def add_logged_checkpoint(self, guild_id: int, checkpoint: int) -> None:
        """Add a checkpoint to the logged list for a server"""
        all_data = self.load_all_banned_data()
        guild_id_str = str(guild_id)
        
        if guild_id_str not in all_data:
            all_data[guild_id_str] = {}
        
        logged_checkpoints = all_data[guild_id_str].get("_logged_checkpoints", [])
        if checkpoint not in logged_checkpoints:
            logged_checkpoints.append(checkpoint)
            all_data[guild_id_str]["_logged_checkpoints"] = sorted(logged_checkpoints)
            
            with open(self.banned_users_file, 'w') as f:
                json.dump(all_data, f, indent=2)
    
    async def check_and_log_checkpoints(self, guild: discord.Guild) -> None:
        """Check if we've hit new decay checkpoints and log them"""
        if not self.config['decay_mode'] or not guild:
            return
        
        effective_count = self.get_effective_member_count(guild)
        banned_count = len(self.load_banned_users(guild.id))
        
        if effective_count <= 0:
            return
        
        progress_percentage = (banned_count / effective_count) * 100
        checkpoints = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95]
        logged_checkpoints = self.get_logged_checkpoints(guild.id)
        
        for checkpoint in checkpoints:
            if progress_percentage >= checkpoint and checkpoint not in logged_checkpoints:
                # Calculate current ban chance for this checkpoint
                current_chance = self.calculate_decay_chance(guild)
                
                # Log to ban logs channel
                log_channel = self.bot.get_channel(self.config['ban_logs'])
                if log_channel:
                    await log_channel.send(
                        f"📊 **Decay Checkpoint {checkpoint}%** reached!\n"
                        f"Progress: {banned_count}/{effective_count} banned ({progress_percentage:.1f}%)\n"
                        f"Current ban chance: **{current_chance*100:.1f}%**"
                    )
                
                # Mark this checkpoint as logged
                self.add_logged_checkpoint(guild.id, checkpoint)
    
    def calculate_decay_chance(self, guild: discord.Guild) -> float:
        """Calculate ban chance using decay mode (inverse curve)"""
        if not guild:
            return self.config['ban_chance']
        
        effective_members = self.get_effective_member_count(guild)
        banned_users = self.load_banned_users(guild.id)
        banned_count = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        
        if effective_members <= 0:
            # No valid members to calculate from, use default ban chance
            return self.config['ban_chance']
        
        # Calculate decay factor: as more people are banned, chance decreases
        # decay_factor ranges from 0 (all banned) to 1 (none banned)
        remaining_members = max(0, effective_members - banned_count)
        decay_factor = remaining_members / effective_members
        
        # Apply inverse curve: higher decay_factor = higher ban chance
        min_chance = self.config['min_decay_chance']
        max_chance = self.config['max_decay_chance']
        
        # Inverse curve: chance starts high and decreases as people are banned
        decay_chance = min_chance + (max_chance - min_chance) * decay_factor
        
        return decay_chance
    
    def get_current_ban_chance(self, guild: discord.Guild) -> float:
        """Get the current ban chance (either normal or decay mode)"""
        if self.config['decay_mode']:
            return self.calculate_decay_chance(guild)
        else:
            return self.config['ban_chance']

    def reset_game_state(self, guild_id: int) -> bool:
        """Reset all game state for a server (checkpoints and banned users)"""
        all_data = self.load_all_banned_data()
        guild_id_str = str(guild_id)
        
        # Reset session ban counts
        self.session_ban_counts.clear()
        
        # Clear initial participants tracking
        if guild_id in self.initial_participants:
            del self.initial_participants[guild_id]
        
        if guild_id_str in all_data:
            del all_data[guild_id_str]
            
            with open(self.banned_users_file, 'w') as f:
                json.dump(all_data, f, indent=2)
            return True
        return False
    
    async def get_or_create_spectator_role(self, guild: discord.Guild) -> discord.Role:
        """Get or create the spectator role for the guild"""
        spectator_role_name = self.config['spectator_role']
        
        # Check if role already exists
        for role in guild.roles:
            if role.name == spectator_role_name:
                return role
        
        # Create the role if it doesn't exist
        try:
            role = await guild.create_role(
                name=spectator_role_name,
                color=discord.Color.gray(),
                reason="Ban Royale spectator role for mid-game joiners"
            )
            print(f"📋 [CONSOLE] Created spectator role '{spectator_role_name}' in {guild.name}")
            return role
        except discord.Forbidden:
            print(f"❌ [CONSOLE] Failed to create spectator role in {guild.name} - insufficient permissions")
            return None
    
    async def clear_spectator_roles(self, guild: discord.Guild) -> None:
        """Remove spectator role from all members and delete the role"""
        spectator_role_name = self.config['spectator_role']
        
        for role in guild.roles:
            if role.name == spectator_role_name:
                # Remove role from all members who have it
                members_with_role = []
                for member in guild.members:
                    if role in member.roles:
                        members_with_role.append(member.display_name)
                        try:
                            await member.remove_roles(role, reason="Ban Royale game ended")
                        except discord.Forbidden:
                            print(f"❌ [CONSOLE] Failed to remove spectator role from {member.display_name}")
                
                # Delete the role
                try:
                    await role.delete(reason="Ban Royale game ended")
                    if members_with_role:
                        print(f"🗑️ [CONSOLE] Removed spectator role from {len(members_with_role)} members in {guild.name}")
                except discord.Forbidden:
                    print(f"❌ [CONSOLE] Failed to delete spectator role in {guild.name}")
                break
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new members joining during an active game"""
        if not self.enabled or member.bot:
            return
        
        guild = member.guild
        if guild.id not in self.initial_participants:
            return  # No game was started in this guild
        
        # Check if this member was part of the initial participants
        if member.id not in self.initial_participants[guild.id]:
            # This is a mid-game joiner, add spectator role
            spectator_role = await self.get_or_create_spectator_role(guild)
            if spectator_role:
                try:
                    await member.add_roles(spectator_role, reason="Mid-game joiner - added to spectators")
                    print(f"👀 [CONSOLE] Added spectator role to {member.display_name} (mid-game joiner) in {guild.name}")
                    
                    # Send a DM or welcome message explaining they're a spectator
                    try:
                        embed = discord.Embed(
                            title="🎭 Welcome to the Ban Royale!",
                            description=f"You joined **{guild.name}** during an active Ban Royale game.",
                            color=0x808080
                        )
                        embed.add_field(
                            name="👀 Spectator Status",
                            value="You've been assigned as a spectator since the game was already in progress.",
                            inline=False
                        )
                        embed.add_field(
                            name="🚫 Restrictions",
                            value="You cannot use `!ban` commands during this game.",
                            inline=False
                        )
                        embed.add_field(
                            name="⏰ Next Game",
                            value="You'll be able to participate when the next game starts!",
                            inline=False
                        )
                        await member.send(embed=embed)
                    except discord.Forbidden:
                        pass  # Can't send DM, that's fine
                        
                except discord.Forbidden:
                    print(f"❌ [CONSOLE] Failed to add spectator role to {member.display_name}")

    async def check_win_condition(self, guild: discord.Guild) -> bool:
        """Check if win condition is met and handle game end"""
        if not self.enabled or not guild:
            return False
        
        effective_count = self.get_effective_member_count(guild)
        banned_users = self.load_banned_users(guild.id)
        banned_count = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        remaining_members_list = self.get_remaining_members(guild)
        remaining_count = len(remaining_members_list)
        
        if remaining_count <= 1:
            # Win condition met! Disable the bot but preserve game state
            self.enabled = False
            
            # Console log
            if remaining_count == 1:
                winner = remaining_members_list[0]
                print(f"🏆 [CONSOLE] Ban Royale WIN CONDITION met in {guild.name} - Winner: {winner.name}")
            else:
                print(f"💀 [CONSOLE] Ban Royale TOTAL ELIMINATION in {guild.name} - everyone banned!")
            
            # Get both channels
            log_channel = self.bot.get_channel(self.config['ban_logs'])
            ban_channel = self.bot.get_channel(self.config['ban_channel'])
            
            if remaining_count == 1:
                winner = remaining_members_list[0]
                win_embed = discord.Embed(
                    title="🏆 GAME OVER - We Have a Winner! 🏆",
                    description=f"**The Ban Royale has concluded with a victor!**\n\n🎉 **{winner.mention} is the CHAMPION!** 🎉",
                    color=0xffd700  # Gold color
                )
                win_embed.add_field(
                    name="🎯 Final Result",
                    value=f"Only **1 participant** remains out of **{effective_count}** original members!",
                    inline=False
                )
                win_embed.add_field(
                    name="🔴 Bot Status",
                    value="Ban Royale has been **disabled**",
                    inline=True
                )
                win_embed.add_field(
                    name="🔧 Next Steps",
                    value="Use `!endgame` to unban all participants and reset for the next event",
                    inline=True
                )
                win_embed.set_footer(text=f"🎉 Congratulations {winner.display_name}!")
                
                # Check if nitro is available or if we should show the fake button
                nitro_link = os.getenv('MAIN_NITRO_LINK', '').strip()
                view = None
                if nitro_link or True:  # Always show button, let the interaction handle the logic
                    view = NitroButtonView(winner.id)
                
                # Send to both channels
                if log_channel:
                    await log_channel.send(embed=win_embed, view=view)
                if ban_channel:
                    await ban_channel.send(embed=win_embed, view=view)
            else:
                elimination_embed = discord.Embed(
                    title="🏁 GAME OVER - Total Elimination! 🏁",
                    description="**Every participant has been eliminated!**",
                    color=0x8b0000  # Dark red color
                )
                elimination_embed.add_field(
                    name="💀 Final Result",
                    value=f"All **{effective_count}** participants have been banned!",
                    inline=False
                )
                elimination_embed.add_field(
                    name="🔴 Bot Status",
                    value="Ban Royale has been **disabled**",
                    inline=True
                )
                elimination_embed.add_field(
                    name="🔧 Next Steps",
                    value="Use `!endgame` to unban all participants and reset for the next event",
                    inline=True
                )
                elimination_embed.set_footer(text="💀 No survivors remain...")
                
                # Send to both channels
                if log_channel:
                    await log_channel.send(embed=elimination_embed)
                if ban_channel:
                    await ban_channel.send(embed=elimination_embed)
            
            return True
        
        return False

    def get_progress_increment(self, total_users: int) -> int:
        """Calculate appropriate progress update increment based on total users"""
        if total_users <= 10:
            return 1  # Update every user
        elif total_users <= 50:
            return 5  # Update every 5 users
        elif total_users <= 100:
            return 10  # Update every 10 users
        elif total_users <= 200:
            return 20  # Update every 20 users
        else:
            return max(25, total_users // 10)  # Update every 25 users or 10% of total, whichever is larger
    
    async def perform_mass_unban(self, ctx: commands.Context, banned_users: dict) -> tuple[int, int]:
        """Helper function to perform mass unban with progress tracking"""
        # Count only actual user IDs (exclude special keys that start with underscore)
        total_users = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        unbanned_count = 0
        failed_count = 0
        processed_count = 0
        
        # Calculate progress increment based on total users
        progress_increment = self.get_progress_increment(total_users)
        
        # Send initial progress message
        progress_msg = await ctx.send(f"Unbanning {total_users} users... Progress: 0/{total_users} processed...")
        
        banned_users_list = list(banned_users.items())
        
        for i, (user_id_str, user_info) in enumerate(banned_users_list):
            # Skip special keys that start with underscore (like '_logged_checkpoints')
            if user_id_str.startswith('_'):
                continue
            user_id = int(user_id_str)
            processed_count += 1
            
            retry_count = 0
            max_retries = 3
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    ban_entry = await ctx.guild.fetch_ban(discord.Object(id=user_id))
                    await ctx.guild.unban(ban_entry.user, reason=f"Game ended by {ctx.author.name}")
                    self.remove_banned_user(ctx.guild.id, user_id)
                    unbanned_count += 1
                    success = True
                    
                except discord.NotFound:
                    # User is not actually banned, remove from tracking
                    self.remove_banned_user(ctx.guild.id, user_id)
                    unbanned_count += 1  # Count as success since they're no longer banned
                    success = True
                    
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_count += 1
                        wait_time = min(retry_count * 5, 30)  # Progressive backoff, max 30 seconds
                        await asyncio.sleep(wait_time)
                    else:
                        failed_count += 1
                        success = True  # Don't retry for other HTTP errors
                        
                except discord.Forbidden:
                    failed_count += 1
                    success = True  # Don't retry for permission errors
            
            if not success:
                failed_count += 1
            
            # Add delay between operations to avoid rate limiting (1.5 seconds)
            await asyncio.sleep(1.5)
            
            # Update progress based on calculated increment or on the last user
            if processed_count % progress_increment == 0 or processed_count == total_users:
                try:
                    await progress_msg.edit(content=f"Progress: {processed_count}/{total_users} processed... (Unbanned: {unbanned_count}, Failed: {failed_count})")
                except discord.HTTPException:
                    # If we can't edit the progress message, continue anyway
                    pass
        
        return unbanned_count, failed_count

# Run the bot
if __name__ == "__main__":
    # Get bot token from environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found!")
        print("Please create a .env file with your bot token.")
        print("See .env.example for the required format.")
        exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Error: Invalid token provided!")
        print("Please check your DISCORD_TOKEN in the .env file.")
    except Exception as e:
        print(f"Error starting bot: {e}")