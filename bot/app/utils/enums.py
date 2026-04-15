from enum import Enum


class BotMode(str, Enum):
    PROD = "prod"
    DEV = "dev"

