import discord
import random
import asyncio
from discord.ext import commands

from main import Main

class BasicCommands(commands.Cog):
    """Basic Ban Royale commands (enable, disable, ban, etc.)"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.main_cog = None  # Will be set by main.py
    
    def get_main_cog(self) -> 'Main':
        """Get reference to main cog for shared functionality"""
        if self.main_cog is None:
            self.main_cog = self.bot.get_cog('Main')
        return self.main_cog

    @commands.command(name="enable", aliases=['start'])
    async def _enable(self, ctx: commands.Context):
        """Enable the Ban Royale functionality with countdown"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # Check if user has bot master role
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        if main.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is already enabled!")
        
        allowed_mentions = discord.AllowedMentions(everyone=True)
        
        # Start countdown sequence with @everyone ping
        countdown_msg = await ctx.send("@everyone 🚀 **Ban Royale Game Starting in 10 seconds!** 🚀", allowed_mentions=allowed_mentions)
        await asyncio.sleep(5)  # Wait 5 seconds (10 -> 5)
        
        await countdown_msg.edit(content="@everyone ⏰ **Game Starting in 5 seconds!** ⏰")
        await asyncio.sleep(1)  # Wait 1 second (5 -> 4)
        
        await countdown_msg.edit(content="@everyone ⏰ **4** ⏰")
        await asyncio.sleep(1)  # Wait 1 second (4 -> 3)
        
        await countdown_msg.edit(content="@everyone ⏰ **3** ⏰")
        await asyncio.sleep(1)  # Wait 1 second (3 -> 2)
        
        await countdown_msg.edit(content="@everyone ⏰ **2** ⏰")
        await asyncio.sleep(1)  # Wait 1 second (2 -> 1)
        
        await countdown_msg.edit(content="@everyone ⏰ **1** ⏰")
        await asyncio.sleep(1)  # Wait 1 second (1 -> GO)
        
        await countdown_msg.edit(content="@everyone 🔥 **GO! BAN ROYALE IS LIVE!** 🔥")
        
        # Enable the bot
        main.enabled = True
        # Reset ban counts for new game
        main.session_ban_counts.clear()
        
        # Record initial participants (who was here when game started)
        initial_members = set()
        bot_master_role_id = main.config['bot_master']
        bot_member = ctx.guild.get_member(self.bot.user.id)
        bot_top_role_position = bot_member.top_role.position if bot_member else 0
        
        for member in ctx.guild.members:
            # Skip bots
            if member.bot:
                continue
            # Skip users with bot master role
            if any(role.id == bot_master_role_id for role in member.roles):
                continue
            # Skip users with roles above the bot
            if member.top_role.position >= bot_top_role_position:
                continue
            initial_members.add(member.id)
        
        main.initial_participants[ctx.guild.id] = initial_members
        
        # Console log
        print(f"🚀 [CONSOLE] Ban Royale ENABLED in {ctx.guild.name} by {ctx.author.name} - {len(initial_members)} initial participants")
        
        # Send final status message
        await ctx.send(f"✅ Ban Royale has been **enabled**! Session ban counts reset. **Let the games begin!** 🎯")

    @commands.command(name="disable")
    async def _disable(self, ctx: commands.Context):
        """Disable the Ban Royale functionality"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # Check if user has bot master role
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        if not main.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is already disabled!")
        
        main.enabled = False
        print(f"🔴 [CONSOLE] Ban Royale DISABLED in {ctx.guild.name} by {ctx.author.name}")
        await ctx.send(f"Ban Royale has been **disabled**!")

    @commands.command(name="ban", aliases=['b'])
    async def _ban(self, ctx: commands.Context, *, user: discord.Member = None):
        """Ban a user with a chance of failure"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # Check if Ban Royale is enabled
        if not main.enabled:
            return await ctx.send(f"{ctx.author.mention}, Ban Royale is currently disabled!")
        
        if not user: 
            return await ctx.send(f"{ctx.author.mention}, I need someone to ban.")
        
        if ctx.channel.id != main.config['ban_channel']: 
            return await ctx.send(f"{ctx.author.mention}, You can't ban in this channel!")
        
        if not ctx.guild: 
            return await ctx.send("You can't ban people in DMs.")
        
        try: 
            user = await commands.MemberConverter().convert(ctx, user)
        except commands.BadArgument: 
            return await ctx.send(f"{ctx.author.mention}, I can't find that user!")

        if user.id == ctx.author.id: 
            return await ctx.send(f"{ctx.author.mention}, You can't ban yourself.")

        # Allow users without roles (only @everyone) to ban anyone
        # Only apply role hierarchy check if the author has roles above @everyone
        if ctx.author.top_role.position > 0 and ctx.author.top_role.position <= user.top_role.position:
            return await ctx.send(f"{ctx.author.mention}, You can't ban that person!")
        
        # Check if user has spectator role (mid-game joiner)
        spectator_role_name = main.config['spectator_role']
        for role in ctx.author.roles:
            if role.name == spectator_role_name:
                return await ctx.send(f"{ctx.author.mention}, Spectators cannot use ban commands! You joined mid-game.")

        current_chance = main.get_current_ban_chance(ctx.guild)
        if random.random() < current_chance:
            retry_count = 0
            max_retries = 3
            success = False
            
            while retry_count < max_retries and not success:
                try: 
                    await user.ban(reason=f"Ban Royale: Banned by {ctx.author.name}", delete_message_seconds=1)
                    # Track the banned user
                    main.save_banned_user(ctx.guild.id, user.id, user.name, ctx.author.name)
                    success = True
                except discord.Forbidden: 
                    return await ctx.send(f"{ctx.author.mention}, Can't ban this user! (insufficient permissions)")
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
                await ctx.message.add_reaction(main.config['react_emoji'])
                
                # Update session ban count
                user_id = str(ctx.author.id)
                if user_id not in main.session_ban_counts:
                    main.session_ban_counts[user_id] = 0
                main.session_ban_counts[user_id] += 1
                ban_count = main.session_ban_counts[user_id]
                
                # Send message to ban channel with ban count
                ban_channel = self.bot.get_channel(main.config['ban_channel'])
                if ban_channel:
                    await ban_channel.send(f"{ctx.author.mention} banned {user.mention}! **({ban_count})**")
                
                # Send log to logs channel
                log_channel = self.bot.get_channel(main.config['ban_logs'])
                if log_channel:
                    await log_channel.send(f"{ctx.author.mention} banned {user.mention}! ({ban_count})")
                
                # Check and log decay checkpoints if in decay mode
                await main.check_and_log_checkpoints(ctx.guild)
                
                # Check win condition and end game if met
                game_ended = await main.check_win_condition(ctx.guild)
                if game_ended:
                    return  # Game ended, no need for delay
                
                # Add configurable delay after successful ban
                if main.config['ban_delay'] > 0:
                    await asyncio.sleep(main.config['ban_delay'])
            return

        await ctx.send(f"{ctx.author.mention}, your attempted ban against **{user.name}** failed! (lol)")

    @commands.command(name="banchance", aliases=['bc'])
    async def _banchance(self, ctx: commands.Context):
        """Set the chance of a ban being successful"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
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
        
        main.config['ban_chance'] = chance
        await ctx.send(f"Ban chance has been set to **{chance*100}%**!")

    @commands.command(name="bandelay", aliases=['bd'])
    async def _bandelay(self, ctx: commands.Context):
        """Set the delay between ban operations in seconds"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
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
        
        main.config['ban_delay'] = delay
        if delay == 0:
            await ctx.send(f"Ban delay has been **disabled**!")
        else:
            await ctx.send(f"Ban delay has been set to **{delay} seconds**!")

    @commands.command(name="help", aliases=['h', 'commands'])
    async def _help(self, ctx: commands.Context):
        """Display all available commands"""
        embed = discord.Embed(
            title="🤖 Ban Royale Commands",
            description="All available commands for the Ban Royale bot",
            color=0x00ff00
        )
        
        # Basic Commands
        basic_commands = [
            "`!enable` or `!start` - Enable the bot royale functionality with countdown (Bot Master only)",
            "`!disable` - Disable the bot royale functionality (Bot Master only)",
            "`!ban <user>` or `!b <user>` - Attempt to ban a user with a configurable chance",
            "`!banchance <percentage>` or `!bc <percentage>` - Set the ban success chance (Bot Master only)",
            "`!bandelay <seconds>` or `!bd <seconds>` - Set delay between ban operations (0-60 seconds, Bot Master only)",
            "`!config` or `!cfg` - Display current bot configuration in an embed (Bot Master only)",
            "`!endgame` or `!eg` - End the current game, disable bot, unban all participants, and reset state (Bot Master only)"
        ]
        embed.add_field(
            name="📋 Basic Commands",
            value="\n".join(basic_commands),
            inline=False
        )
        
        # Decay Mode Commands
        decay_commands = [
            "`!decay` or `!d` - Toggle decay mode on/off (Bot Master only)",
            "`!decaymin <percentage>` or `!dmin <percentage>` - Set minimum decay chance (Bot Master only)",
            "`!decaymax <percentage>` or `!dmax <percentage>` - Set maximum decay chance (Bot Master only)"
        ]
        embed.add_field(
            name="📉 Decay Mode Commands",
            value="\n".join(decay_commands),
            inline=False
        )
        
        # Unban Commands
        unban_commands = [
            "`!unbanall` or `!ua` - Unban all users who were banned during the event (Bot Master only)"
        ]
        embed.add_field(
            name="🔓 Unban Commands",
            value="\n".join(unban_commands),
            inline=False
        )
        
        # Utility Commands
        utility_commands = [
            "`!remaining` or `!r` - Show how many participants remain in the current game"
        ]
        embed.add_field(
            name="📊 Utility Commands",
            value="\n".join(utility_commands),
            inline=False
        )
        
        # Footer
        embed.set_footer(text="Note: Bot Master commands require the configured Bot Master role")
        
        await ctx.send(embed=embed)

    @commands.command(name="config", aliases=['cfg'])
    async def _config(self, ctx: commands.Context):
        """Display current bot configuration"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        embed = discord.Embed(
            title="🤖 Ban Royale Configuration",
            color=0x00ff00 if main.enabled else 0xff0000,
            timestamp=discord.utils.utcnow()
        )
        
        # Status
        status = "🟢 Enabled" if main.enabled else "🔴 Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        # Ban settings
        if main.config['decay_mode']:
            current_chance = main.get_current_ban_chance(ctx.guild)
            embed.add_field(name="Current Ban Chance (Decay)", value=f"{current_chance*100:.1f}%", inline=True)
        else:
            embed.add_field(name="Ban Chance (Static)", value=f"{main.config['ban_chance']*100:.1f}%", inline=True)
        
        embed.add_field(name="Ban Delay", value=f"{main.config['ban_delay']:.1f}s", inline=True)
        
        # Member count (always show)
        effective_count = main.get_effective_member_count(ctx.guild)
        banned_count = len(main.load_banned_users(ctx.guild.id))
        embed.add_field(name="Members", value=f"{effective_count} (excl. bots/masters)", inline=True)
        embed.add_field(name="Progress", value=f"{banned_count}/{effective_count} banned", inline=True)
        
        # Decay mode settings
        decay_status = "🟢 Enabled" if main.config['decay_mode'] else "🔴 Disabled"
        embed.add_field(name="Decay Mode", value=decay_status, inline=True)
        
        if main.config['decay_mode']:
            logged_checkpoints = main.get_logged_checkpoints(ctx.guild.id)
            
            embed.add_field(name="Decay Range", value=f"{main.config['min_decay_chance']*100:.1f}% - {main.config['max_decay_chance']*100:.1f}%", inline=True)
            
            # Show logged checkpoints
            if logged_checkpoints:
                checkpoint_str = ", ".join([f"{cp}%" for cp in sorted(logged_checkpoints)])
                embed.add_field(name="Logged Checkpoints", value=checkpoint_str, inline=True)
            else:
                embed.add_field(name="Logged Checkpoints", value="None yet", inline=True)
        
        # Channel info (show clickable links)
        ban_channel = self.bot.get_channel(main.config['ban_channel'])
        if ban_channel:
            embed.add_field(name="Ban Channel", value=f"<#{main.config['ban_channel']}>", inline=True)
        else:
            embed.add_field(name="Ban Channel", value="Channel not found", inline=True)
        
        logs_channel = self.bot.get_channel(main.config['ban_logs'])
        if logs_channel:
            embed.add_field(name="Logs Channel", value=f"<#{main.config['ban_logs']}>", inline=True)
        else:
            embed.add_field(name="Logs Channel", value="Channel not found", inline=True)
        
        # React emoji
        embed.add_field(name="React Emoji", value=main.config['react_emoji'], inline=True)
        
        # Server-specific stats  
        banned_users = main.load_banned_users(ctx.guild.id)
        embed.add_field(name="Banned Users (This Server)", value=str(len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])), inline=True)
        
        embed.set_footer(text=f"Server: {ctx.guild.name}")
        
        await ctx.send(embed=embed)

    @commands.command(name="endgame", aliases=['eg'])
    async def _end_game(self, ctx: commands.Context):
        """Manually end the current game, disable bot, and unban all participants"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        effective_count = main.get_effective_member_count(ctx.guild)
        banned_users = main.load_banned_users(ctx.guild.id)
        banned_count = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        
        if banned_count == 0:
            embed = discord.Embed(
                title="❌ No Game in Progress",
                description="There is no active game to end. No users are currently banned during this event.",
                color=0xff6b6b
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            return await ctx.send(embed=embed)
        
        # Check current state
        was_decay_mode = main.config['decay_mode']
        was_already_disabled = not main.enabled
        remaining_count = effective_count - banned_count
        
        # Create initial status embed
        embed = discord.Embed(
            title="🏁 Ending Ban Royale Game",
            color=0xffa500
        )
        
        if was_already_disabled:
            embed.description = "**Cleaning up completed game...**"
        else:
            embed.description = "**Ending game and shutting down Ban Royale...**"
        
        embed.add_field(name="📊 Final Statistics", value=f"**{banned_count}**/{effective_count} participants were banned\n**{remaining_count}** participants remain", inline=False)
        embed.set_footer(text=f"Initiated by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
        
        # Perform mass unban only if there are users to unban
        if banned_count > 0:
            unbanned_count, failed_count = await main.perform_mass_unban(ctx, banned_users)
        else:
            unbanned_count, failed_count = 0, 0
        
        # Disable the bot (if not already disabled)
        if not was_already_disabled:
            main.enabled = False
            print(f"🏁 [CONSOLE] Ban Royale ENDED manually in {ctx.guild.name} by {ctx.author.name}")
        
        # Reset decay mode if it was enabled
        if was_decay_mode:
            main.config['decay_mode'] = False
        
        # Reset game state (clear checkpoints and any remaining tracking)
        main.reset_game_state(ctx.guild.id)
        
        # Remove all spectator roles
        await main.clear_spectator_roles(ctx.guild)
        
        # Final status embed
        final_embed = discord.Embed(
            title="✅ Game Cleanup Completed!",
            color=0x00ff00
        )
        
        cleanup_actions = []
        if not was_already_disabled:
            cleanup_actions.append("🔴 Ban Royale has been **disabled**")
        if was_decay_mode:
            cleanup_actions.append("📉 Decay mode has been **reset**")
        if banned_count > 0:
            cleanup_actions.append(f"🔓 Unbanned **{unbanned_count}** users (Failed: **{failed_count}**)")
        cleanup_actions.append("🗑️ Game state has been **cleared**")
        cleanup_actions.append("🔄 Session ban counts have been **reset**")
        
        final_embed.add_field(
            name="🔧 Actions Completed",
            value="\n".join(cleanup_actions),
            inline=False
        )
        
        final_embed.set_footer(text=f"Game ended by {ctx.author.display_name}")
        
        await ctx.send(embed=final_embed)
        
        # Log to ban logs channel
        log_channel = self.bot.get_channel(main.config['ban_logs'])
        if log_channel:
            log_msg = f"🏁 **GAME ENDED** by {ctx.author.mention}\n"
            log_msg += f"Final stats: {banned_count}/{effective_count} banned, {remaining_count} remained\n"
            log_msg += f"Unbanned: {unbanned_count}, Failed: {failed_count}\n"
            log_msg += f"Ban Royale disabled"
            if was_decay_mode:
                log_msg += f", Decay mode reset"
            await log_channel.send(log_msg)


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(BasicCommands(bot))