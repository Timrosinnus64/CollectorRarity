
SPECIAL_NAMES = {
    "EMERALD": "emerald",
    "COLLECTOR": "collector",
    "DIAMOND": "diamond",
    "SHINY": "Shiny",
}

T1Req       = 250  # need 250 at rarity = 1
T1Rarity    = 1     # the “top 1” rarity value
CommonReq   = 5150
CommonRarity= 340
RoundingOpt = 50  # round to nearest 10

collector_slope = (CommonReq - T1Req) / (CommonRarity - T1Rarity)
# ≈ 14.257 
