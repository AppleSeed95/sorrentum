import enum


class AssetClass(enum.Enum):
    ETFs = "etfs"
    Forex = "forex"
    Futures = "Futures"
    SP500 = "sp_500"
    Stocks = "stocks"


class Frequency(enum.Enum):
    Daily = "D"
    Hourly = "H"
    Minutely = "T"
    Tick = "tick"


class ContractType(enum.Enum):
    Continuous = "continuous"
    Expiry = "expiry"


class Extension(enum.Enum):
    CSV = "csv"
    Parquet = "pq"