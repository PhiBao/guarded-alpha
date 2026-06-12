from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.strategy import evaluate_strategy


def test_evaluate_strategy_returns_vote_breakdown() -> None:
    mandate = load_config().mandate

    decision, vibe_score = evaluate_strategy(fixture_snapshot(), fixture_portfolio(), mandate)

    assert decision.symbol == vibe_score.symbol
    assert len(vibe_score.votes) == 7
    assert set(vibe_score.breakdown) == {
        "momentum",
        "mean_reversion",
        "liquidity",
        "sentiment",
        "regime",
        "route",
        "rebalance",
    }
