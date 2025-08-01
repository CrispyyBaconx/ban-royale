import discord
import asyncio
from discord.ext import commands

class UnbanCommands(commands.Cog):
    """Unban commands for Ban Royale (mass unban functionality)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.main_cog = None  # Will be set by main.py
    
    def get_main_cog(self):
        """Get reference to main cog for shared functionality"""
        if self.main_cog is None:
            self.main_cog = self.bot.get_cog('Main')
        return self.main_cog

    @commands.command(name="unbanall", aliases=['ua'])
    async def _unbanall(self, ctx):
        """Unban all users who were banned during the event"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        banned_users = main.load_banned_users(ctx.guild.id)
        
        if not banned_users:
            return await ctx.send(f"{ctx.author.mention}, No users are currently tracked as banned during this event!")
        
        # Count only actual user IDs (exclude special keys that start with underscore)
        total_users = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        await ctx.send(f"Starting to unban {total_users} users banned during the event... This may take a while to avoid rate limits.")
        
        unbanned_count = 0
        failed_count = 0
        processed_count = 0
        
        # Calculate progress increment based on total users
        progress_increment = main.get_progress_increment(total_users)
        
        # Send initial progress message
        progress_msg = await ctx.send(f"Progress: 0/{total_users} processed...")
        
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
                    await ctx.guild.unban(ban_entry.user, reason=f"Event mass unban by {ctx.author.name}")
                    main.remove_banned_user(ctx.guild.id, user_id)
                    unbanned_count += 1
                    success = True
                    
                except discord.NotFound:
                    # User is not actually banned, remove from tracking
                    main.remove_banned_user(ctx.guild.id, user_id)
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
        
        await ctx.send(f"Unban complete! Successfully unbanned **{unbanned_count}** users. Failed: **{failed_count}** users.")
        
        # Log the mass unban
        log_channel = self.bot.get_channel(main.config['ban_logs'])
        if log_channel:
            await log_channel.send(f"{ctx.author.mention} performed a mass unban of event participants! Unbanned: {unbanned_count}, Failed: {failed_count}")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(UnbanCommands(bot))