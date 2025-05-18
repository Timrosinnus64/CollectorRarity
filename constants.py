
# This thing is useful for example you want a mythical or case other special to
# or your emerald collector or dimaond have other names insted of changing it in lines of code
# you change it here EMERALD: "birthday" now the code makes birthday or whatever special you define
SPECIAL_NAMES = {
    "EMERALD": "emerald",
    "COLLECTOR": "collector",
    "DIAMOND": "diamond",
    "SHINY": "Shiny",
}

# Ty Moooffical for this 
T1Req       = 250  # number of balls  for top 1 ball
T1Rarity    = 1     
CommonReq   = 5150 # this one is for common balls
CommonRarity= 340 
RoundingOpt = 50  

collector_slope = (CommonReq - T1Req) / (CommonRarity - T1Rarity)

