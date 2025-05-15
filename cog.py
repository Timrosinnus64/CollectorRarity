import logging

import discord
from discord import app_commands
from discord.ext import commands 
from collections import defaultdict
from datetime import datetime, timedelta, timezone 
from typing import TYPE_CHECKING, Optional, cast 

from ballsdex.core.models import BallInstance
from ballsdex.core.models import Player, Special
from ballsdex.core.utils.transformers import BallEnabledTransform
from ballsdex.core.utils.transformers import SpecialTransform
from ballsdex.settings import settings 
from .constants import SPECIAL_NAMES, T1Req, T1Rarity, RoundingOpt, collector_slope 

log = logging.getLogger("ballsdex.packages.collector.cog")

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class claim(commands.GroupCog):
    """
    Collector commands.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        
    def calc_collector_requirement(self, rarity: float) -> int:
        raw = T1Req + (rarity - T1Rarity) * collector_slope
        # bucket it down to nearest RoundingOpt
        buckets = int(raw // RoundingOpt)
        return buckets * RoundingOpt or RoundingOpt 
        
    @app_commands.checks.cooldown(1, 20, key=lambda i: i.user.id)
    @app_commands.command()
    async def collector(
        self, 
        interaction: discord.Interaction,
        ball: BallEnabledTransform 
    ):  
        """ 
        Create a collector Ball.

        Parameters 
        ---------- 
        ball: BallEnabledTransform 
          The ball to create.
        """
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        collector = await Special.get(name=SPECIAL_NAMES["COLLECTOR"]) 
        
        await interaction.response.defer(ephemeral=True)
           
        player_balls = await BallInstance.filter(player=player, ball=ball).all()
        current_count = len(player_balls)
  
        required = self.calc_collector_requirement(ball.rarity)  

        if current_count == 0:
            await interaction.followup.send(
              f"You need {required} {ball.country} to create a collector ball. You have nothing.",
        )     

        elif current_count >= required:      
            await BallInstance.create(
            ball=ball,  # Use ball instead of countryball
            player=player,
            attack_bonus=0,
            health_bonus=0,
            special=collector,
        )
                    
            await interaction.followup.send(f"Successfully created a collector {ball.country}!")
        else:
            remaining = required - current_count
            await interaction.followup.send(
              f"You need {remaining} more {ball.country} to create a collector ball. currently you have {current_count}.", 
        )       

    @app_commands.command()
    async def diamond(
        self,
        interaction: discord.Interaction,
        ball: BallEnabledTransform 
    ):
        """
        Create a diamond ball

        Parameters
        ----------
        ball: BallEnabledTransform
          The diamond ball to create
        """  
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        await interaction.response.defer(ephemeral=True)

        Shiny = await Special.get(name="Shiny")

        shiny_balls = await BallInstance.filter(player=player, ball=ball, special=Shiny).all()
        current_count = len(shiny_balls)

        required = min(25, round(10 * ball.rarity))    

        if current_count >= required:
            await BallInstance.create(
            ball=ball,
            player=player,
            attack_bonus=0,
            health_bonus=0,
            special=diamond,
                
        )
            await interaction.followup.send(f"Successfully created a diamond {ball.country}!")
        else:
            remaining = required - current_count
            await interaction.followup.send(
              f"You need {remaining} more shiny {ball.country} to create a diamond ball. currently you have {current_count}.",
        )

    @app_commands.checks.cooldown(1, 600, key=lambda i: i.user.id)
    @app_commands.command()
    async def emerald(
        self,
        interaction: discord.Interaction,
        ball: BallEnabledTransform
    ):
        """
        Create an emerald ball.
    
        Parameters
        ----------
        ball: BallEnabledTransform
          The emerald ball you want
        """
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        MIN_REQ = 1

        MAX_REQ = 3 
        
        await interaction.response.defer(ephemeral=True)
    
        # Get all tradeable special types
       # Shiny = await Special.get(name="Shiny")
        excluded_names = [SPECIAL_NAMES["SHINY"], SPECIAL_NAMES["EMERALD"]]
        required_specials = await Special.filter(tradeable=True).exclude(name__in=excluded_names).all()
       # required_specials = await Special.filter(tradeable=True).exclude(Shiny).all()
    
        # Get all the player's balls that have specials
        query = BallInstance.filter(player=player, ball=ball).prefetch_related("special")
        special_balls = await query
        shiny_special = await Special.get(name=SPECIAL_NAMES["SHINY"])
        # Filter balls that actually have specials
        special_balls = [b for b in special_balls if b.special]
        
        FORCE_SPECIALS = [SPECIAL_NAMES["COLLECTOR"], SPECIAL_NAMES["DIAMOND"]]

        now = datetime.now(timezone.utc)
        # Count how many of each special type the player has
        special_counts = defaultdict(int)
        for ball_instance in special_balls:  # Renamed to avoid naming conflict with the parameter
            if ball_instance.special:
                special_counts[ball_instance.special.id] += 1
    
        # Track any missing requirements
        missing_requirements = []
    
        # Try to get the emerald special
        try:
            emerald = await Special.get(name=SPECIAL_NAMES["EMERALD"])
        except:
            await interaction.followup.send("Error: Emerald special type doesn't exist in the database.")
            return
    
        # Check requirements for each special type
        meets_all_requirements = True
        shiny_substitutes = 0 
        
        for special in required_specials: 
            required_count = round((special.rarity) * (MAX_REQ - MIN_REQ) + MIN_REQ)
            player_count = special_counts[special.id]
            
            if special.name not in FORCE_SPECIALS:    
                is_current = (special.start_date and special.start_date <= now and
                            (not special.end_date or special.end_date >= now))

                if is_current:
                   if player_count < required_count:
                       meets_all_requirements = False
                       missing_requirements.append((special.name, player_count, required_count))
                       continue
                              
                exists = await BallInstance.filter(ball=ball, special=special).exists() 
                
                if not exists:
                    shiny_substitutes += required_count
                    continue

            if player_count < required_count:
                meets_all_requirements = False
                missing_requirements.append((special.name, player_count, required_count))
                
        if shiny_substitutes > 0:
            shiny_count = await BallInstance.filter(
                player=player, ball=ball, special=shiny_special
            ).count()
            required_shinies = shiny_substitutes 
        
            if shiny_count < required_shinies:
                meets_all_requirements = False
                missing_requirements.append(("shiny", shiny_count, required_shinies))
        # Create the emerald ball if all requirements are met
        if meets_all_requirements:
            try:
                await BallInstance.create(
                    ball=ball,
                    player=player,
                    health_bonus=0,
                    attack_bonus=0,
                    special=emerald,
                )
                await interaction.followup.send(f"Successfully created an emerald {ball.country}!")
            except Exception as e:
                await interaction.followup.send(f"Error creating emerald ball: {str(e)}")
        else:
            # Format the message about missing requirements
         #  lines = [f"{name},{have}/{need}" for name, have, need in missing_requirements] 
         #  await interaction.followup.send(f"Failed to create an emerald {ball.country} ball.\n" + "\n".join(lines)) 
         missing_text = ", ".join(f"{name} ({have}/{need})" for name, have, need in missing_requirements)
         await interaction.followup.send(
            f"Failed to create an emerald {ball.country} ball. Missing: {missing_text}"
         )
             
    @app_commands.command()
    @app_commands.checks.has_any_role(*settings.root_role_ids, *settings.admin_role_ids)
    @app_commands.choices( 
     purge=[
        app_commands.Choice(name="EMERALD", value="emerald"),
        app_commands.Choice(name="DIAMOND", value="diamond"),
        app_commands.Choice(name="COLLECTOR", value="collector"),
    ])
    async def purge_special(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        purge: app_commands.Choice[str],
    ):
        """
        Purge selected special balls from all users. Use with caution.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
    
        special = await Special.get_or_none(name__iexact=purge.value)
        shiny = await Special.get_or_none(name="Shiny") if purge.value == "diamond" else None
    
        if not special:
            await interaction.followup.send("Selected special type not found.", ephemeral=True)
            return
    
        all_instances = await BallInstance.filter(special=special).prefetch_related("player", "ball", "special")
    
        purged = 0
        for instance in all_instances:
            player = instance.player
            ball = instance.ball
    
            if purge.value == "collector":
                required = round(200 * ball.rarity)
                count = await BallInstance.filter(player=player, ball=ball).count()
                if count >= required:
                    continue  # still valid, skip
    
            elif purge.value == "diamond":
                required = min(47, round(6 * ball.rarity))
                count = await BallInstance.filter(player=player, ball=ball, special=shiny).count()
                if count >= required:
                    continue  # still valid, skip
    
            await instance.delete()
            purged += 1
            try:
                user = await self.bot.fetch_user(player.discord_id)
                await user.send(f"Your {purge.name.title()} ball has been removed due to event rules.")
            except Exception as e:
                logging.warning(f"Failed to DM user: {e}")
    
        await interaction.followup.send(f"Purged {purged} {purge.name.title()} balls.", ephemeral=True)
        
