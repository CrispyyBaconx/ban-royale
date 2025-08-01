import discord
from discord.ext import commands

class UtilityCommands(commands.Cog):
    """Utility commands for Ban Royale (remaining participants, etc.)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.main_cog = None  # Will be set by main.py
    
    def get_main_cog(self):
        """Get reference to main cog for shared functionality"""
        if self.main_cog is None:
            self.main_cog = self.bot.get_cog('Main')
        return self.main_cog

    @commands.command(name="remaining", aliases=['r'])
    async def _remaining(self, ctx):
        """Show how many participants remain in the current game"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        if not ctx.guild:
            return await ctx.send("This command can only be used in servers.")
        
        if not main.enabled:
            embed = discord.Embed(
                title="📊 Game Status",
                description="No Ban Royale game is currently active.",
                color=0x808080
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            return await ctx.send(embed=embed)
        
        effective_count = main.get_effective_member_count(ctx.guild)
        banned_users = main.load_banned_users(ctx.guild.id)
        banned_count = len([user_id for user_id in banned_users.keys() if not user_id.startswith('_')])
        remaining_members_list = main.get_remaining_members(ctx.guild)
        remaining_count = len(remaining_members_list)
        
        # Calculate percentage
        if effective_count > 0:
            percentage_remaining = (remaining_count / effective_count) * 100
            percentage_banned = (banned_count / effective_count) * 100
        else:
            percentage_remaining = 0
            percentage_banned = 0
        
        embed = discord.Embed(
            title="📊 Ban Royale Status",
            description="Current game statistics",
            color=0x00ff00 if remaining_count > 1 else 0xffd700
        )
        
        embed.add_field(
            name="👥 Participants Remaining",
            value=f"**{remaining_count}** out of {effective_count} ({percentage_remaining:.1f}%)",
            inline=False
        )
        
        embed.add_field(
            name="💀 Participants Banned",
            value=f"**{banned_count}** out of {effective_count} ({percentage_banned:.1f}%)",
            inline=False
        )
        
        # Add status indicator
        if remaining_count <= 1:
            if remaining_count == 1:
                embed.add_field(name="🏆 Status", value="**Winner determined!**", inline=False)
            else:
                embed.add_field(name="💀 Status", value="**Total elimination!**", inline=False)
        elif remaining_count <= 5:
            embed.add_field(name="🔥 Status", value="**Final showdown!**", inline=False)
        elif remaining_count <= 10:
            embed.add_field(name="⚡ Status", value="**Getting intense!**", inline=False)
        else:
            embed.add_field(name="🎯 Status", value="**Game in progress**", inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(UtilityCommands(bot))