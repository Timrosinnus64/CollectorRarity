from ballsdex.core.utils.transformers import BallTransform
import discord
import random
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from ballsdex.core.models import BallInstance, Player, balls, specials
from ballsdex.settings import settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

# Define rarity range-based goals
RARITY_COLLECTION_GOALS = [
    ((raritynumberhere, raritynumberhere), collectiblenumberhere),
    ((raritynumberhere, float("inf")), collectiblenumberhere)
]

# Helper to get collection goal from rarity
def get_collection_goal_by_rarity(rarity: float) -> int:
    for (low, high), goal in RARITY_COLLECTION_GOALS:
        if low <= rarity < high:
            return goal
    return 25  # Fallback if not matched

class Collector(commands.GroupCog, group_name="collector"):
    """
    Collector Code command
    """
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command()
    async def progress(self, interaction: discord.Interaction, ball: BallTransform):
        """
        Check the player's progress towards collecting enough collectibles to get the Collector card.

        Parameters:
        ball: BallTransform
            The ball you want to see progress for.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        player = await Player.get_or_none(discord_id=interaction.user.id)
        if not player:
            await interaction.followup.send("You don't have any balls yet!", ephemeral=True)
            return

        # Fetch user's collectibles (balls)
        user_balls = await BallInstance.filter(player=player).select_related("ball")

        if not user_balls:
            await interaction.followup.send("You have no collectibles yet!", ephemeral=True)
            return

        # Filter balls to check for the specific flock (target collectible)
        target_ball_instances = [ball for ball in user_balls if ball.ball == ball]

        # Count the total number of specific flock balls the player has
        total_target_balls = len(target_ball_instances)

        # Get collection goal based on rarity range
        rarity = ball.rarity
        COLLECTION_GOAL = get_collection_goal_by_rarity(rarity)

        # Calculate remaining
        remaining = max(0, COLLECTION_GOAL - total_target_balls)

        # Send progress information
        embed = discord.Embed(title="Collection Progress", color=discord.Colour.from_rgb(168, 199, 247))
        embed.add_field(name="Total Collectibles", value=f"**{total_target_balls}** {ball.country}", inline=False)
        embed.add_field(name="Collectible Goal", value=f"**{COLLECTION_GOAL}**", inline=False)
        embed.add_field(name="Remaining to Unlock", value=f"**{remaining}**", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command()
    async def claim(self, interaction: discord.Interaction, ball: BallTransform):
        """
        Reward the user with the Collector card if they have collected enough items.

        Parameters:
        ball: BallTransform
            The ball you want to claim.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        player = await Player.get_or_none(discord_id=interaction.user.id)
        if not player:
            await interaction.followup.send("You don't have any balls yet!", ephemeral=True)
            return

        user_balls = await BallInstance.filter(player=player).select_related("ball")

        if not user_balls:
            await interaction.followup.send("You have no collectibles yet!", ephemeral=True)
            return

        target_ball_instances = [ball for ball in user_balls if ball.ball_id == flock.pk]
        total_target_balls = len(target_ball_instances)

        rarity = ball.rarity
        COLLECTION_GOAL = get_collection_goal_by_rarity(rarity)

        special = next((x for x in specials.values() if x.name == "Collector"), None)
        if not special:
            await interaction.followup.send("Collector card not found! Please contact support.", ephemeral=True)
            return

        has_special_card = any(
            ball.special_id == special.pk and ball.ball.country == ball.country 
            for ball in user_balls
        )

        if has_special_card:
            reward_text = "You already have the Collector card for this ball!"
        else:
            if total_target_balls >= COLLECTION_GOAL:
                special_ball = next(
                    (ball for ball in balls.values() if ball.country == ball.country), 
                    None
                )
                if not special_ball:
                    await interaction.followup.send("Special ball not found! Please contact support.", ephemeral=True)
                    return

                await BallInstance.create(
                    ball=special_ball,
                    player=player,
                    server_id=interaction.guild_id,
                    attack_bonus=random.randint(-20, 20),
                    health_bonus=random.randint(-20, 20),
                    special=special
                )
                reward_text = "The Collector card has been added to your collection!"
            else:
                reward_text = f"You have **{total_target_balls}/{COLLECTION_GOAL}** {ball.country}'s. Keep grinding to unlock the Collector card!"

        embed = discord.Embed(title="Collector Card Reward", color=discord.Colour.from_rgb(168, 199, 247))
        embed.add_field(name="Total Collectibles", value=f"**{total_target_balls}** {ball.country}", inline=False)
        embed.add_field(name="Special Reward", value=reward_text, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)
