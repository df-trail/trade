from __future__ import annotations

from ztrade.config import AppConfig, DataProviderKind
from ztrade.data.ibkr import IbkrHistoricalDataProvider, IbkrSnapshotProvider, ibkr_settings_from_config
from ztrade.data.live import polygon_provider_from_env
from ztrade.data.providers import CsvReplayDataProvider, DataProvider, DemoDataProvider


def create_data_provider(config: AppConfig) -> DataProvider:
    if config.data_provider == DataProviderKind.DEMO:
        return DemoDataProvider(config.default_watchlist)
    if config.data_provider == DataProviderKind.CSV_REPLAY:
        if not config.csv_replay_path:
            raise ValueError("csv_replay_path is required when data_provider is csv_replay.")
        return CsvReplayDataProvider(config.csv_replay_path, delay_seconds=config.replay_delay_seconds)
    if config.data_provider == DataProviderKind.POLYGON_SNAPSHOT:
        return polygon_provider_from_env(
            symbols=config.default_watchlist,
            api_key_env=config.polygon_api_key_env,
            poll_interval_seconds=config.live_poll_interval_seconds,
            finnhub_api_key_env=config.finnhub_api_key_env if config.enable_finnhub_news else None,
        )
    if config.data_provider == DataProviderKind.IBKR_HISTORICAL:
        return IbkrHistoricalDataProvider(
            symbols=config.default_watchlist,
            settings=ibkr_settings_from_config(config),
            delay_seconds=config.replay_delay_seconds,
        )
    if config.data_provider == DataProviderKind.IBKR_SNAPSHOT:
        return IbkrSnapshotProvider(
            symbols=config.default_watchlist,
            settings=ibkr_settings_from_config(config),
            poll_interval_seconds=config.live_poll_interval_seconds,
        )
    raise ValueError(f"Unsupported data provider: {config.data_provider}")
