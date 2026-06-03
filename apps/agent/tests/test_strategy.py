from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import DecisionAction
from guarded_alpha.strategy import choose_trade


def test_choose_trade_selects_best_fixture_candidate() -> None:
    mandate = load_config().mandate
    decision = choose_trade(fixture_snapshot(), fixture_portfolio(), mandate)

    assert decision.action == DecisionAction.BUY
    assert decision.symbol == "CAKE"
    assert decision.notional_usd == 100.0
    assert decision.score >= mandate.min_signal_score

