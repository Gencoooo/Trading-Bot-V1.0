# Vorab festgelegte Auswahlregel (vor Ansicht der Out-of-Sample-Daten)

Festgelegt am 2026-10-09, bevor irgendeine OOS-Kennzahl der eigenen Varianten angesehen wurde.

1. **Einzel-Coin-Bot (`trend_bot_v1`)**: die TrendEnsemble-Variante mit der höchsten mittleren
   In-Sample-Portfolio-Sharpe über die drei Zeitebenen (1d/4h/1h), sofern ihr In-Sample-Max-Drawdown
   auf allen Zeitebenen besser als −60 % ist.
2. **Portfolio-Bot (`rotation_bot_v1`)**: die Portfolio-Variante mit der höchsten mittleren
   In-Sample-Sharpe über die drei Zeitebenen; bei Gleichstand (±0,03) entscheidet die Calmar Ratio.
3. Alle Varianten werden mit ihrer In-Sample- **und** Out-of-Sample-Leistung berichtet, auch die
   verworfenen – und auch dann, wenn eine verworfene Variante OOS besser gewesen wäre.
4. Anzahl aller getesteten Varianten fließt in die Deflated Sharpe Ratio ein.

## Ergebnis der Auswahl (ausschließlich In-Sample, vor jeder OOS-Auswertung der eigenen Varianten)

* Einzel-Coin-Bot: 30 TrendEnsemble/MetaSelector-Varianten getestet (Runde 1: 20, Runde 2: 10).
  Gewinner: `y_fast8_bin50` (mittlere IS-Sharpe 1,501; schlechtester IS-Drawdown −44 %)
  → registriert als `trend_bot_v1` = Mehrheitsabstimmung der 8 Benchmark-Gewinner-Regeln.
* Portfolio-Bot: 13 eigene Varianten + 3 Referenzen getestet.
  Gewinner: `x_rot_top5_iv_btc0_trend100` (mittlere IS-Sharpe 1,560; Calmar 2,17)
  → registriert als `rotation_bot_v1`.
