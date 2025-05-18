import logging
from typing import TYPE_CHECKING, Optional, cast
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.models import BallInstance, Player, Special
from ballsdex.core.utils.transformers import BallEnabledTransform
from ballsdex.settings import settings
from .constants import SPECIAL_NAMES, T1Req, T1Rarity, RoundingOpt, collector_slope

log = logging.getLogger("ballsdex.packages.collector.cog")

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class claim(commands.GroupCog):
    """
    Collector commands for special balls creation.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        
    def calc_collector_requirement(self, rarity: float) -> int:
        """Calculate the number of balls required for a collector ball."""
        raw = T1Req + (rarity - T1Rarity) * collector_slope
        # Bucket it down to nearest RoundingOpt
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
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            collector_special = await Special.get(name=SPECIAL_NAMES["COLLECTOR"])
            
            await interaction.response.defer(ephemeral=True)
               
            player_balls = await BallInstance.filter(player=player, ball=ball).all()
            current_count = len(player_balls)
      
            required = self.calc_collector_requirement(ball.rarity)  

            if current_count == 0:
                await interaction.followup.send(
                  f"You need {required} {ball.country} to create a collector ball. You have nothing."
                )     
            elif current_count >= required:      
                await BallInstance.create(
                    ball=ball,  
                    player=player,
                    attack_bonus=0,
                    health_bonus=0,
                    special=collector_special,
                )
                        
                await interaction.followup.send(f"Successfully created a collector {ball.country}!")
            else:
                remaining = required - current_count
                await interaction.followup.send(
                  f"You need {remaining} more {ball.country} to create a collector ball. Currently you have {current_count}."
                )
        except Exception as e:
            log.error(f"Error in collector command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.checks.cooldown(1, 20, key=lambda i: i.user.id) 
    @app_commands.command()
    async def diamond(
        self,
        interaction: discord.Interaction,
        ball: BallEnabledTransform 
    ):
        """
        Create a diamond ball.

        Parameters
        ----------
        ball: BallEnabledTransform
          The diamond ball to create
        """  
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            diamond_special = await Special.get(name=SPECIAL_NAMES["DIAMOND"])
            shiny_special = await Special.get(name=SPECIAL_NAMES["SHINY"])

            await interaction.response.defer(ephemeral=True)

            shiny_balls = await BallInstance.filter(player=player, ball=ball, special=shiny_special).all()
            current_count = len(shiny_balls)
            
            # Calculate required shinies based on rarity (max 25)
            required = min(25, round(10 * ball.rarity))    

            if current_count >= required:
                await BallInstance.create(
                    ball=ball,
                    player=player,
                    attack_bonus=0,
                    health_bonus=0,
                    special=diamond_special,
                )
                await interaction.followup.send(f"Successfully created a diamond {ball.country}!")
            else:
                remaining = required - current_count
                await interaction.followup.send(
                    f"You need {remaining} more shiny {ball.country} to create a diamond ball. Currently you have {current_count}."
                )
        except Exception as e:
            log.error(f"Error in diamond command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")

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
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)

            min_req = 1
            max_req = 3 
            
            await interaction.response.defer(ephemeral=True)
        
            # Get emerald special
            emerald_special = await Special.get(name=SPECIAL_NAMES["EMERALD"])
            shiny_special = await Special.get(name=SPECIAL_NAMES["SHINY"])
            
            # Get all tradeable special types (excluding shiny and emerald)
            excluded_names = [SPECIAL_NAMES["SHINY"], SPECIAL_NAMES["EMERALD"]]
            required_specials = await Special.filter(tradeable=True).exclude(name__in=excluded_names).all()
          
            # Get all the player's balls that have specials
            special_balls = await BallInstance.filter(player=player, ball=ball).prefetch_related("special")
            
            # Filter balls that actually have specials
            special_balls = [b for b in special_balls if b.special]
            
            # Special types that must always be included (cannot be substituted)
            force_specials = [SPECIAL_NAMES["COLLECTOR"], SPECIAL_NAMES["DIAMOND"]]

            now = datetime.now(timezone.utc)
            
            # Count how many of each special type the player has for this ball
            special_counts = defaultdict(int)
            for ball_instance in special_balls:  
                if ball_instance.special:
                    special_counts[ball_instance.special.id] += 1
        
            # Track any missing requirements
            missing_requirements = []
            meets_all_requirements = True
            shiny_substitutes = 0 
            
            # Check requirements for each special type
            for special in required_specials: 
                # Calculate requirement based on special rarity
                required_count = round((special.rarity) * (max_req - min_req) + min_req)
                player_count = special_counts[special.id]
                
                if special.name not in force_specials:    
                    is_current = (special.start_date and special.start_date <= now and
                                (not special.end_date or special.end_date >= now))

                    # If it's a current event special but player doesn't have enough
                    if is_current:
                       if player_count < required_count:
                           meets_all_requirements = False
                           missing_requirements.append((special.name, player_count, required_count))
                           continue
                                  
                    # Check if this ball type exists with this special
                    exists = await BallInstance.filter(ball=ball, special=special).exists() 
                    
                    # If this ball type doesn't exist with this special, use shinies instead
                    if not exists:
                        shiny_substitutes += required_count
                        continue

                # If not enough of this special, add to missing requirements
                if player_count < required_count:
                    meets_all_requirements = False
                    missing_requirements.append((special.name, player_count, required_count))
                    
            # Check shiny substitutes if needed
            if shiny_substitutes > 0:
                shiny_count = await BallInstance.filter(
                    player=player, ball=ball, special=shiny_special
                ).count()
                required_shinies = shiny_substitutes 
            
                if shiny_count < required_shinies:
                    meets_all_requirements = False
                    missing_requirements.append(("Extra shiny", shiny_count, required_shinies))
                    
            # Create the emerald ball if all requirements are met
            if meets_all_requirements:
                await BallInstance.create(
                    ball=ball,
                    player=player,
                    health_bonus=0,
                    attack_bonus=0,
                    special=emerald_special,
                )
                await interaction.followup.send(f"Successfully created an emerald {ball.country}!")
            else:
                missing_text = ", ".join(f"{name} ({have}/{need})" for name, have, need in missing_requirements)
                await interaction.followup.send(
                    f"Failed to create an emerald {ball.country} ball. Missing: {missing_text}"
                )
        except Exception as e:
            log.error(f"Error in emerald command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_any_role(*settings.root_role_ids, *settings.admin_role_ids)
    @app_commands.choices( 
        purge=[
            app_commands.Choice(name="EMERALD", value="EMERALD"),
            app_commands.Choice(name="DIAMOND", value="DIAMOND"),
            app_commands.Choice(name="COLLECTOR", value="COLLECTOR"),
        ]
    )
    async def purge_special(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        purge: app_commands.Choice[str],
    ):
        """
        Purge selected special balls from all users who no longer meet requirements. Use with caution.
        """
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        
            special_name = purge.value
            special = await Special.get_or_none(name=special_name)
            
            if not special:
                await interaction.followup.send(f"Special type '{special_name}' not found.", ephemeral=True)
                return
        
            all_instances = await BallInstance.filter(special=special).prefetch_related("player", "ball")
        
            purged = 0
            for instance in all_instances:
                player = instance.player
                ball = instance.ball
        
                if special_name == "COLLECTOR":
                    required = self.calc_collector_requirement(ball.rarity)
                    count = await BallInstance.filter(player=player, ball=ball).count()
                    if count >= required:
                        continue  # still valid, skip
        
                elif special_name == "DIAMOND":
                    shiny = await Special.get(name=SPECIAL_NAMES["SHINY"])
                    required = min(25, round(10 * ball.rarity))
                    count = await BallInstance.filter(player=player, ball=ball, special=shiny).count()
                    if count >= required:
                        continue  # still valid, skip
                
                # If we get here, the requirement is not met
                await instance.delete()
                purged += 1
                
                # Try to notify the user about the purge
                try:
                    user = await self.bot.fetch_user(player.discord_id)
                    await user.send(f"Your {special_name.lower()} {ball.country} ball has been removed because you no longer meet the requirements.")
                except Exception as e:
                    log.warning(f"Failed to DM user {player.discord_id}: {e}")
        
            await interaction.followup.send(f"Purged {purged} {special_name.lower()} balls.", ephemeral=True)
        except Exception as e:
            log.error(f"Error in purge_special command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")
