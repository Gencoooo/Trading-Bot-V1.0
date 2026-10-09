from trading_bot import cli
from trading_bot.data import synthetic_ohlcv


def test_list_shows_every_family(capsys):
    cli.main(["list"])
    out = capsys.readouterr().out
    for fam in ("benchmark", "trend", "mean_reversion", "ml", "bot"):
        assert fam in out
    assert "ft_binhv45" in out


def test_backtest_command_runs_offline(capsys, monkeypatch):
    df = synthetic_ohlcv(800, seed=4)
    monkeypatch.setattr(cli, "load_ohlcv", lambda *a, **k: df)
    cli.main(["backtest", "--strategy", "golden_cross_50_200", "--symbol", "TEST", "--interval", "1d", "--trades", "3"])
    out = capsys.readouterr().out
    assert "Sharpe" in out and "Buy & Hold" in out
