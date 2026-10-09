# Katalog: alle nachgebauten Bots

Jeder Bot ist in `trading_bot/strategies/` implementiert und besteht den automatischen Look-ahead-Test. Parameter sind die veröffentlichten Standardwerte bzw. die hyperoptimierten Werte aus dem Original.

| Bot | Familie | Original-Zeitebene | Vorbild / Quelle | Logik |
|---|---|---|---|---|
| `buy_hold` | Buy & Hold | – | Benchmark | Kaufen am ersten Tag und halten - die Messlatte für jeden Bot. |
| `adx_trend` | Trendfolge | – | Wilder ADX/DMI | Kauf bei ADX>25 und +DI>-DI, Verkauf bei +DI<-DI. |
| `chandelier_exit` | Trendfolge | – | TradingView 'Chandelier Exit' (everget), ATR 22 x 3 | Long wenn der Kurs über dem Short-Chandelier-Stop schließt, bis er unter den Long-Stop fällt. |
| `ema_cross_12_26` | Trendfolge | – | Zenbot trend_ema / klassischer EMA-Crossover | Long solange EMA12 > EMA26. |
| `ft_adx_momentum` | Trendfolge | 1h | freqtrade-strategies/berlinguyinca/ADXMomentum.py | ADX>25, Momentum>0, +DI>25 und +DI>-DI; TP 1 %. |
| `ft_adx_smas` | Trendfolge | 1h | freqtrade-strategies/berlinguyinca/AdxSmas.py | SMA3/SMA6-Kreuzung bei ADX>25; TP 10 %. |
| `ft_hlhb` | Trendfolge | 4h | freqtrade-strategies/hlhb.py | RSI(10)-Kreuzung über 50 plus EMA5/10-Kreuzung bei ADX>25, mit Trailing-Stop. |
| `ft_multi_ma` | Trendfolge | 4h | freqtrade-strategies/MultiMa.py | TEMA-Leiter: Kauf wenn TEMA30<TEMA15 und TEMA45<TEMA30, Verkauf bei Bruch der langen Leiter. |
| `ft_strategy001` | Trendfolge | 5m | freqtrade-strategies/Strategy001.py | EMA20/50-Kreuzung mit grüner Heikin-Ashi-Kerze. |
| `ft_supertrend` | Trendfolge | 1h | freqtrade-strategies/Supertrend.py | Drei Supertrends (hyperoptimiert) müssen 'up' sein; Ausstieg wenn drei andere 'down'. |
| `ft_trend_following` | Trendfolge | 5m | freqtrade-strategies/futures/TrendFollowingStrategy.py (Long-Seite) | Close kreuzt EMA20 bei steigendem OBV; Trailing-Stop. |
| `golden_cross_50_200` | Trendfolge | – | backtrader/backtesting.py Beispiele, Detzel et al. (2018) MA-Regeln | Long solange SMA50 > SMA200 ('Golden Cross'). |
| `heikin_ashi_trend` | Trendfolge | – | Heikin-Ashi-Trendbots (YouTube/TradingView) | Zwei grüne HA-Kerzen über EMA50 -> Kauf; zwei rote -> Verkauf. |
| `hull_trend` | Trendfolge | – | TradingView 'Hull Suite' (HMA 55) | Long solange die Hull-MA steigt. |
| `ichimoku` | Trendfolge | – | Ichimoku Kinko Hyo (9/26/52) | Long über der Wolke mit Tenkan > Kijun. |
| `macd_gekko` | Trendfolge | – | Gekko MACD-Strategie (12/26/9, Histogramm-Vorzeichen) | Long solange MACD-Histogramm > 0. |
| `parabolic_sar` | Trendfolge | – | Wilder Parabolic SAR (0.02/0.2), Zenbot sar | Long solange Close > SAR. |
| `sma200_filter` | Trendfolge | – | Meb Faber 'A Quantitative Approach to Tactical Asset Allocation' (200-Tage-Linie) | Long solange Close > SMA200. |
| `sma_cross_10_20` | Trendfolge | – | backtesting.py Quickstart 'SmaCross' (n1=10, n2=20) | Long solange SMA10 > SMA20. |
| `supertrend_10_3` | Trendfolge | – | TradingView Supertrend (ATR 10, Faktor 3) | Long solange der Supertrend nach oben zeigt. |
| `tsmom_30` | Trendfolge | – | Time-Series Momentum (Moskowitz/Ooi/Pedersen 2012; Liu/Tsyvinski Krypto-Momentum) | Long wenn die Rendite der letzten 30 Bars > 0. |
| `tsmom_90` | Trendfolge | – | Time-Series Momentum (Moskowitz/Ooi/Pedersen 2012) | Long wenn die Rendite der letzten 90 Bars > 0. |
| `ut_bot` | Trendfolge | – | TradingView 'UT Bot Alerts' (QuantNomad), Key=1, ATR=10 | Kauf wenn der Kurs den ATR-Trailing-Stop von unten kreuzt, Verkauf umgekehrt. |
| `bollinger_breakout` | Ausbruch | – | Bollinger-Ausbruch (Momentum-Variante) | Kauf über dem oberen Band, Verkauf unter der Mittellinie. |
| `keltner_breakout` | Ausbruch | – | Keltner-Kanal-Ausbruch (EMA20 ± 2 ATR) | Kauf über dem oberen Keltner-Band, Verkauf unter der Mitte. |
| `squeeze_momentum` | Ausbruch | – | TradingView 'Squeeze Momentum Indicator' (LazyBear) | Kauf wenn der Squeeze (BB in KC) endet und das Momentum positiv ist; Ausstieg bei fallendem Momentum. |
| `turtle_20_10` | Ausbruch | – | Turtle Trading System 1 / Jesse 'Donchian' Beispiel | 20-Bar-Hoch-Ausbruch, Ausstieg am 10-Bar-Tief, 2N-Stop. |
| `turtle_55_20` | Ausbruch | – | Turtle Trading System 2 | 55-Bar-Hoch-Ausbruch, Ausstieg am 20-Bar-Tief, 2N-Stop. |
| `bollinger_reversion` | Mean Reversion | – | Zenbot bollinger-Strategie | Kauf unter dem unteren Band, Verkauf über dem oberen Band. |
| `cci_gekko` | Mean Reversion | – | Gekko CCI (±100) | Kauf bei CCI<=-100, Verkauf bei CCI>=100. |
| `connors_rsi2` | Mean Reversion | – | Larry Connors RSI(2) (Short Term Trading Strategies That Work) | Über SMA200: Kauf bei RSI(2)<10, Verkauf über SMA5. |
| `ft_bband_rsi` | Mean Reversion | 1h | freqtrade-strategies/berlinguyinca/BbandRsi.py | RSI<30 unter dem unteren BB kaufen, bei RSI>70 verkaufen. |
| `ft_binhv45` | Mean Reversion | 1m | freqtrade-strategies/berlinguyinca/BinHV45.py | Dip-Käufer: Schlusskurs fällt stark unter das untere Bollinger-Band (40), TP 1.25 %. |
| `ft_clucmay72018` | Mean Reversion | 5m | freqtrade-strategies/berlinguyinca/ClucMay72018.py | Kauf 1.5 % unter dem unteren BB unterhalb EMA50, Verkauf an der BB-Mitte, TP 1 %. |
| `ft_combined_binh_cluc` | Mean Reversion | 5m | freqtrade-strategies/berlinguyinca/CombinedBinHAndCluc.py | Kombination aus BinHV45 und ClucMay72018, TP 5 %, SL 5 %. |
| `ft_sample_strategy` | Mean Reversion | 5m | freqtrade/templates/sample_strategy.py (offizielles Template) | RSI kreuzt 30 aufwärts, TEMA unter BB-Mitte und steigend; Ausstieg RSI>70. |
| `ft_strategy002` | Mean Reversion | 5m | freqtrade-strategies/Strategy002.py | RSI<30, Stoch<20, unter BB und Hammer-Kerze. |
| `ft_strategy003` | Mean Reversion | 5m | freqtrade-strategies/Strategy003.py | Tief überverkauft (RSI<28, MFI<16, Fisher-RSI<-0.94) im Aufwärtstrend. |
| `ft_strategy004` | Mean Reversion | 5m | freqtrade-strategies/Strategy004.py | Starker Trend (ADX) + CCI<-100 + Stochastik-Kreuzung aus dem Keller. |
| `ft_strategy005` | Mean Reversion | 5m | freqtrade-strategies/Strategy005.py | Volumen-Spike (4x) unter SMA40 mit RSI 26-35; Ausstieg RSI>74 bei MACD<0. |
| `ft_universal_macd` | Mean Reversion | 5m | freqtrade-strategies/UniversalMACD.py | Kauf wenn EMA12/EMA26-1 in einem engen negativen Band liegt; Ausstieg nur über ROI/SL. |
| `rsi_gekko` | Mean Reversion | – | Gekko RSI-Strategie (14, 30/70) | Kauf bei RSI<30, Verkauf bei RSI>70. |
| `stochrsi_gekko` | Mean Reversion | – | Gekko StochRSI (interval 3, 20/80, persistence 3) | Kauf nach 3 Bars StochRSI<20, Verkauf nach 3 Bars >80. |
| `wavetrend_cross` | Mean Reversion | – | TradingView 'WaveTrend Oscillator' (LazyBear), 10/21, OB/OS 53 | Kauf bei WT-Kreuzung nach oben unter -53, Verkauf bei Kreuzung nach unten über +53. |
| `williams_r` | Mean Reversion | – | Williams %R (14) | Kauf beim Kreuzen über -80, Verkauf über -20. |
| `dca_bot` | DCA/Grid-Bot | – | 3Commas/Gainium-DCA-Bot (Standard-Setup: TP 1.5 %, 6 Safety Orders, Abstand 2 %, Step 1.2, Volumen 1.5) | Kauft eine Basis-Order, verbilligt mit wachsenden Safety-Orders und verkauft alles mit 1.5 % Gewinn. |
| `grid_bot` | DCA/Grid-Bot | – | Pionex/Binance Spot-Grid-Bot (geometrisch, 20 Grids, ±15 %, Neustart außerhalb der Range) | Verteilt Kauf-/Verkaufsorders auf ein Preisgitter und verdient an Schwankungen innerhalb der Range. |
| `ml_ar_forecast` | ML-Vorhersage | – | Statistische Prognose-Bots (ARIMA/AR-Modelle auf Renditen) | AR(5)-Modell auf Log-Renditen, walk-forward neu geschätzt; long wenn die Prognose > 0. |
| `ml_freqai_lightgbm` | ML-Vorhersage | – | Freqtrade FreqAI (FreqaiExampleStrategy + LightGBMRegressor, DI-Ausreißerfilter) | LightGBM sagt die mittlere Rendite der nächsten 24 Kerzen voraus; Kauf bei >1 % (nur wenn der Dissimilarity-Index < 1), Verkauf bei <0. |
| `ml_logistic` | ML-Vorhersage | – | Typischer 'ML Trading Bot' (scikit-learn LogisticRegression auf TA-Features) | Logistische Regression sagt die Richtung der nächsten Kerze voraus; long wenn P(up)>0.5. |
| `ml_lorentzian_knn` | ML-Vorhersage | – | TradingView 'Machine Learning: Lorentzian Classification' (jdehorty) - Re-Implementierung | k-NN (k=8) mit Lorentz-Distanz über RSI/WT/CCI/ADX-Features der letzten 2000 Kerzen (jede 4.), Original-Label, Volatilitäts- und Kernel-Filter, 4 Kerzen Haltedauer. |
| `ml_lstm` | ML-Vorhersage | – | Die populären 'LSTM Bitcoin Price Prediction'-Repos/Tutorials (PyTorch) | LSTM über die letzten 32 Kerzen sagt die nächste Kerzenrichtung voraus; long wenn P(up)>0.5. Skalierung nur auf dem Trainingsfenster. |
| `ml_random_forest` | ML-Vorhersage | – | GitHub-Klassiker 'Random Forest Stock/Crypto Prediction' (scikit-learn) | Random Forest klassifiziert die nächste Kerze (hoch/runter); long wenn P(up)>0.5. |
| `demo_leaky_tutorial_rf` | demo | – | Typischer Tutorial-Fehler (train_test_split(shuffle=True), Backtest auf Trainingsdaten) | Abschreckendes Beispiel mit Look-ahead-Bias - nicht handelbar. |
