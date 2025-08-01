import discord
import random
import os
import json
import asyncio
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv

# TODO:
# ✅ implement inverse curve for ban chance as more people are banned (DONE - decay mode)
# exclude users above bot role + those with bot master

# Load environment variables from .env file
load_dotenv()

# Load configuration (with .env file support)
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
}

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

    def load_all_banned_data(self):
        """Load all banned users data from the file"""
        try:
            with open(self.banned_users_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def load_banned_users(self, guild_id):
        """Load the list of users banned during the event for a specific server"""
        all_data = self.load_all_banned_data()
        return all_data.get(str(guild_id), {})
    
    def save_banned_user(self, guild_id, user_id, username, banned_by):
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
    
    def remove_banned_user(self, guild_id, user_id):
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

    def get_effective_member_count(self, guild):
        """Get the effective member count for decay calculations (excluding bots and bot masters)"""
        if not guild:
            return 0
        
        effective_count = 0
        bot_master_role_id = self.config['bot_master']
        
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue
            
            # Skip users with bot master role
            if any(role.id == bot_master_role_id for role in member.roles):
                continue
            
            effective_count += 1
        
        return effective_count
    
    def get_logged_checkpoints(self, guild_id):
        """Get the list of checkpoints already logged for a server"""
        all_data = self.load_all_banned_data()
        guild_data = all_data.get(str(guild_id), {})
        return guild_data.get("_logged_checkpoints", [])
    
    def add_logged_checkpoint(self, guild_id, checkpoint):
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
    
    async def check_and_log_checkpoints(self, guild):
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
    
    def calculate_decay_chance(self, guild):
        """Calculate ban chance using decay mode (inverse curve)"""
        if not guild:
            return self.config['ban_chance']
        
        effective_members = self.get_effective_member_count(guild)
        banned_users = self.load_banned_users(guild.id)
        banned_count = len(banned_users)
        
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
    
    def get_current_ban_chance(self, guild):
        """Get the current ban chance (either normal or decay mode)"""
        if self.config['decay_mode']:
            return self.calculate_decay_chance(guild)
        else:
            return self.config['ban_chance']

    @commands.command(name="enable")
    async def _enable(self, ctx):
        """Enable or disable the Ban Royale functionality"""
        # Check if user has bot master role
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        if self.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is already enabled!")
        
        self.enabled = True
        await ctx.send(f"Ban Royale has been **enabled**!")

    @commands.command(name="disable")
    async def _disable(self, ctx):
        """Disable the Ban Royale functionality"""
        # Check if user has bot master role
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        if not self.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is already disabled!")
        
        self.enabled = False
        await ctx.send(f"Ban Royale has been **disabled**!")

    @commands.command(name="ban", aliases=['b'])
    async def _ban(self, ctx, *, user=None):
        """Ban a user with a chance of failure"""
        # Check if Ban Royale is enabled
        if not self.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is currently disabled!")
        
        if not user: 
            return await ctx.send(f"{ctx.author.mention}, I need someone to ban.")
        
        if ctx.channel.id != self.config['ban_channel']: 
            return await ctx.send(f"{ctx.author.mention}, You can't ban in this channel!")
        
        if not ctx.guild: 
            return await ctx.send("You can't ban people in DMs.")
        
        try: 
            user = await commands.MemberConverter().convert(ctx, user)
        except commands.BadArgument: 
            return await ctx.send(f"{ctx.author.mention}, I can't find that user!")

        if user.id == ctx.author.id: 
            return await ctx.send(f"{ctx.author.mention}, You can't ban yourself.")

        if ctx.author.top_role.position <= user.top_role.position:
            return await ctx.send(f"{ctx.author.mention}, You can't ban that person!")

        current_chance = self.get_current_ban_chance(ctx.guild)
        if random.random() < current_chance:
            retry_count = 0
            max_retries = 3
            success = False
            
            while retry_count < max_retries and not success:
                try: 
                    await user.ban(reason=f"Ban Royale: Banned by {ctx.author.name}")
                    # Track the banned user
                    self.save_banned_user(ctx.guild.id, user.id, user.name, ctx.author.name)
                    success = True
                except discord.Forbidden: 
                    return await ctx.send("I don't have permissions to do that. Please contact an admin to fix this.")
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = min(retry_count * 5, 30)  # Progressive backoff
                            await asyncio.sleep(wait_time)
                        else:
                            return await ctx.send(f"{ctx.author.mention}, Failed to ban after multiple rate limit retries. Please try again later.")
                    else:
                        return await ctx.send(f"Failed to ban user: {e}")
            
            if success:
                await ctx.message.add_reaction(self.config['react_emoji'])
                log_channel = self.bot.get_channel(self.config['ban_logs'])
                if log_channel:
                    await log_channel.send(f"{ctx.author.mention} banned {user.mention}!")
                
                # Check and log decay checkpoints if in decay mode
                await self.check_and_log_checkpoints(ctx.guild)
                
                # Check win condition and end game if met
                game_ended = await self.check_win_condition(ctx.guild)
                if game_ended:
                    return  # Game ended, no need for delay
                
                # Add configurable delay after successful ban
                if self.config['ban_delay'] > 0:
                    await asyncio.sleep(self.config['ban_delay'])
            return

        await ctx.send(f"{ctx.author.mention}, your attempted ban against **{user.name}** failed! (lol)")

    @commands.command(name="banchance", aliases=['bc'])
    async def _banchance(self, ctx):
        """Set the chance of a ban being successful"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        # get the chance from the command
        # if its a floating point
        try: 
            chance = float(ctx.message.content.split(" ")[1])
        except IndexError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        except ValueError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        
        # set the chance
        try:
            chance = chance / 100 # convert to decimal
            if chance < 0.0001: # 0.01%
                return await ctx.send(f"{ctx.author.mention}, The minimum ban chance is **0.01%**! Setting any lower would be too cruel...")
        except ValueError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        
        self.config['ban_chance'] = chance
        await ctx.send(f"Ban chance has been set to **{chance*100}%**!")

    @commands.command(name="bandelay", aliases=['bd'])
    async def _bandelay(self, ctx):
        """Set the delay between ban operations in seconds"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        # get the delay from the command
        try: 
            delay = float(ctx.message.content.split(" ")[1])
        except IndexError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0** and **60** seconds!")
        except ValueError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0** and **60** seconds!")
        
        # validate the delay
        if delay < 0:
            return await ctx.send(f"{ctx.author.mention}, Ban delay cannot be negative!")
        if delay > 60:
            return await ctx.send(f"{ctx.author.mention}, Maximum ban delay is **60 seconds**!")
        
        self.config['ban_delay'] = delay
        if delay == 0:
            await ctx.send(f"Ban delay has been **disabled**!")
        else:
            await ctx.send(f"Ban delay has been set to **{delay} seconds**!")

    @commands.command(name="decay", aliases=['d'])
    async def _decay(self, ctx):
        """Toggle decay mode on/off"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        self.config['decay_mode'] = not self.config['decay_mode']
        status = "**enabled**" if self.config['decay_mode'] else "**disabled**"
        await ctx.send(f"Decay mode has been {status}!")
        
        if self.config['decay_mode']:
            effective_count = self.get_effective_member_count(ctx.guild)
            await ctx.send(f"📊 Effective members for decay calculations: **{effective_count}** (excluding bots and bot masters)")

    @commands.command(name="decaymin", aliases=['dmin'])
    async def _decaymin(self, ctx):
        """Set the minimum decay chance percentage"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        try: 
            chance = float(ctx.message.content.split(" ")[1])
        except IndexError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        except ValueError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        
        chance = chance / 100  # convert to decimal
        if chance < 0.0001:
            return await ctx.send(f"{ctx.author.mention}, The minimum decay chance is **0.01%**!")
        if chance > 1.0:
            return await ctx.send(f"{ctx.author.mention}, The maximum decay chance is **100%**!")
        if chance >= self.config['max_decay_chance']:
            return await ctx.send(f"{ctx.author.mention}, Minimum decay chance must be less than maximum decay chance ({self.config['max_decay_chance']*100:.1f}%)!")
        
        self.config['min_decay_chance'] = chance
        await ctx.send(f"Minimum decay chance has been set to **{chance*100:.1f}%**!")

    @commands.command(name="decaymax", aliases=['dmax'])
    async def _decaymax(self, ctx):
        """Set the maximum decay chance percentage"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        try: 
            chance = float(ctx.message.content.split(" ")[1])
        except IndexError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        except ValueError:
            return await ctx.send(f"{ctx.author.mention}, Please enter a valid number between **0.01** and **100**!")
        
        chance = chance / 100  # convert to decimal
        if chance < 0.0001:
            return await ctx.send(f"{ctx.author.mention}, The minimum decay chance is **0.01%**!")
        if chance > 1.0:
            return await ctx.send(f"{ctx.author.mention}, The maximum decay chance is **100%**!")
        if chance <= self.config['min_decay_chance']:
            return await ctx.send(f"{ctx.author.mention}, Maximum decay chance must be greater than minimum decay chance ({self.config['min_decay_chance']*100:.1f}%)!")
        
        self.config['max_decay_chance'] = chance
        await ctx.send(f"Maximum decay chance has been set to **{chance*100:.1f}%**!")

    @commands.command(name="config", aliases=['cfg'])
    async def _config(self, ctx):
        """Display current bot configuration"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        embed = discord.Embed(
            title="🤖 Ban Royale Configuration",
            color=0x00ff00 if self.enabled else 0xff0000,
            timestamp=discord.utils.utcnow()
        )
        
        # Status
        status = "🟢 Enabled" if self.enabled else "🔴 Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        # Ban settings
        if self.config['decay_mode']:
            current_chance = self.get_current_ban_chance(ctx.guild)
            embed.add_field(name="Current Ban Chance (Decay)", value=f"{current_chance*100:.1f}%", inline=True)
        else:
            embed.add_field(name="Ban Chance (Static)", value=f"{self.config['ban_chance']*100:.1f}%", inline=True)
        
        embed.add_field(name="Ban Delay", value=f"{self.config['ban_delay']:.1f}s", inline=True)
        
        # Decay mode settings
        decay_status = "🟢 Enabled" if self.config['decay_mode'] else "🔴 Disabled"
        embed.add_field(name="Decay Mode", value=decay_status, inline=True)
        
        if self.config['decay_mode']:
            effective_count = self.get_effective_member_count(ctx.guild)
            banned_count = len(self.load_banned_users(ctx.guild.id))
            logged_checkpoints = self.get_logged_checkpoints(ctx.guild.id)
            
            embed.add_field(name="Decay Range", value=f"{self.config['min_decay_chance']*100:.1f}% - {self.config['max_decay_chance']*100:.1f}%", inline=True)
            embed.add_field(name="Effective Members", value=f"{effective_count} (excl. bots/masters)", inline=True)
            embed.add_field(name="Progress", value=f"{banned_count}/{effective_count} banned", inline=True)
            
            # Show logged checkpoints
            if logged_checkpoints:
                checkpoint_str = ", ".join([f"{cp}%" for cp in sorted(logged_checkpoints)])
                embed.add_field(name="Logged Checkpoints", value=checkpoint_str, inline=True)
            else:
                embed.add_field(name="Logged Checkpoints", value="None yet", inline=True)
        
        # Channel info (show clickable links)
        ban_channel = self.bot.get_channel(self.config['ban_channel'])
        if ban_channel:
            embed.add_field(name="Ban Channel", value=f"<#{self.config['ban_channel']}>", inline=True)
        else:
            embed.add_field(name="Ban Channel", value="Channel not found", inline=True)
        
        logs_channel = self.bot.get_channel(self.config['ban_logs'])
        if logs_channel:
            embed.add_field(name="Logs Channel", value=f"<#{self.config['ban_logs']}>", inline=True)
        else:
            embed.add_field(name="Logs Channel", value="Channel not found", inline=True)
        
        # React emoji
        embed.add_field(name="React Emoji", value=self.config['react_emoji'], inline=True)
        
        # Server-specific stats  
        banned_users = self.load_banned_users(ctx.guild.id)
        embed.add_field(name="Banned Users (This Server)", value=str(len(banned_users)), inline=True)
        
        embed.set_footer(text=f"Server: {ctx.guild.name}")
        
        await ctx.send(embed=embed)

    def reset_game_state(self, guild_id):
        """Reset all game state for a server (checkpoints and banned users)"""
        all_data = self.load_all_banned_data()
        guild_id_str = str(guild_id)
        
        if guild_id_str in all_data:
            del all_data[guild_id_str]
            
            with open(self.banned_users_file, 'w') as f:
                json.dump(all_data, f, indent=2)
            return True
        return False

    async def check_win_condition(self, guild):
        """Check if win condition is met and handle game end"""
        if not self.enabled or not guild:
            return False
        
        effective_count = self.get_effective_member_count(guild)
        banned_count = len(self.load_banned_users(guild.id))
        remaining_members = effective_count - banned_count
        
        if remaining_members <= 1:
            # Win condition met! Disable the bot but preserve game state
            self.enabled = False
            
            log_channel = self.bot.get_channel(self.config['ban_logs'])
            if log_channel:
                if remaining_members == 1:
                    await log_channel.send(
                        f"🏆 **GAME OVER - We have a winner!** 🏆\n"
                        f"Only **1 participant** remains out of {effective_count} original members!\n"
                        f"Ban Royale has been **disabled**. Use `!endgame` to unban all participants and reset for the next event."
                    )
                else:
                    await log_channel.send(
                        f"🏁 **GAME OVER - All participants eliminated!** 🏁\n"
                        f"All {effective_count} participants have been banned!\n"
                        f"Ban Royale has been **disabled**. Use `!endgame` to unban all participants and reset for the next event."
                    )
            
            return True
        
        return False

    async def perform_mass_unban(self, ctx, banned_users):
        """Helper function to perform mass unban with progress tracking"""
        total_users = len(banned_users)
        unbanned_count = 0
        failed_count = 0
        processed_count = 0
        
        # Send initial progress message
        progress_msg = await ctx.send(f"Unbanning {total_users} users... Progress: 0/{total_users} processed...")
        
        banned_users_list = list(banned_users.items())
        
        for i, (user_id_str, user_info) in enumerate(banned_users_list):
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
            
            # Update progress every 5 users or on the last user
            if processed_count % 5 == 0 or processed_count == total_users:
                try:
                    await progress_msg.edit(content=f"Progress: {processed_count}/{total_users} processed... (Unbanned: {unbanned_count}, Failed: {failed_count})")
                except discord.HTTPException:
                    # If we can't edit the progress message, continue anyway
                    pass
        
        return unbanned_count, failed_count

    @commands.command(name="endgame", aliases=['eg'])
    async def _end_game(self, ctx):
        """Manually end the current game, disable bot, and unban all participants"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        effective_count = self.get_effective_member_count(ctx.guild)
        banned_users = self.load_banned_users(ctx.guild.id)
        banned_count = len(banned_users)
        
        if banned_count == 0:
            return await ctx.send(f"{ctx.author.mention}, No game is currently in progress!")
        
        # Check current state
        was_decay_mode = self.config['decay_mode']
        was_already_disabled = not self.enabled
        remaining_count = effective_count - banned_count
        
        if was_already_disabled:
            await ctx.send(f"🏁 **Cleaning up completed game...**\nFinal stats: {banned_count}/{effective_count} participants were banned, {remaining_count} remain.")
        else:
            await ctx.send(f"🏁 **Ending game and shutting down Ban Royale...**\nFinal stats: {banned_count}/{effective_count} participants were banned, {remaining_count} remain.")
        
        # Perform mass unban
        unbanned_count, failed_count = await self.perform_mass_unban(ctx, banned_users)
        
        # Disable the bot (if not already disabled)
        if not was_already_disabled:
            self.enabled = False
        
        # Reset decay mode if it was enabled
        if was_decay_mode:
            self.config['decay_mode'] = False
        
        # Reset game state (clear checkpoints and any remaining tracking)
        self.reset_game_state(ctx.guild.id)
        
        # Final status message
        status_msg = f"✅ **Game cleanup completed!**\n"
        if not was_already_disabled:
            status_msg += f"• Ban Royale has been **disabled**\n"
        if was_decay_mode:
            status_msg += f"• Decay mode has been **reset**\n"
        status_msg += f"• Unbanned **{unbanned_count}** users (Failed: **{failed_count}**)\n"
        status_msg += f"• Game state has been **cleared**"
        
        await ctx.send(status_msg)
        
        # Log to ban logs channel
        log_channel = self.bot.get_channel(self.config['ban_logs'])
        if log_channel:
            log_msg = f"🏁 **GAME ENDED** by {ctx.author.mention}\n"
            log_msg += f"Final stats: {banned_count}/{effective_count} banned, {remaining_count} remained\n"
            log_msg += f"Unbanned: {unbanned_count}, Failed: {failed_count}\n"
            log_msg += f"Ban Royale disabled"
            if was_decay_mode:
                log_msg += f", Decay mode reset"
            await log_channel.send(log_msg)

    @commands.command(name="unbanall", aliases=['ua'])
    async def _unbanall(self, ctx):
        """Unban all users who were banned during the event"""
        # need to be a bot master to use this command
        if not any(role.id == self.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        banned_users = self.load_banned_users(ctx.guild.id)
        
        if not banned_users:
            return await ctx.send(f"{ctx.author.mention}, No users are currently tracked as banned during this event!")
        
        total_users = len(banned_users)
        await ctx.send(f"Starting to unban {total_users} users banned during the event... This may take a while to avoid rate limits.")
        
        unbanned_count = 0
        failed_count = 0
        processed_count = 0
        
        # Send initial progress message
        progress_msg = await ctx.send(f"Progress: 0/{total_users} processed...")
        
        banned_users_list = list(banned_users.items())
        
        for i, (user_id_str, user_info) in enumerate(banned_users_list):
            user_id = int(user_id_str)
            processed_count += 1
            
            retry_count = 0
            max_retries = 3
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    ban_entry = await ctx.guild.fetch_ban(discord.Object(id=user_id))
                    await ctx.guild.unban(ban_entry.user, reason=f"Event mass unban by {ctx.author.name}")
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
            
            # Update progress every 5 users or on the last user
            if processed_count % 5 == 0 or processed_count == total_users:
                try:
                    await progress_msg.edit(content=f"Progress: {processed_count}/{total_users} processed... (Unbanned: {unbanned_count}, Failed: {failed_count})")
                except discord.HTTPException:
                    # If we can't edit the progress message, continue anyway
                    pass
        
        await ctx.send(f"Unban complete! Successfully unbanned **{unbanned_count}** users. Failed: **{failed_count}** users.")
        
        # Log the mass unban
        log_channel = self.bot.get_channel(self.config['ban_logs'])
        if log_channel:
            await log_channel.send(f"{ctx.author.mention} performed a mass unban of event participants! Unbanned: {unbanned_count}, Failed: {failed_count}")

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