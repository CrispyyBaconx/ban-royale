from discord.ext import commands
from enum import Enum
import random
import datetime

class Action(Enum):
    KICK = "kick"
    MUTE = "mute"
    BAN = "ban"
    NITRO = "nitro"


class MiscCommands(commands.Cog):
    """Miscellaneous commands for Ban Royale (easter eggs, etc.)"""
    # gooning pool is a list of tuples, each tuple contains:
    # 1. the message to send
    # 2. the chance that the message is chosen
    # 3. the action to perform if the message is chosen
    # all chances must sum to 1 or the bot will crash on startup

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gooning_pool: list[tuple[str, float, Action]] = [
            ["was kicked for gooning in a server full of children", 0.5, Action.KICK], 
            ["was muted for gooning in a public park", 0.4, Action.MUTE],
            ["stop gooning", 0.09, Action.BAN],
            [", congrats! you gooned your way to 1 month of discord nitro", 0.01, Action.NITRO],
        ]
        gooning_pool_sum = sum(chance for _, chance, _ in self.gooning_pool)
        if gooning_pool_sum != 1:
            raise ValueError("Gooning pool chances must sum to 1")
    
    @commands.command(name="goon", aliases=['g'])
    async def _goon(self, ctx: commands.Context):
        """If you really want to"""
        # anyone can use this command
        # it just kicks the person who sent the command
        chances = [chance for _, chance, _ in self.gooning_pool]
        message, _, action = random.choices(self.gooning_pool, weights=chances, k=1)[0]

        await ctx.send(f"{ctx.author.mention}{message}")
        match action:
            case Action.KICK:
                await ctx.author.kick(reason="You were kicked for gooning in a server full of children, seek help")
            case Action.MUTE:
                await ctx.author.timeout(reason="You were muted for gooning in a server full of children, seek help", until=datetime.timedelta(minutes=30))
            case Action.BAN:
                await ctx.author.ban(reason="You were banned for gooning in a server full of children, seek help")
            case Action.NITRO:
                # send an ephemeral message with a stored nitro link
                await ctx.send(f"{ctx.author.mention}, here's your nitro: 🖕", ephemeral=True)
                # remove nitro from the pool once claimed
                self.gooning_pool = [item for item in self.gooning_pool if item[2] != Action.NITRO]
                # normalize the remaining chances so they sum to 1
                total_chance = sum(chance for _, chance, _ in self.gooning_pool)
                self.gooning_pool = [(message, chance/total_chance, action) for message, chance, action in self.gooning_pool]


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(MiscCommands(bot))