# Anhang: vollständige Ranglisten

Portfolio = alle 20 Coins gleich gewichtet (täglich rebalanciert); Portfolio-Bots verteilen ihr Kapital selbst. Kosten 0,1 % Gebühr + 0,05 % Slippage pro Order.


## In-Sample 2017–2023 – 1d

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | keltner_breakout | Ausbruch | +62,6 % | 1,64 | −27,1 % | 2,31 | 20 % | 4 | 65 % |
| 2 | bollinger_breakout | Ausbruch | +76,1 % | 1,64 | −40,1 % | 1,90 | 28 % | 7 | 60 % |
| 3 | **rotation_bot_v1** | Eigener Bot | +114,2 % | 1,59 | −48,9 % | 2,34 | 39 % | – | – |
| 4 | turtle_20_10 | Ausbruch | +73,8 % | 1,51 | −46,8 % | 1,58 | 32 % | 5 | 60 % |
| 5 | ema_cross_12_26 | Trendfolge | +91,8 % | 1,50 | −55,3 % | 1,66 | 45 % | 6 | 70 % |
| 6 | pf_xs_momentum_30d_top5 | Trendfolge | +138,6 % | 1,50 | −65,3 % | 2,12 | 68 % | – | – |
| 7 | tsmom_30 | Trendfolge | +88,9 % | 1,48 | −66,7 % | 1,33 | 47 % | 13 | 70 % |
| 8 | ichimoku | Trendfolge | +62,6 % | 1,47 | −40,0 % | 1,57 | 28 % | 5 | 60 % |
| 9 | **trend_bot_v1** | Eigener Bot | +68,4 % | 1,47 | −40,8 % | 1,68 | 33 % | 7 | 65 % |
| 10 | **own_v05_fast_trend** | Eigener Bot | +68,5 % | 1,46 | −46,4 % | 1,48 | 37 % | 8 | 65 % |
| 11 | heikin_ashi_trend | Trendfolge | +61,0 % | 1,45 | −41,3 % | 1,48 | 30 % | 17 | 60 % |
| 12 | chandelier_exit | Trendfolge | +82,1 % | 1,45 | −62,8 % | 1,31 | 45 % | 5 | 70 % |
| 13 | macd_gekko | Trendfolge | +83,9 % | 1,44 | −49,6 % | 1,69 | 52 % | 12 | 75 % |
| 14 | sma_cross_10_20 | Trendfolge | +86,3 % | 1,44 | −63,6 % | 1,36 | 48 % | 10 | 60 % |
| 15 | supertrend_10_3 | Trendfolge | +83,1 % | 1,40 | −67,3 % | 1,24 | 48 % | 4 | 65 % |
| 16 | parabolic_sar | Trendfolge | +75,1 % | 1,39 | −57,4 % | 1,31 | 47 % | 14 | 65 % |
| 17 | **rotation_v0_plain** | Eigener Bot | +95,0 % | 1,25 | −67,3 % | 1,41 | 67 % | – | – |
| 18 | hull_trend | Trendfolge | +59,1 % | 1,20 | −59,8 % | 0,99 | 46 % | 8 | 60 % |
| 19 | adx_trend | Trendfolge | +45,4 % | 1,19 | −49,0 % | 0,93 | 28 % | 6 | 40 % |
| 20 | ut_bot | Trendfolge | +57,2 % | 1,17 | −63,8 % | 0,90 | 46 % | 19 | 40 % |
| 21 | turtle_55_20 | Ausbruch | +41,7 % | 1,16 | −36,5 % | 1,14 | 21 % | 3 | 40 % |
| 22 | **own_v01_all_bots** | Eigener Bot | +23,6 % | 1,11 | −27,5 % | 0,86 | 22 % | 0 | 70 % |
| 23 | **own_v04_vol_target** | Eigener Bot | +17,6 % | 1,09 | −24,6 % | 0,72 | 17 % | 7 | 60 % |
| 24 | squeeze_momentum | Ausbruch | +21,8 % | 1,04 | −31,1 % | 0,70 | 11 % | 5 | 35 % |
| 25 | **own_v03_slow_trend** | Eigener Bot | +40,5 % | 1,01 | −56,3 % | 0,72 | 36 % | 7 | 50 % |
| 26 | **buy_hold** | Buy & Hold | +60,7 % | 0,99 | −88,9 % | 0,68 | 100 % | 0 | 0 % |
| 27 | pf_xs_momentum_90d_top5 | Trendfolge | +54,6 % | 0,96 | −85,6 % | 0,64 | 68 % | – | – |
| 28 | **own_v02_follow_best** | Eigener Bot | +23,3 % | 0,96 | −31,5 % | 0,74 | 22 % | 10 | 35 % |
| 29 | dca_bot | DCA/Grid-Bot | +38,3 % | 0,83 | −76,6 % | 0,50 | 73 % | 44 | 35 % |
| 30 | sma200_filter | Trendfolge | +31,3 % | 0,82 | −66,6 % | 0,47 | 35 % | 5 | 25 % |
| 31 | ft_multi_ma | Trendfolge | +19,9 % | 0,81 | −45,6 % | 0,44 | 19 % | 12 | 30 % |
| 32 | tsmom_90 | Trendfolge | +32,6 % | 0,81 | −72,5 % | 0,45 | 42 % | 8 | 25 % |
| 33 | grid_bot | DCA/Grid-Bot | +31,3 % | 0,80 | −71,6 % | 0,44 | 44 % | 829 | 30 % |
| 34 | ml_lorentzian_knn | ML-Vorhersage | +9,2 % | 0,72 | −12,1 % | 0,76 | 6 % | 8 | 5 % |
| 35 | golden_cross_50_200 | Trendfolge | +23,1 % | 0,67 | −68,0 % | 0,34 | 36 % | 1 | 15 % |
| 36 | stochrsi_gekko | Mean Reversion | +13,8 % | 0,52 | −77,4 % | 0,18 | 48 % | 12 | 10 % |
| 37 | rsi_gekko | Mean Reversion | +13,1 % | 0,50 | −70,0 % | 0,19 | 44 % | 1 | 20 % |
| 38 | ml_logistic | ML-Vorhersage | +11,1 % | 0,46 | −71,4 % | 0,16 | 31 % | 33 | 20 % |
| 39 | ml_random_forest | ML-Vorhersage | +10,7 % | 0,45 | −71,9 % | 0,15 | 31 % | 31 | 10 % |
| 40 | ml_lstm | ML-Vorhersage | +9,0 % | 0,42 | −78,8 % | 0,11 | 40 % | 10 | 5 % |
| 41 | ml_ar_forecast | ML-Vorhersage | +8,9 % | 0,42 | −68,2 % | 0,13 | 34 % | 68 | 5 % |
| 42 | wavetrend_cross | Mean Reversion | +8,7 % | 0,41 | −70,6 % | 0,12 | 45 % | 1 | 30 % |
| 43 | ft_bband_rsi | Mean Reversion | +5,4 % | 0,39 | −39,1 % | 0,14 | 9 % | 3 | 25 % |
| 44 | connors_rsi2 | Mean Reversion | +4,0 % | 0,29 | −24,5 % | 0,16 | 6 % | 6 | 10 % |
| 45 | bollinger_reversion | Mean Reversion | −1,3 % | 0,24 | −79,5 % | −0,02 | 44 % | 4 | 5 % |
| 46 | ft_supertrend | Trendfolge | +2,2 % | 0,24 | −62,4 % | 0,04 | 26 % | 33 | 5 % |
| 47 | ml_freqai_lightgbm | ML-Vorhersage | +2,0 % | 0,23 | −68,2 % | 0,03 | 29 % | 13 | 5 % |
| 48 | cci_gekko | Mean Reversion | −12,0 % | 0,08 | −83,5 % | −0,14 | 48 % | 6 | 0 % |
| 49 | williams_r | Mean Reversion | −13,7 % | −0,04 | −81,4 % | −0,17 | 43 % | 7 | 0 % |
| 50 | ft_trend_following | Trendfolge | −4,2 % | −0,05 | −50,4 % | −0,08 | 27 % | 13 | 0 % |
| 51 | ft_adx_smas | Trendfolge | −6,7 % | −0,11 | −65,0 % | −0,10 | 26 % | 11 | 0 % |
| 52 | ft_universal_macd | Mean Reversion | −6,7 % | −0,79 | −39,6 % | −0,17 | 5 % | 5 | 10 % |
| 53 | ft_adx_momentum | Trendfolge | −17,7 % | −0,84 | −77,5 % | −0,23 | 12 % | 41 | 0 % |
| 54 | ft_combined_binh_cluc | Mean Reversion | −16,7 % | −1,32 | −70,8 % | −0,24 | 3 % | 16 | 0 % |
| 55 | ft_hlhb † | Trendfolge | +0,6 % | 0,17 | −9,8 % | 0,06 | 2 % | 2 | 10 % |
| 56 | ft_strategy002 † | Mean Reversion | +0,0 % | 0,06 | −1,1 % | 0,03 | 0 % | 0 | 5 % |
| 57 | ft_strategy001 † | Trendfolge | −0,2 % | −0,07 | −8,8 % | −0,03 | 1 % | 3 | 10 % |
| 58 | ft_strategy004 † | Mean Reversion | −0,2 % | −0,10 | −4,7 % | −0,04 | 0 % | 1 | 5 % |
| 59 | ft_strategy003 † | Mean Reversion | −0,2 % | −0,20 | −2,0 % | −0,08 | 0 % | 0 | 5 % |
| 60 | ft_strategy005 † | Mean Reversion | −0,6 % | −0,34 | −4,1 % | −0,14 | 0 % | 0 | 0 % |
| 61 | ft_sample_strategy † | Mean Reversion | −1,8 % | −0,38 | −13,9 % | −0,13 | 1 % | 2 | 0 % |
| 62 | ft_binhv45 † | Mean Reversion | −1,4 % | −0,80 | −9,8 % | −0,14 | 0 % | 1 | 5 % |
| 63 | ft_clucmay72018 † | Mean Reversion | −22,6 % | −2,88 | −80,5 % | −0,28 | 0 % | 13 | 0 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.

## In-Sample 2017–2023 – 4h

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ichimoku | Trendfolge | +80,1 % | 1,65 | −29,8 % | 2,69 | 35 % | 35 | 70 % |
| 2 | **trend_bot_v1** | Eigener Bot | +77,8 % | 1,56 | −44,2 % | 1,76 | 34 % | 12 | 75 % |
| 3 | **rotation_bot_v1** | Eigener Bot | +110,6 % | 1,55 | −52,9 % | 2,09 | 39 % | – | – |
| 4 | pf_xs_momentum_30d_top5 | Trendfolge | +142,3 % | 1,50 | −66,0 % | 2,16 | 68 % | – | – |
| 5 | **own_v05_fast_trend** | Eigener Bot | +71,3 % | 1,50 | −47,7 % | 1,49 | 39 % | 16 | 75 % |
| 6 | hull_trend | Trendfolge | +86,8 % | 1,49 | −50,7 % | 1,71 | 50 % | 49 | 75 % |
| 7 | golden_cross_50_200 | Trendfolge | +86,9 % | 1,45 | −64,7 % | 1,34 | 46 % | 6 | 75 % |
| 8 | sma200_filter | Trendfolge | +79,6 % | 1,41 | −57,5 % | 1,39 | 46 % | 32 | 65 % |
| 9 | ema_cross_12_26 | Trendfolge | +78,0 % | 1,40 | −49,4 % | 1,58 | 49 % | 37 | 70 % |
| 10 | sma_cross_10_20 | Trendfolge | +75,1 % | 1,36 | −57,9 % | 1,30 | 50 % | 62 | 55 % |
| 11 | bollinger_breakout | Ausbruch | +50,4 % | 1,30 | −40,0 % | 1,26 | 27 % | 39 | 45 % |
| 12 | tsmom_90 | Trendfolge | +70,1 % | 1,27 | −50,9 % | 1,38 | 49 % | 48 | 65 % |
| 13 | keltner_breakout | Ausbruch | +40,3 % | 1,26 | −29,3 % | 1,37 | 18 % | 22 | 35 % |
| 14 | **rotation_v0_plain** | Eigener Bot | +97,1 % | 1,25 | −67,5 % | 1,44 | 67 % | – | – |
| 15 | supertrend_10_3 | Trendfolge | +62,5 % | 1,21 | −46,1 % | 1,36 | 48 % | 23 | 60 % |
| 16 | heikin_ashi_trend | Trendfolge | +46,5 % | 1,19 | −55,1 % | 0,84 | 33 % | 110 | 25 % |
| 17 | turtle_55_20 | Ausbruch | +42,7 % | 1,18 | −34,2 % | 1,25 | 24 % | 17 | 55 % |
| 18 | **own_v04_vol_target** | Eigener Bot | +18,0 % | 1,14 | −23,6 % | 0,76 | 16 % | 17 | 65 % |
| 19 | chandelier_exit | Trendfolge | +50,8 % | 1,06 | −50,3 % | 1,01 | 48 % | 31 | 40 % |
| 20 | **own_v03_slow_trend** | Eigener Bot | +41,3 % | 1,04 | −53,8 % | 0,77 | 36 % | 17 | 50 % |
| 21 | turtle_20_10 | Ausbruch | +39,1 % | 1,01 | −49,9 % | 0,78 | 33 % | 31 | 45 % |
| 22 | **own_v01_all_bots** | Eigener Bot | +21,1 % | 1,00 | −33,3 % | 0,64 | 25 % | 0 | 55 % |
| 23 | **buy_hold** | Buy & Hold | +59,5 % | 0,98 | −89,2 % | 0,67 | 100 % | 0 | 0 % |
| 24 | dca_bot | DCA/Grid-Bot | +52,7 % | 0,96 | −77,9 % | 0,68 | 75 % | 145 | 50 % |
| 25 | pf_xs_momentum_90d_top5 | Trendfolge | +54,6 % | 0,96 | −85,7 % | 0,64 | 67 % | – | – |
| 26 | tsmom_30 | Trendfolge | +41,4 % | 0,94 | −66,7 % | 0,62 | 49 % | 91 | 30 % |
| 27 | grid_bot | DCA/Grid-Bot | +35,5 % | 0,92 | −70,0 % | 0,51 | 46 % | 1701 | 40 % |
| 28 | ft_multi_ma | Trendfolge | +20,0 % | 0,90 | −36,5 % | 0,55 | 10 % | 11 | 20 % |
| 29 | squeeze_momentum | Ausbruch | +18,1 % | 0,90 | −41,6 % | 0,43 | 11 % | 32 | 10 % |
| 30 | adx_trend | Trendfolge | +26,9 % | 0,86 | −45,1 % | 0,60 | 26 % | 32 | 30 % |
| 31 | **own_v02_follow_best** | Eigener Bot | +16,6 % | 0,81 | −40,0 % | 0,41 | 21 % | 38 | 15 % |
| 32 | macd_gekko | Trendfolge | +27,8 % | 0,72 | −71,8 % | 0,39 | 51 % | 84 | 0 % |
| 33 | parabolic_sar | Trendfolge | +23,8 % | 0,67 | −73,2 % | 0,32 | 50 % | 84 | 0 % |
| 34 | ft_supertrend | Trendfolge | +14,9 % | 0,54 | −63,3 % | 0,24 | 42 % | 69 | 20 % |
| 35 | ml_freqai_lightgbm | ML-Vorhersage | +13,2 % | 0,53 | −60,6 % | 0,22 | 29 % | 93 | 5 % |
| 36 | ut_bot | Trendfolge | −0,1 % | 0,26 | −78,0 % | −0,00 | 49 % | 115 | 0 % |
| 37 | wavetrend_cross | Mean Reversion | −4,9 % | 0,18 | −74,2 % | −0,07 | 48 % | 7 | 5 % |
| 38 | stochrsi_gekko | Mean Reversion | −6,5 % | 0,16 | −91,0 % | −0,07 | 48 % | 76 | 5 % |
| 39 | connors_rsi2 | Mean Reversion | +0,6 % | 0,12 | −33,5 % | 0,02 | 8 % | 42 | 15 % |
| 40 | ft_hlhb | Trendfolge | +0,6 % | 0,11 | −15,1 % | 0,04 | 8 % | 14 | 10 % |
| 41 | bollinger_reversion | Mean Reversion | −12,8 % | 0,07 | −88,4 % | −0,15 | 51 % | 24 | 0 % |
| 42 | ft_adx_smas | Trendfolge | −10,2 % | −0,02 | −80,4 % | −0,13 | 38 % | 40 | 5 % |
| 43 | rsi_gekko | Mean Reversion | −18,5 % | −0,07 | −90,5 % | −0,20 | 49 % | 8 | 0 % |
| 44 | ml_logistic | ML-Vorhersage | −10,8 % | −0,08 | −91,0 % | −0,12 | 37 % | 245 | 0 % |
| 45 | ft_trend_following | Trendfolge | −16,3 % | −0,11 | −85,8 % | −0,19 | 64 % | 36 | 0 % |
| 46 | ml_lstm | ML-Vorhersage | −12,6 % | −0,12 | −83,7 % | −0,15 | 34 % | 172 | 0 % |
| 47 | cci_gekko | Mean Reversion | −27,2 % | −0,23 | −95,2 % | −0,29 | 50 % | 39 | 0 % |
| 48 | ft_adx_momentum | Trendfolge | −10,7 % | −0,24 | −70,7 % | −0,15 | 28 % | 126 | 5 % |
| 49 | ml_lorentzian_knn | ML-Vorhersage | −4,4 % | −0,25 | −38,1 % | −0,12 | 7 % | 56 | 0 % |
| 50 | williams_r | Mean Reversion | −28,0 % | −0,35 | −93,9 % | −0,30 | 43 % | 48 | 0 % |
| 51 | ft_bband_rsi | Mean Reversion | −24,1 % | −0,49 | −88,9 % | −0,27 | 31 % | 13 | 0 % |
| 52 | ml_random_forest | ML-Vorhersage | −24,5 % | −0,51 | −92,0 % | −0,27 | 34 % | 260 | 0 % |
| 53 | ft_universal_macd | Mean Reversion | −13,3 % | −0,73 | −67,5 % | −0,20 | 15 % | 37 | 0 % |
| 54 | ft_strategy001 | Trendfolge | −6,5 % | −0,97 | −37,8 % | −0,17 | 6 % | 16 | 10 % |
| 55 | ft_sample_strategy | Mean Reversion | −10,5 % | −1,03 | −53,2 % | −0,20 | 4 % | 16 | 5 % |
| 56 | ml_ar_forecast | ML-Vorhersage | −45,0 % | −1,39 | −98,6 % | −0,46 | 33 % | 359 | 0 % |
| 57 | ft_combined_binh_cluc | Mean Reversion | −37,1 % | −1,67 | −95,7 % | −0,39 | 10 % | 55 | 0 % |
| 58 | ft_strategy003 † | Mean Reversion | −0,0 % | −0,03 | −3,1 % | −0,01 | 0 % | 1 | 25 % |
| 59 | ft_strategy002 † | Mean Reversion | −0,0 % | −0,04 | −1,9 % | −0,02 | 0 % | 1 | 20 % |
| 60 | ft_strategy005 † | Mean Reversion | −0,5 % | −0,22 | −7,7 % | −0,07 | 0 % | 1 | 20 % |
| 61 | ft_strategy004 † | Mean Reversion | −3,4 % | −0,53 | −23,7 % | −0,14 | 0 % | 4 | 5 % |
| 62 | ft_binhv45 † | Mean Reversion | −7,6 % | −1,38 | −40,4 % | −0,19 | 0 % | 7 | 0 % |
| 63 | ft_clucmay72018 † | Mean Reversion | −40,1 % | −2,97 | −96,2 % | −0,42 | 2 % | 45 | 0 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.

## In-Sample 2017–2023 – 1h

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **rotation_bot_v1** | Eigener Bot | +106,2 % | 1,54 | −50,7 % | 2,09 | 39 % | – | – |
| 2 | pf_xs_momentum_30d_top5 | Trendfolge | +139,6 % | 1,51 | −65,9 % | 2,12 | 68 % | – | – |
| 3 | **trend_bot_v1** | Eigener Bot | +70,1 % | 1,48 | −40,5 % | 1,73 | 35 % | 23 | 60 % |
| 4 | golden_cross_50_200 | Trendfolge | +84,2 % | 1,48 | −48,5 % | 1,74 | 49 % | 27 | 70 % |
| 5 | ft_multi_ma | Trendfolge | +27,7 % | 1,39 | −16,8 % | 1,65 | 9 % | 20 | 40 % |
| 6 | **own_v05_fast_trend** | Eigener Bot | +57,4 % | 1,32 | −50,3 % | 1,14 | 40 % | 42 | 55 % |
| 7 | **rotation_v0_plain** | Eigener Bot | +90,7 % | 1,23 | −70,7 % | 1,28 | 67 % | – | – |
| 8 | **own_v04_vol_target** | Eigener Bot | +15,8 % | 1,08 | −27,0 % | 0,59 | 16 % | 35 | 55 % |
| 9 | dca_bot | DCA/Grid-Bot | +64,3 % | 1,08 | −77,2 % | 0,83 | 76 % | 234 | 55 % |
| 10 | **buy_hold** | Buy & Hold | +58,8 % | 0,98 | −89,0 % | 0,66 | 100 % | 0 | 0 % |
| 11 | pf_xs_momentum_90d_top5 | Trendfolge | +54,4 % | 0,96 | −85,6 % | 0,64 | 67 % | – | – |
| 12 | **own_v03_slow_trend** | Eigener Bot | +33,4 % | 0,92 | −60,6 % | 0,55 | 36 % | 35 | 45 % |
| 13 | **own_v01_all_bots** | Eigener Bot | +15,0 % | 0,74 | −41,0 % | 0,37 | 27 % | 0 | 30 % |
| 14 | grid_bot | DCA/Grid-Bot | +24,0 % | 0,73 | −67,8 % | 0,35 | 46 % | 2325 | 25 % |
| 15 | supertrend_10_3 | Trendfolge | +21,2 % | 0,63 | −77,6 % | 0,27 | 49 % | 93 | 0 % |
| 16 | ichimoku | Trendfolge | +18,7 % | 0,61 | −67,5 % | 0,28 | 35 % | 154 | 0 % |
| 17 | sma200_filter | Trendfolge | +14,6 % | 0,52 | −71,6 % | 0,20 | 49 % | 151 | 0 % |
| 18 | ema_cross_12_26 | Trendfolge | +13,3 % | 0,50 | −80,2 % | 0,17 | 49 % | 154 | 0 % |
| 19 | keltner_breakout | Ausbruch | +9,6 % | 0,48 | −41,8 % | 0,23 | 17 % | 85 | 0 % |
| 20 | hull_trend | Trendfolge | +11,0 % | 0,45 | −84,0 % | 0,13 | 50 % | 205 | 0 % |
| 21 | turtle_55_20 | Ausbruch | +9,4 % | 0,44 | −64,8 % | 0,14 | 23 % | 66 | 0 % |
| 22 | ml_freqai_lightgbm | ML-Vorhersage | +8,3 % | 0,44 | −55,5 % | 0,15 | 16 % | 147 | 10 % |
| 23 | sma_cross_10_20 | Trendfolge | +8,5 % | 0,41 | −86,8 % | 0,10 | 49 % | 247 | 5 % |
| 24 | **own_v02_follow_best** | Eigener Bot | +3,8 % | 0,29 | −44,5 % | 0,09 | 19 % | 87 | 5 % |
| 25 | bollinger_reversion | Mean Reversion | −4,9 % | 0,23 | −91,8 % | −0,05 | 51 % | 101 | 0 % |
| 26 | connors_rsi2 | Mean Reversion | +2,2 % | 0,22 | −53,9 % | 0,04 | 6 % | 176 | 0 % |
| 27 | ft_supertrend | Trendfolge | −1,1 % | 0,21 | −67,8 % | −0,02 | 43 % | 118 | 5 % |
| 28 | chandelier_exit | Trendfolge | −3,5 % | 0,18 | −83,8 % | −0,04 | 50 % | 128 | 0 % |
| 29 | tsmom_90 | Trendfolge | −5,2 % | 0,15 | −81,0 % | −0,06 | 50 % | 213 | 0 % |
| 30 | wavetrend_cross | Mean Reversion | −10,3 % | 0,11 | −85,8 % | −0,12 | 50 % | 28 | 5 % |
| 31 | rsi_gekko | Mean Reversion | −16,3 % | −0,02 | −90,8 % | −0,18 | 50 % | 30 | 5 % |
| 32 | stochrsi_gekko | Mean Reversion | −18,0 % | −0,09 | −96,1 % | −0,19 | 49 % | 311 | 0 % |
| 33 | bollinger_breakout | Ausbruch | −8,6 % | −0,09 | −75,4 % | −0,11 | 28 % | 161 | 0 % |
| 34 | ft_trend_following | Trendfolge | −32,8 % | −0,21 | −95,8 % | −0,34 | 86 % | 56 | 0 % |
| 35 | turtle_20_10 | Ausbruch | −16,3 % | −0,27 | −83,5 % | −0,20 | 33 % | 130 | 0 % |
| 36 | ft_bband_rsi | Mean Reversion | −24,8 % | −0,35 | −93,0 % | −0,27 | 44 % | 36 | 0 % |
| 37 | adx_trend | Trendfolge | −18,7 % | −0,48 | −78,2 % | −0,24 | 26 % | 129 | 0 % |
| 38 | ft_strategy005 | Mean Reversion | −4,1 % | −0,53 | −34,3 % | −0,12 | 3 % | 9 | 5 % |
| 39 | macd_gekko | Trendfolge | −36,2 % | −0,58 | −96,7 % | −0,37 | 50 % | 341 | 0 % |
| 40 | ft_universal_macd | Mean Reversion | −25,4 % | −0,69 | −89,8 % | −0,28 | 23 % | 76 | 0 % |
| 41 | cci_gekko | Mean Reversion | −43,4 % | −0,70 | −98,7 % | −0,44 | 50 % | 166 | 0 % |
| 42 | ft_adx_smas | Trendfolge | −39,5 % | −0,73 | −97,3 % | −0,41 | 44 % | 128 | 0 % |
| 43 | squeeze_momentum | Ausbruch | −20,7 % | −1,10 | −81,3 % | −0,25 | 12 % | 129 | 0 % |
| 44 | ft_hlhb | Trendfolge | −26,1 % | −1,34 | −86,4 % | −0,30 | 18 % | 56 | 0 % |
| 45 | ft_strategy001 | Trendfolge | −17,7 % | −1,38 | −77,3 % | −0,23 | 17 % | 58 | 0 % |
| 46 | williams_r | Mean Reversion | −57,5 % | −1,44 | −99,6 % | −0,58 | 44 % | 203 | 0 % |
| 47 | ft_combined_binh_cluc | Mean Reversion | −38,9 % | −1,45 | −97,9 % | −0,40 | 9 % | 99 | 0 % |
| 48 | parabolic_sar | Trendfolge | −62,7 % | −1,65 | −99,8 % | −0,63 | 50 % | 344 | 0 % |
| 49 | tsmom_30 | Trendfolge | −65,9 % | −1,75 | −99,9 % | −0,66 | 50 % | 391 | 0 % |
| 50 | ft_adx_momentum | Trendfolge | −48,2 % | −1,75 | −98,6 % | −0,49 | 35 % | 272 | 0 % |
| 51 | ml_lorentzian_knn | ML-Vorhersage | −24,4 % | −1,84 | −85,5 % | −0,29 | 6 % | 226 | 0 % |
| 52 | ft_sample_strategy | Mean Reversion | −30,0 % | −1,88 | −90,6 % | −0,33 | 11 % | 48 | 0 % |
| 53 | heikin_ashi_trend | Trendfolge | −76,6 % | −3,45 | −100,0 % | −0,77 | 35 % | 477 | 0 % |
| 54 | ut_bot | Trendfolge | −85,9 % | −3,50 | −100,0 % | −0,86 | 51 % | 495 | 0 % |
| 55 | ml_logistic | ML-Vorhersage | −77,8 % | −3,65 | −100,0 % | −0,78 | 33 % | 832 | 0 % |
| 56 | ml_lstm | ML-Vorhersage | −77,3 % | −3,68 | −100,0 % | −0,77 | 29 % | 840 | 0 % |
| 57 | ml_random_forest | ML-Vorhersage | −83,2 % | −4,38 | −100,0 % | −0,83 | 30 % | 924 | 0 % |
| 58 | ml_ar_forecast | ML-Vorhersage | −94,0 % | −7,05 | −100,0 % | −0,94 | 31 % | 1282 | 0 % |
| 59 | ft_strategy002 † | Mean Reversion | −0,6 % | −0,24 | −8,6 % | −0,06 | 0 % | 2 | 15 % |
| 60 | ft_strategy004 † | Mean Reversion | −4,0 % | −0,44 | −24,7 % | −0,16 | 2 % | 16 | 10 % |
| 61 | ft_strategy003 † | Mean Reversion | −1,4 % | −0,49 | −10,8 % | −0,13 | 1 % | 4 | 10 % |
| 62 | ft_binhv45 † | Mean Reversion | −6,7 % | −0,95 | −42,5 % | −0,16 | 1 % | 18 | 0 % |
| 63 | ft_clucmay72018 † | Mean Reversion | −28,1 % | −2,16 | −89,4 % | −0,31 | 2 % | 69 | 0 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.

## Out-of-Sample 2024–2026 – 1d

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **rotation_bot_v1** | Eigener Bot | +28,9 % | 0,77 | −44,7 % | 0,65 | 50 % | – | – |
| 2 | bollinger_breakout | Ausbruch | +17,0 % | 0,70 | −32,8 % | 0,52 | 25 % | 6 | 50 % |
| 3 | keltner_breakout | Ausbruch | +14,9 % | 0,69 | −29,4 % | 0,50 | 17 % | 4 | 70 % |
| 4 | **own_v04_vol_target** | Eigener Bot | +11,1 % | 0,67 | −20,9 % | 0,53 | 26 % | 10 | 75 % |
| 5 | ichimoku | Trendfolge | +13,5 % | 0,56 | −34,1 % | 0,39 | 29 % | 5 | 60 % |
| 6 | tsmom_90 | Trendfolge | +13,9 % | 0,52 | −46,3 % | 0,30 | 45 % | 7 | 65 % |
| 7 | **rotation_v0_plain** | Eigener Bot | +12,2 % | 0,48 | −54,3 % | 0,22 | 71 % | – | – |
| 8 | ft_bband_rsi | Mean Reversion | +6,6 % | 0,48 | −23,4 % | 0,28 | 14 % | 3 | 45 % |
| 9 | pf_xs_momentum_90d_top5 | Trendfolge | +11,7 % | 0,48 | −56,3 % | 0,21 | 68 % | – | – |
| 10 | **own_v05_fast_trend** | Eigener Bot | +7,2 % | 0,38 | −46,0 % | 0,16 | 36 % | 11 | 55 % |
| 11 | squeeze_momentum | Ausbruch | +3,6 % | 0,36 | −18,2 % | 0,20 | 10 % | 5 | 45 % |
| 12 | **own_v01_all_bots** | Eigener Bot | +5,0 % | 0,36 | −27,3 % | 0,18 | 27 % | 0 | 50 % |
| 13 | **own_v03_slow_trend** | Eigener Bot | +6,2 % | 0,35 | −49,8 % | 0,12 | 43 % | 10 | 45 % |
| 14 | turtle_20_10 | Ausbruch | +5,6 % | 0,33 | −42,3 % | 0,13 | 31 % | 5 | 45 % |
| 15 | **trend_bot_v1** | Eigener Bot | +5,6 % | 0,33 | −43,4 % | 0,13 | 31 % | 7 | 45 % |
| 16 | heikin_ashi_trend | Trendfolge | +5,5 % | 0,33 | −45,3 % | 0,12 | 29 % | 16 | 45 % |
| 17 | stochrsi_gekko | Mean Reversion | +4,8 % | 0,32 | −48,8 % | 0,10 | 53 % | 15 | 50 % |
| 18 | ema_cross_12_26 | Trendfolge | +4,8 % | 0,31 | −49,3 % | 0,10 | 43 % | 6 | 55 % |
| 19 | connors_rsi2 | Mean Reversion | +3,4 % | 0,31 | −9,3 % | 0,37 | 8 % | 7 | 40 % |
| 20 | dca_bot | DCA/Grid-Bot | +2,8 % | 0,31 | −57,7 % | 0,05 | 77 % | 34 | 55 % |
| 21 | pf_xs_momentum_30d_top5 | Trendfolge | +1,5 % | 0,30 | −66,6 % | 0,02 | 75 % | – | – |
| 22 | turtle_55_20 | Ausbruch | +4,2 % | 0,29 | −33,2 % | 0,13 | 22 % | 3 | 40 % |
| 23 | **buy_hold** | Buy & Hold | −3,7 % | 0,26 | −71,8 % | −0,05 | 100 % | 0 | 0 % |
| 24 | grid_bot | DCA/Grid-Bot | +3,0 % | 0,26 | −36,6 % | 0,08 | 46 % | 628 | 55 % |
| 25 | wavetrend_cross | Mean Reversion | +0,4 % | 0,21 | −52,6 % | 0,01 | 56 % | 1 | 50 % |
| 26 | adx_trend | Trendfolge | +2,1 % | 0,21 | −49,2 % | 0,04 | 23 % | 5 | 40 % |
| 27 | chandelier_exit | Trendfolge | +1,2 % | 0,21 | −51,2 % | 0,02 | 40 % | 6 | 35 % |
| 28 | sma200_filter | Trendfolge | −0,3 % | 0,20 | −54,7 % | −0,00 | 43 % | 5 | 35 % |
| 29 | ut_bot | Trendfolge | +0,6 % | 0,19 | −57,7 % | 0,01 | 44 % | 20 | 25 % |
| 30 | tsmom_30 | Trendfolge | +0,1 % | 0,19 | −59,8 % | 0,00 | 46 % | 17 | 45 % |
| 31 | supertrend_10_3 | Trendfolge | +0,3 % | 0,19 | −55,6 % | 0,01 | 42 % | 4 | 30 % |
| 32 | hull_trend | Trendfolge | −0,0 % | 0,18 | −48,6 % | −0,00 | 47 % | 8 | 40 % |
| 33 | sma_cross_10_20 | Trendfolge | −0,7 % | 0,17 | −58,2 % | −0,01 | 47 % | 10 | 35 % |
| 34 | rsi_gekko | Mean Reversion | −1,0 % | 0,15 | −46,1 % | −0,02 | 47 % | 1 | 45 % |
| 35 | macd_gekko | Trendfolge | −5,6 % | 0,06 | −68,7 % | −0,08 | 53 % | 13 | 30 % |
| 36 | williams_r | Mean Reversion | −5,0 % | 0,05 | −42,9 % | −0,12 | 45 % | 9 | 30 % |
| 37 | cci_gekko | Mean Reversion | −7,4 % | 0,04 | −52,7 % | −0,14 | 53 % | 7 | 40 % |
| 38 | golden_cross_50_200 | Trendfolge | −7,9 % | 0,01 | −52,5 % | −0,15 | 44 % | 1 | 20 % |
| 39 | ml_random_forest | ML-Vorhersage | −6,2 % | 0,01 | −39,2 % | −0,16 | 49 % | 43 | 30 % |
| 40 | parabolic_sar | Trendfolge | −7,4 % | −0,03 | −60,0 % | −0,12 | 47 % | 14 | 20 % |
| 41 | bollinger_reversion | Mean Reversion | −9,4 % | −0,04 | −47,4 % | −0,20 | 51 % | 4 | 35 % |
| 42 | ft_multi_ma | Trendfolge | −0,8 % | −0,04 | −12,8 % | −0,06 | 3 % | 2 | 35 % |
| 43 | ml_freqai_lightgbm | ML-Vorhersage | −8,6 % | −0,05 | −51,1 % | −0,17 | 58 % | 22 | 20 % |
| 44 | ml_lstm | ML-Vorhersage | −11,2 % | −0,13 | −49,6 % | −0,23 | 51 % | 18 | 20 % |
| 45 | ml_logistic | ML-Vorhersage | −11,7 % | −0,16 | −46,4 % | −0,25 | 48 % | 46 | 25 % |
| 46 | ft_supertrend | Trendfolge | −9,2 % | −0,21 | −41,4 % | −0,22 | 27 % | 25 | 25 % |
| 47 | **own_v02_follow_best** | Eigener Bot | −6,5 % | −0,26 | −34,5 % | −0,19 | 25 % | 12 | 30 % |
| 48 | ml_lorentzian_knn | ML-Vorhersage | −3,0 % | −0,26 | −16,4 % | −0,18 | 7 % | 9 | 35 % |
| 49 | ft_universal_macd | Mean Reversion | −4,5 % | −0,55 | −17,2 % | −0,26 | 9 % | 7 | 30 % |
| 50 | ft_adx_momentum | Trendfolge | −12,3 % | −0,64 | −36,0 % | −0,34 | 14 % | 25 | 10 % |
| 51 | ft_hlhb | Trendfolge | −3,9 % | −0,68 | −17,0 % | −0,23 | 5 % | 3 | 30 % |
| 52 | ft_trend_following | Trendfolge | −23,6 % | −0,83 | −65,9 % | −0,36 | 41 % | 11 | 5 % |
| 53 | ft_adx_smas | Trendfolge | −23,5 % | −0,85 | −58,3 % | −0,40 | 31 % | 9 | 15 % |
| 54 | ml_ar_forecast | ML-Vorhersage | −34,0 % | −0,86 | −72,6 % | −0,47 | 54 % | 74 | 5 % |
| 55 | ft_combined_binh_cluc | Mean Reversion | −16,8 % | −1,33 | −43,2 % | −0,39 | 4 % | 17 | 5 % |
| 56 | ft_strategy005 † | Mean Reversion | +0,3 % | 1,04 | +0,0 % | – | 0 % | 0 | 45 % |
| 57 | ft_strategy003 † | Mean Reversion | +0,2 % | 0,85 | +0,0 % | – | 0 % | 0 | 35 % |
| 58 | ft_strategy002 † | Mean Reversion | +0,2 % | 0,64 | −0,1 % | 3,54 | 0 % | 0 | 40 % |
| 59 | ft_sample_strategy † | Mean Reversion | +1,6 % | 0,63 | −2,6 % | 0,61 | 1 % | 2 | 55 % |
| 60 | ft_strategy001 † | Trendfolge | −0,3 % | −0,12 | −3,3 % | −0,10 | 2 % | 3 | 35 % |
| 61 | ft_strategy004 † | Mean Reversion | −1,1 % | −0,87 | −3,4 % | −0,31 | 1 % | 1 | 40 % |
| 62 | ft_binhv45 † | Mean Reversion | −1,9 % | −1,55 | −5,3 % | −0,36 | 0 % | 1 | 15 % |
| 63 | ft_clucmay72018 † | Mean Reversion | −19,8 % | −2,58 | −46,4 % | −0,43 | 0 % | 13 | 0 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.

## Out-of-Sample 2024–2026 – 4h

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **rotation_bot_v1** | Eigener Bot | +30,7 % | 0,76 | −44,9 % | 0,68 | 50 % | – | – |
| 2 | ft_multi_ma | Trendfolge | +8,0 % | 0,70 | −17,2 % | 0,47 | 6 % | 7 | 55 % |
| 3 | keltner_breakout | Ausbruch | +11,9 % | 0,61 | −31,1 % | 0,38 | 18 % | 23 | 55 % |
| 4 | **own_v04_vol_target** | Eigener Bot | +9,6 % | 0,60 | −20,2 % | 0,47 | 25 % | 23 | 80 % |
| 5 | **trend_bot_v1** | Eigener Bot | +12,2 % | 0,52 | −40,6 % | 0,30 | 32 % | 13 | 50 % |
| 6 | wavetrend_cross | Mean Reversion | +13,0 % | 0,50 | −44,0 % | 0,29 | 52 % | 8 | 75 % |
| 7 | turtle_55_20 | Ausbruch | +8,8 % | 0,46 | −38,5 % | 0,23 | 22 % | 17 | 55 % |
| 8 | **rotation_v0_plain** | Eigener Bot | +12,2 % | 0,45 | −54,0 % | 0,23 | 71 % | – | – |
| 9 | pf_xs_momentum_90d_top5 | Trendfolge | +11,7 % | 0,44 | −55,8 % | 0,21 | 68 % | – | – |
| 10 | bollinger_breakout | Ausbruch | +8,0 % | 0,41 | −44,4 % | 0,18 | 26 % | 39 | 50 % |
| 11 | ichimoku | Trendfolge | +8,0 % | 0,40 | −50,6 % | 0,16 | 34 % | 36 | 50 % |
| 12 | **own_v05_fast_trend** | Eigener Bot | +6,8 % | 0,36 | −47,7 % | 0,14 | 38 % | 21 | 55 % |
| 13 | dca_bot | DCA/Grid-Bot | +5,1 % | 0,36 | −58,5 % | 0,09 | 78 % | 67 | 60 % |
| 14 | **own_v01_all_bots** | Eigener Bot | +4,3 % | 0,31 | −32,3 % | 0,13 | 31 % | 0 | 45 % |
| 15 | squeeze_momentum | Ausbruch | +3,2 % | 0,29 | −24,2 % | 0,13 | 11 % | 32 | 40 % |
| 16 | hull_trend | Trendfolge | +3,4 % | 0,28 | −64,5 % | 0,05 | 49 % | 52 | 50 % |
| 17 | pf_xs_momentum_30d_top5 | Trendfolge | +1,5 % | 0,28 | −66,5 % | 0,02 | 75 % | – | – |
| 18 | **own_v03_slow_trend** | Eigener Bot | +2,6 % | 0,25 | −51,2 % | 0,05 | 43 % | 23 | 45 % |
| 19 | sma_cross_10_20 | Trendfolge | +2,0 % | 0,25 | −65,1 % | 0,03 | 49 % | 60 | 50 % |
| 20 | sma200_filter | Trendfolge | +2,2 % | 0,24 | −58,0 % | 0,04 | 45 % | 36 | 40 % |
| 21 | **buy_hold** | Buy & Hold | −5,2 % | 0,24 | −71,9 % | −0,07 | 100 % | 0 | 0 % |
| 22 | supertrend_10_3 | Trendfolge | +1,7 % | 0,23 | −59,8 % | 0,03 | 46 % | 25 | 50 % |
| 23 | golden_cross_50_200 | Trendfolge | +0,3 % | 0,19 | −50,4 % | 0,01 | 45 % | 7 | 35 % |
| 24 | ema_cross_12_26 | Trendfolge | −0,0 % | 0,19 | −65,8 % | −0,00 | 47 % | 38 | 40 % |
| 25 | turtle_20_10 | Ausbruch | +1,1 % | 0,18 | −50,7 % | 0,02 | 31 % | 33 | 35 % |
| 26 | adx_trend | Trendfolge | +0,7 % | 0,16 | −42,4 % | 0,02 | 24 % | 32 | 45 % |
| 27 | rsi_gekko | Mean Reversion | −2,3 % | 0,15 | −41,7 % | −0,06 | 50 % | 9 | 35 % |
| 28 | tsmom_90 | Trendfolge | −1,7 % | 0,15 | −61,8 % | −0,03 | 47 % | 50 | 40 % |
| 29 | chandelier_exit | Trendfolge | −1,6 % | 0,14 | −64,4 % | −0,03 | 47 % | 35 | 35 % |
| 30 | ft_bband_rsi | Mean Reversion | −1,3 % | 0,13 | −35,7 % | −0,04 | 37 % | 13 | 50 % |
| 31 | parabolic_sar | Trendfolge | −2,6 % | 0,12 | −56,7 % | −0,05 | 50 % | 90 | 40 % |
| 32 | tsmom_30 | Trendfolge | −4,2 % | 0,08 | −67,8 % | −0,06 | 47 % | 90 | 45 % |
| 33 | macd_gekko | Trendfolge | −7,2 % | 0,02 | −60,9 % | −0,12 | 52 % | 86 | 30 % |
| 34 | ft_adx_smas | Trendfolge | −7,8 % | −0,07 | −46,9 % | −0,17 | 42 % | 33 | 30 % |
| 35 | ml_freqai_lightgbm | ML-Vorhersage | −7,7 % | −0,10 | −38,4 % | −0,20 | 42 % | 104 | 25 % |
| 36 | grid_bot | DCA/Grid-Bot | −8,5 % | −0,11 | −50,2 % | −0,17 | 46 % | 1089 | 5 % |
| 37 | bollinger_reversion | Mean Reversion | −13,4 % | −0,13 | −48,9 % | −0,27 | 51 % | 25 | 20 % |
| 38 | ut_bot | Trendfolge | −17,1 % | −0,29 | −69,1 % | −0,25 | 48 % | 121 | 20 % |
| 39 | ft_sample_strategy | Mean Reversion | −3,4 % | −0,35 | −15,5 % | −0,22 | 6 % | 16 | 25 % |
| 40 | **own_v02_follow_best** | Eigener Bot | −7,9 % | −0,37 | −35,7 % | −0,22 | 23 % | 37 | 20 % |
| 41 | ft_supertrend | Trendfolge | −16,3 % | −0,38 | −59,2 % | −0,28 | 40 % | 53 | 25 % |
| 42 | heikin_ashi_trend | Trendfolge | −15,4 % | −0,43 | −62,9 % | −0,25 | 31 % | 107 | 25 % |
| 43 | cci_gekko | Mean Reversion | −25,1 % | −0,45 | −64,1 % | −0,39 | 53 % | 41 | 10 % |
| 44 | ft_hlhb | Trendfolge | −5,1 % | −0,49 | −22,3 % | −0,23 | 11 % | 15 | 35 % |
| 45 | williams_r | Mean Reversion | −25,3 % | −0,58 | −59,2 % | −0,43 | 43 % | 51 | 10 % |
| 46 | ft_trend_following | Trendfolge | −32,0 % | −0,59 | −76,0 % | −0,42 | 74 % | 26 | 5 % |
| 47 | connors_rsi2 | Mean Reversion | −8,3 % | −0,64 | −28,8 % | −0,29 | 9 % | 42 | 20 % |
| 48 | ft_strategy001 | Trendfolge | −4,9 % | −0,75 | −18,1 % | −0,27 | 8 % | 17 | 35 % |
| 49 | ft_universal_macd | Mean Reversion | −16,0 % | −0,81 | −45,1 % | −0,35 | 21 % | 39 | 20 % |
| 50 | ft_adx_momentum | Trendfolge | −27,2 % | −1,10 | −64,1 % | −0,42 | 33 % | 90 | 0 % |
| 51 | stochrsi_gekko | Mean Reversion | −38,8 % | −1,13 | −77,2 % | −0,50 | 49 % | 79 | 5 % |
| 52 | ml_lstm | ML-Vorhersage | −43,1 % | −1,29 | −82,7 % | −0,52 | 49 % | 195 | 5 % |
| 53 | ml_lorentzian_knn | ML-Vorhersage | −14,2 % | −1,34 | −39,6 % | −0,36 | 8 % | 56 | 15 % |
| 54 | ft_combined_binh_cluc | Mean Reversion | −26,1 % | −1,36 | −59,3 % | −0,44 | 11 % | 45 | 5 % |
| 55 | ml_logistic | ML-Vorhersage | −51,4 % | −1,65 | −88,8 % | −0,58 | 53 % | 288 | 0 % |
| 56 | ml_random_forest | ML-Vorhersage | −54,5 % | −1,90 | −89,9 % | −0,61 | 53 % | 290 | 5 % |
| 57 | ml_ar_forecast | ML-Vorhersage | −80,8 % | −4,30 | −99,0 % | −0,82 | 53 % | 555 | 0 % |
| 58 | ft_strategy003 † | Mean Reversion | +0,5 % | 0,49 | −1,2 % | 0,39 | 0 % | 1 | 60 % |
| 59 | ft_strategy005 † | Mean Reversion | −0,7 % | −0,30 | −4,8 % | −0,15 | 1 % | 1 | 45 % |
| 60 | ft_strategy004 † | Mean Reversion | −2,0 % | −0,48 | −8,7 % | −0,23 | 1 % | 4 | 30 % |
| 61 | ft_strategy002 † | Mean Reversion | −1,0 % | −0,75 | −3,6 % | −0,27 | 0 % | 1 | 50 % |
| 62 | ft_binhv45 † | Mean Reversion | −4,8 % | −1,28 | −14,8 % | −0,32 | 1 % | 7 | 15 % |
| 63 | ft_clucmay72018 † | Mean Reversion | −19,2 % | −1,75 | −46,0 % | −0,42 | 2 % | 35 | 5 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.

## Out-of-Sample 2024–2026 – 1h

| # | Bot | Familie | CAGR | Sharpe | Max. DD | Calmar | Zeit im Markt | Trades/Jahr | schlägt B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **rotation_bot_v1** | Eigener Bot | +29,7 % | 0,75 | −44,7 % | 0,67 | 50 % | – | – |
| 2 | **trend_bot_v1** | Eigener Bot | +11,9 % | 0,51 | −43,3 % | 0,28 | 33 % | 24 | 55 % |
| 3 | **rotation_v0_plain** | Eigener Bot | +12,2 % | 0,45 | −54,7 % | 0,22 | 71 % | – | – |
| 4 | pf_xs_momentum_90d_top5 | Trendfolge | +11,7 % | 0,44 | −56,2 % | 0,21 | 68 % | – | – |
| 5 | **own_v04_vol_target** | Eigener Bot | +6,1 % | 0,43 | −23,6 % | 0,26 | 25 % | 44 | 65 % |
| 6 | ft_multi_ma | Trendfolge | +3,0 % | 0,32 | −21,6 % | 0,14 | 6 % | 17 | 45 % |
| 7 | dca_bot | DCA/Grid-Bot | +2,1 % | 0,31 | −60,7 % | 0,04 | 81 % | 69 | 65 % |
| 8 | **own_v05_fast_trend** | Eigener Bot | +4,5 % | 0,30 | −50,3 % | 0,09 | 39 % | 50 | 45 % |
| 9 | pf_xs_momentum_30d_top5 | Trendfolge | +1,5 % | 0,27 | −66,5 % | 0,02 | 75 % | – | – |
| 10 | **buy_hold** | Buy & Hold | −5,1 % | 0,24 | −72,2 % | −0,07 | 100 % | 0 | 0 % |
| 11 | golden_cross_50_200 | Trendfolge | +1,3 % | 0,22 | −64,7 % | 0,02 | 47 % | 28 | 40 % |
| 12 | **own_v03_slow_trend** | Eigener Bot | −3,3 % | 0,09 | −55,9 % | −0,06 | 43 % | 44 | 20 % |
| 13 | turtle_55_20 | Ausbruch | −4,1 % | −0,03 | −43,0 % | −0,09 | 23 % | 68 | 45 % |
| 14 | **own_v01_all_bots** | Eigener Bot | −3,1 % | −0,04 | −40,1 % | −0,08 | 33 % | 0 | 10 % |
| 15 | wavetrend_cross | Mean Reversion | −10,1 % | −0,05 | −43,3 % | −0,23 | 52 % | 30 | 20 % |
| 16 | ft_universal_macd | Mean Reversion | −6,1 % | −0,16 | −36,4 % | −0,17 | 24 % | 61 | 35 % |
| 17 | keltner_breakout | Ausbruch | −6,5 % | −0,19 | −36,8 % | −0,18 | 18 % | 88 | 35 % |
| 18 | rsi_gekko | Mean Reversion | −15,4 % | −0,20 | −56,5 % | −0,27 | 52 % | 32 | 15 % |
| 19 | grid_bot | DCA/Grid-Bot | −11,8 % | −0,25 | −51,8 % | −0,23 | 46 % | 1338 | 15 % |
| 20 | ft_trend_following | Trendfolge | −26,2 % | −0,27 | −75,6 % | −0,35 | 90 % | 38 | 5 % |
| 21 | ichimoku | Trendfolge | −13,9 % | −0,29 | −64,2 % | −0,22 | 35 % | 147 | 30 % |
| 22 | ml_freqai_lightgbm | ML-Vorhersage | −9,8 % | −0,33 | −36,9 % | −0,27 | 21 % | 145 | 25 % |
| 23 | ft_strategy004 | Mean Reversion | −2,0 % | −0,35 | −13,3 % | −0,15 | 3 % | 16 | 35 % |
| 24 | ft_bband_rsi | Mean Reversion | −20,2 % | −0,41 | −61,0 % | −0,33 | 48 % | 34 | 15 % |
| 25 | supertrend_10_3 | Trendfolge | −22,0 % | −0,44 | −72,9 % | −0,30 | 48 % | 104 | 10 % |
| 26 | sma200_filter | Trendfolge | −24,0 % | −0,53 | −77,8 % | −0,31 | 47 % | 151 | 20 % |
| 27 | bollinger_reversion | Mean Reversion | −26,3 % | −0,54 | −68,2 % | −0,39 | 53 % | 100 | 15 % |
| 28 | chandelier_exit | Trendfolge | −27,9 % | −0,61 | −74,5 % | −0,37 | 49 % | 142 | 5 % |
| 29 | ema_cross_12_26 | Trendfolge | −27,8 % | −0,62 | −78,7 % | −0,35 | 49 % | 153 | 10 % |
| 30 | ft_supertrend | Trendfolge | −23,6 % | −0,64 | −68,7 % | −0,34 | 41 % | 105 | 5 % |
| 31 | bollinger_breakout | Ausbruch | −20,2 % | −0,67 | −59,0 % | −0,34 | 27 % | 159 | 10 % |
| 32 | turtle_20_10 | Ausbruch | −22,8 % | −0,68 | −60,4 % | −0,38 | 33 % | 135 | 15 % |
| 33 | hull_trend | Trendfolge | −35,1 % | −0,84 | −77,8 % | −0,45 | 49 % | 206 | 5 % |
| 34 | ft_combined_binh_cluc | Mean Reversion | −18,7 % | −0,87 | −52,6 % | −0,36 | 9 % | 71 | 20 % |
| 35 | adx_trend | Trendfolge | −24,1 % | −0,95 | −62,8 % | −0,38 | 25 % | 125 | 20 % |
| 36 | **own_v02_follow_best** | Eigener Bot | −15,1 % | −0,96 | −42,5 % | −0,35 | 20 % | 77 | 10 % |
| 37 | sma_cross_10_20 | Trendfolge | −39,0 % | −0,98 | −79,4 % | −0,49 | 48 % | 241 | 0 % |
| 38 | ft_adx_smas | Trendfolge | −36,4 % | −1,11 | −78,9 % | −0,46 | 44 % | 117 | 0 % |
| 39 | tsmom_90 | Trendfolge | −43,1 % | −1,27 | −88,4 % | −0,49 | 48 % | 210 | 5 % |
| 40 | ft_hlhb | Trendfolge | −20,4 % | −1,29 | −49,0 % | −0,42 | 23 % | 55 | 0 % |
| 41 | cci_gekko | Mean Reversion | −49,6 % | −1,52 | −86,8 % | −0,57 | 51 % | 169 | 5 % |
| 42 | ft_strategy005 | Mean Reversion | −12,9 % | −1,64 | −32,6 % | −0,40 | 6 % | 12 | 10 % |
| 43 | ft_sample_strategy | Mean Reversion | −23,4 % | −1,69 | −53,9 % | −0,43 | 17 % | 48 | 5 % |
| 44 | ft_strategy001 | Trendfolge | −24,1 % | −1,85 | −55,1 % | −0,44 | 23 % | 56 | 15 % |
| 45 | squeeze_momentum | Ausbruch | −23,2 % | −1,97 | −53,0 % | −0,44 | 11 % | 122 | 15 % |
| 46 | williams_r | Mean Reversion | −52,0 % | −2,01 | −87,6 % | −0,59 | 45 % | 215 | 0 % |
| 47 | macd_gekko | Trendfolge | −62,0 % | −2,08 | −93,7 % | −0,66 | 50 % | 343 | 0 % |
| 48 | ft_adx_momentum | Trendfolge | −44,6 % | −2,11 | −81,3 % | −0,55 | 37 % | 203 | 5 % |
| 49 | parabolic_sar | Trendfolge | −64,2 % | −2,31 | −94,8 % | −0,68 | 48 % | 369 | 0 % |
| 50 | stochrsi_gekko | Mean Reversion | −62,0 % | −2,39 | −94,1 % | −0,66 | 47 % | 316 | 0 % |
| 51 | tsmom_30 | Trendfolge | −68,8 % | −2,71 | −96,2 % | −0,71 | 49 % | 375 | 0 % |
| 52 | ut_bot | Trendfolge | −78,1 % | −3,62 | −98,6 % | −0,79 | 52 % | 510 | 0 % |
| 53 | connors_rsi2 | Mean Reversion | −33,5 % | −3,63 | −68,4 % | −0,49 | 7 % | 174 | 5 % |
| 54 | heikin_ashi_trend | Trendfolge | −74,0 % | −4,42 | −97,6 % | −0,76 | 35 % | 460 | 0 % |
| 55 | ml_lorentzian_knn | ML-Vorhersage | −48,0 % | −6,09 | −83,7 % | −0,57 | 5 % | 223 | 5 % |
| 56 | ml_logistic | ML-Vorhersage | −92,3 % | −6,65 | −99,9 % | −0,92 | 46 % | 994 | 0 % |
| 57 | ml_lstm | ML-Vorhersage | −93,3 % | −7,12 | −99,9 % | −0,93 | 39 % | 960 | 0 % |
| 58 | ml_random_forest | ML-Vorhersage | −93,9 % | −7,44 | −100,0 % | −0,94 | 40 % | 1029 | 0 % |
| 59 | ml_ar_forecast | ML-Vorhersage | −99,4 % | −13,01 | −100,0 % | −0,99 | 44 % | 1620 | 0 % |
| 60 | ft_binhv45 † | Mean Reversion | −0,8 % | −0,16 | −9,3 % | −0,08 | 1 % | 14 | 45 % |
| 61 | ft_strategy003 † | Mean Reversion | −3,3 % | −0,91 | −11,8 % | −0,28 | 2 % | 5 | 25 % |
| 62 | ft_clucmay72018 † | Mean Reversion | −16,4 % | −1,56 | −41,4 % | −0,40 | 2 % | 47 | 10 % |
| 63 | ft_strategy002 † | Mean Reversion | −2,3 % | −1,70 | −6,5 % | −0,36 | 1 % | 2 | 35 % |

† weniger als 2 % der Zeit investiert – die Kennzahlen beruhen auf sehr wenigen Trades und sind kaum aussagekräftig.
