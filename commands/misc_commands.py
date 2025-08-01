from discord.ext import commands

class MiscCommands(commands.Cog):
    """Miscellaneous commands for Ban Royale (easter eggs, etc.)"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="goon", aliases=['g'])
    async def _goon(self, ctx):
        """If you really want to"""
        # anyone can use this command
        # it just kicks the person who sent the command
        await ctx.author.kick(reason="You were kicked for gooning in a server full of children, seek help")
        await ctx.send(f"{ctx.author.mention} was kicked for gooning in a server full of children")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(MiscCommands(bot))