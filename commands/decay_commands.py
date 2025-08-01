from discord.ext import commands

class DecayCommands(commands.Cog):
    """Decay mode commands for Ban Royale (dynamic ban chance based on participants)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.main_cog = None  # Will be set by main.py
    
    def get_main_cog(self):
        """Get reference to main cog for shared functionality"""
        if self.main_cog is None:
            self.main_cog = self.bot.get_cog('Main')
        return self.main_cog

    @commands.command(name="decay", aliases=['d'])
    async def _decay(self, ctx):
        """Toggle decay mode on/off"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
            return await ctx.send(f"{ctx.author.mention}, You don't have permission to use this command!")
        
        main.config['decay_mode'] = not main.config['decay_mode']
        status = "**enabled**" if main.config['decay_mode'] else "**disabled**"
        await ctx.send(f"Decay mode has been {status}!")
        
        if main.config['decay_mode']:
            effective_count = main.get_effective_member_count(ctx.guild)
            await ctx.send(f"📊 Effective members for decay calculations: **{effective_count}** (excluding bots and bot masters)")

    @commands.command(name="decaymin", aliases=['dmin'])
    async def _decaymin(self, ctx):
        """Set the minimum decay chance percentage"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
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
        if chance >= main.config['max_decay_chance']:
            return await ctx.send(f"{ctx.author.mention}, Minimum decay chance must be less than maximum decay chance ({main.config['max_decay_chance']*100:.1f}%)!")
        
        main.config['min_decay_chance'] = chance
        await ctx.send(f"Minimum decay chance has been set to **{chance*100:.1f}%**!")

    @commands.command(name="decaymax", aliases=['dmax'])
    async def _decaymax(self, ctx):
        """Set the maximum decay chance percentage"""
        main = self.get_main_cog()
        if not main:
            return await ctx.send("Error: Main cog not found!")
        
        # need to be a bot master to use this command
        if not any(role.id == main.config['bot_master'] for role in ctx.author.roles):
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
        if chance <= main.config['min_decay_chance']:
            return await ctx.send(f"{ctx.author.mention}, Maximum decay chance must be greater than minimum decay chance ({main.config['min_decay_chance']*100:.1f}%)!")
        
        main.config['max_decay_chance'] = chance
        await ctx.send(f"Maximum decay chance has been set to **{chance*100:.1f}%**!")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(DecayCommands(bot))