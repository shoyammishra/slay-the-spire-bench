"""Shared enumerations for the simulator."""
from enum import Enum, auto


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    STATUS = auto()
    CURSE = auto()


class CardRarity(Enum):
    BASIC = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SPECIAL = auto()
    CURSE = auto()


class IntentType(Enum):
    ATTACK = auto()
    BUFF = auto()
    DEBUFF = auto()
    BLOCK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    ATTACK_DEFEND = auto()
    SLEEP = auto()
    STUN = auto()
    UNKNOWN = auto()
    ESCAPE = auto()
    MAGIC = auto()


class NodeType(Enum):
    MONSTER = auto()
    ELITE = auto()
    REST = auto()
    MERCHANT = auto()
    TREASURE = auto()
    EVENT = auto()
    BOSS = auto()


class PowerId(str, Enum):
    # Player buffs
    STRENGTH = "Strength"
    DEXTERITY = "Dexterity"
    FOCUS = "Focus"
    VIGOR = "Vigor"
    FLEX = "Flex"
    ENERGIZED = "Energized"
    DOUBLE_TAP = "Double Tap"
    RAGE = "Rage"
    METALLICIZE = "Metallicize"
    DEMON_FORM = "Demon Form"
    DARK_EMBRACE = "Dark Embrace"
    FEEL_NO_PAIN = "Feel No Pain"
    FIRE_BREATHING = "Fire Breathing"
    FLAME_BARRIER = "Flame Barrier"
    JUGGERNAUT = "Juggernaut"
    COMBUST = "Combust"
    EVOLVE = "Evolve"
    RUPTURE = "Rupture"

    # Silent player powers
    NOXIOUS_FUMES = "Noxious Fumes"
    ENVENOM = "Envenom"
    THOUSAND_CUTS = "A Thousand Cuts"
    AFTER_IMAGE = "After Image"
    ACCURACY = "Accuracy"
    INFINITE_BLADES = "Infinite Blades"
    TOOLS_OF_THE_TRADE = "Tools of the Trade"
    WRAITH_FORM = "Wraith Form"
    BURST = "Burst"
    BLUR = "Blur"
    PHANTASMAL = "Phantasmal Killer"   # double damage takes effect NEXT turn
    DOUBLE_DAMAGE = "Double Damage"    # active this turn
    NEXT_TURN_BLOCK = "Next Turn Block"
    NEXT_TURN_DRAW = "Next Turn Draw"
    WELL_LAID_PLANS = "Well-Laid Plans"

    # Debuffs (player or enemy)
    WEAK = "Weak"
    VULNERABLE = "Vulnerable"
    FRAIL = "Frail"
    POISON = "Poison"
    CONFUSED = "Confused"
    CONSTRICTED = "Constricted"
    ENTANGLED = "Entangled"
    NO_DRAW = "No Draw"
    HEX = "Hex"
    SHACKLED = "Shackled"

    # Enemy powers
    CHOKED = "Choked"                  # enemy loses HP per card played
    CORPSE_EXPLOSION = "Corpse Explosion"  # on death, damage other enemies
    THORNS = "Thorns"
    RITUAL = "Ritual"
    CURL_UP = "Curl Up"
    ANGER_ENEMY = "Anger"
    MODE_SHIFT = "Mode Shift"
    SPORE_CLOUD = "Spore Cloud"
    MALLEABLE = "Malleable"
    SHARP_HIDE = "Sharp Hide"
    TIME_WARP = "Time Warp"
    ARTIFACT = "Artifact"
    REGENERATE = "Regenerate"
    INTANGIBLE = "Intangible"
    INVINCIBLE = "Invincible"
