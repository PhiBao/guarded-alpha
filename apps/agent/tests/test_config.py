from guarded_alpha.competition import ELIGIBLE_TOKENS
from guarded_alpha.config import DEFAULT_ELIGIBLE_SYMBOLS, load_config


def test_config_can_use_full_competition_universe(monkeypatch) -> None:
    monkeypatch.setenv("SCAN_FULL_COMPETITION_UNIVERSE", "true")
    monkeypatch.delenv("ELIGIBLE_SYMBOLS", raising=False)

    config = load_config()

    assert config.scan_full_competition_universe is True
    assert config.mandate.eligible_symbols == ELIGIBLE_TOKENS


def test_config_uses_manual_universe_by_default(monkeypatch) -> None:
    monkeypatch.setenv("SCAN_FULL_COMPETITION_UNIVERSE", "false")
    monkeypatch.delenv("ELIGIBLE_SYMBOLS", raising=False)

    config = load_config()

    assert config.scan_full_competition_universe is False
    assert config.mandate.eligible_symbols == DEFAULT_ELIGIBLE_SYMBOLS


def test_config_treats_competition_stables_as_stable(monkeypatch) -> None:
    monkeypatch.delenv("STABLE_SYMBOLS", raising=False)

    stable_symbols = load_config().mandate.stable_symbols

    assert {"USDC", "USDT", "USD1", "USDE", "DAI", "FDUSD"}.issubset(stable_symbols)
