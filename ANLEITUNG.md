# Anleitung: Trading-Bot-V1.0 Schritt für Schritt

Diese Anleitung führt dich von null bis zum laufenden Bot.

**Wichtig vorab:** Du gehst in drei Stufen vor und wechselst erst zur nächsten, wenn die vorige sauber läuft:

| Stufe | Was passiert | Risiko |
|---|---|---|
| **A – Backtest** | Der Bot rechnet aus, wie er sich in der Vergangenheit geschlagen hätte | keins |
| **B – Paper-Trading** | Der Bot handelt **simuliert** mit echten Live-Kursen | keins |
| **C – Live-Trading** | Der Bot handelt mit **echtem Geld** an der Börse | **Totalverlust möglich** |

Empfehlung: Lass Stufe B **mindestens 2–3 Monate** laufen, bevor du über Stufe C nachdenkst.
Das ist keine Anlageberatung.

Die Befehle stehen jeweils für **Windows** (PowerShell) und für **macOS/Linux** (Terminal) da.

---

## Teil 1 – Installation (einmalig, ca. 10 Minuten)

### Schritt 1: Python installieren

Du brauchst **Python 3.11 oder 3.12** (3.10 bis 3.13 funktionieren auch).

**Windows**

1. Öffne <https://www.python.org/downloads/> und lade den Installer herunter.
2. Setze im Installer unbedingt den Haken bei **„Add python.exe to PATH“** und klicke dann auf „Install Now“.
3. Öffne die **PowerShell** (Startmenü → „PowerShell“ eintippen) und prüfe die Installation:

```powershell
python --version
```

Erwartet wird etwa `Python 3.12.x`.

**macOS**

Installiere Python über den Installer von python.org oder per Homebrew (`brew install python@3.12`). Prüfe dann im Terminal:

```bash
python3 --version
```

**Linux (Ubuntu/Debian)**

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
python3 --version
```

### Schritt 2: Den Code herunterladen

Der Bot liegt im Branch **`claude/trading-bot-v1`** deines Repositorys.

**Variante A – mit Git** (Windows: Git von <https://git-scm.com> installieren):

```bash
git clone -b claude/trading-bot-v1 https://github.com/Gencoooo/Trading-Bot-V1.0.git
cd Trading-Bot-V1.0
```

Ist das Repository privat, fragt Git nach deinem GitHub-Login.

**Variante B – ohne Git:**

1. Öffne dein Repository auf GitHub.
2. Wähle links oben im Branch-Menü `claude/trading-bot-v1`.
3. Klicke auf den grünen Knopf **Code → Download ZIP**.
4. Entpacke die ZIP-Datei und öffne im entpackten Ordner ein Terminal bzw. eine PowerShell.

> Alle folgenden Befehle führst du **im Ordner `Trading-Bot-V1.0`** aus.

### Schritt 3: Virtuelle Umgebung anlegen und Pakete installieren

Eine virtuelle Umgebung hält die Pakete des Bots getrennt von deinem restlichen System.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Meldet PowerShell *„Die Ausführung von Skripts ist auf diesem System deaktiviert“*, führst du einmalig
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` aus, bestätigst mit `J` und aktivierst erneut.

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Wenn vorne in der Eingabezeile **`(.venv)`** steht, ist die Umgebung aktiv.

> **Merke:** In jedem neuen Terminal-Fenster musst du die Umgebung erneut aktivieren:
> Windows `.venv\Scripts\Activate.ps1`, macOS/Linux `source .venv/bin/activate`.

### Schritt 4: Installation prüfen

```bash
python -m trading_bot list
```

Es erscheint eine lange Liste aller Bots, darunter `rotation_bot_v1` und `trend_bot_v1`.

Optional kannst du auch die Testsuite starten:

```bash
python -m pytest -q
```

Sie läuft etwa 30 Sekunden und sollte nur „passed“ melden. Ein paar „skipped“ sind normal.

---

## Teil 2 – Stufe A: Den Bot ohne Risiko ausprobieren

### Schritt 5: Marktdaten laden

```bash
python -m trading_bot fetch --intervals 1d
```

Das lädt die Tageskerzen von 20 Coins und dauert etwa eine Minute. Die Daten landen in `data/cache/`.
Für die 4h- und 1h-Kerzen lässt du `--intervals 1d` weg; das dauert dann etwa 10 Minuten.

### Schritt 6: Den empfohlenen Portfolio-Bot testen

```bash
python -m trading_bot portfolio --strategy rotation_bot_v1
```

Du siehst drei Blöcke: **Gesamt**, **bis 2023** und **ab 2024**. Jeder Block vergleicht den Bot mit
„alle Coins gleich gewichtet halten“. Ganz unten steht, welche Coins der Bot **aktuell** halten würde.

So liest du die Kennzahlen:

| Kennzahl | Bedeutung |
|---|---|
| **CAGR** | durchschnittliche Rendite pro Jahr |
| **Sharpe** | Rendite im Verhältnis zur Schwankung (höher ist besser, über 1 ist gut) |
| **Max. Drawdown** | größter zwischenzeitlicher Verlust vom Höchststand |
| **Calmar** | CAGR geteilt durch Max. Drawdown (höher ist besser) |

### Schritt 7 (optional): Den Einzel-Coin-Bot testen

```bash
python -m trading_bot backtest --strategy trend_bot_v1 --symbol BTCUSDT --interval 1d
python -m trading_bot backtest --strategy trend_bot_v1 --symbol ETHUSDT --interval 1d --trades 10
python -m trading_bot backtest --strategy trend_bot_v1 --symbol SOLUSDT --interval 1d --start 2024-01-01
```

* `--trades 10` zeigt die letzten 10 Trades.
* `--start` und `--end` schränken den Zeitraum ein.

Mit `--strategy` kannst du jeden Bot aus `python -m trading_bot list` testen.

---

## Teil 3 – Stufe B: Paper-Trading (simuliert, echte Kurse)

Beim Paper-Trading holt sich der Bot die **aktuellen Kurse von Binance** und führt seine Käufe und
Verkäufe in einem **simulierten Konto** aus. Gebühren und Slippage werden mitgerechnet.
Du brauchst dafür kein Börsenkonto und keinen API-Key.

### Schritt 8: Der erste Lauf

```bash
python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once
```

Was dabei passiert:

* Ein simuliertes Konto mit **10.000 USDT** wird angelegt. Ein anderes Startkapital wählst du mit `--capital 1000`.
* Der Bot **kauft sofort** die Coins, die er laut Strategie gerade halten soll (meist 5 Coins).
* Der Kontostand wird in `state/paper_rotation_bot_v1_1d.json` gespeichert.

Die Ausgabe sieht zum Beispiel so aus:

```
 Modus:      PAPER (simuliert, Zustand in state/paper_rotation_bot_v1_1d.json)
 Strategie:  rotation_bot_v1  (Portfolio)
 Nächste Prüfung:      Samstag, 10.10.2026 um 02:00 Uhr Ortszeit (00:00 UTC)
 Nächste Umschichtung: Donnerstag, 15.10.2026 um 02:00 Uhr Ortszeit (00:00 UTC)
 SOLUSDT Ziel=27.4% vorher=0.0% -> Kauf 25.0134
 ...
```

### Schritt 9: Den Kontostand ansehen

```bash
python -m trading_bot status
```

Der Status zeigt:

* den aktuellen Wert und die Veränderung seit dem Start,
* jede Position mit Menge, Preis und Anteil,
* die letzten Trades.

Diesen Befehl kannst du jederzeit ausführen, auch während der Bot läuft.

### Schritt 10: Den Bot dauerhaft laufen lassen

So arbeitet `rotation_bot_v1`:

* Er **prüft einmal täglich**, kurz nach Kerzenschluss um **00:00 UTC**. In Deutschland ist das 02:00 Uhr (Sommerzeit) bzw. 01:00 Uhr (Winterzeit).
* Er **schichtet nur einmal pro Woche um**, in der Nacht auf **Donnerstag**. An den anderen Tagen passiert nichts.
* War der Bot am Umschichtungstag nicht aktiv, **holt er die Umschichtung beim nächsten Lauf nach**.

Für den Dauerbetrieb hast du zwei Möglichkeiten.

**Variante 1 – einfach: das Fenster offen lassen**

```bash
python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d
```

* Der Bot läuft, bis du ihn mit **Strg+C** beendest. Beim nächsten Start macht er dort weiter, wo er aufgehört hat.
* Der Rechner darf dabei **nicht in den Ruhezustand** gehen. Unter Windows stellst du das unter Einstellungen → System → Energie ein.

**Variante 2 – robuster: automatisch einmal täglich per Zeitplan**

Der Rechner muss dafür nicht durchgehend an sein. Der Bot wird jeden Tag um **02:15 Uhr** gestartet,
erledigt seine Prüfung und beendet sich wieder. 02:15 Uhr liegt im Sommer wie im Winter nach 00:00 UTC.

*Windows – Aufgabenplanung:*

1. Startmenü → **„Aufgabenplanung“** → rechts **„Einfache Aufgabe erstellen…“**.
2. Name: `Trading-Bot`, Trigger: **Täglich**, Uhrzeit **02:15**.
3. Aktion: **„Programm starten“**.
   * Programm/Skript: `C:\Pfad\zu\Trading-Bot-V1.0\.venv\Scripts\python.exe`
   * Argumente: `-m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once`
   * Starten in: `C:\Pfad\zu\Trading-Bot-V1.0`
4. In den Eigenschaften der Aufgabe aktivierst du **„Aufgabe so schnell wie möglich nach einem verpassten Start ausführen“** und, falls gewünscht, „Computer zum Ausführen der Aufgabe reaktivieren“.

*macOS/Linux – cron:*

```bash
crontab -e
```

Füge diese Zeile hinzu und passe den Pfad an:

```
15 2 * * * cd /pfad/zu/Trading-Bot-V1.0 && .venv/bin/python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once >> bot.log 2>&1
```

In `bot.log` siehst du später, was der Bot jeweils gemacht hat.

> **Tipp:** Für echten 24/7-Betrieb eignet sich ein Raspberry Pi oder ein kleiner Cloud-Server
> (ab ca. 4–5 € im Monat). Die Installation dort folgt Teil 1 für Linux.

### Schritt 11: Nützliche Optionen fürs Paper-Trading

| Ziel | Befehl bzw. Zusatz |
|---|---|
| Konto zurücksetzen und neu starten | `--reset` |
| Anderes Startkapital | `--capital 1000` (gilt nur bei neuem Konto bzw. mit `--reset`) |
| Mehrere Testkonten parallel | `--name meinTest` (Status: `python -m trading_bot status --name meinTest`) |
| Nur bestimmte Coins | `--symbols BTCUSDT ETHUSDT SOLUSDT` (Bitcoin sollte für den Marktfilter dabei sein) |
| Einzel-Coin-Bot statt Portfolio-Bot | `--strategy trend_bot_v1 --symbols BTCUSDT` |
| USDC- statt USDT-Paare | `--quote USDC` (eigene Coin-Liste dann z. B. `--symbols BTCUSDC ETHUSDC`) |

---

## Teil 4 – Stufe C: Live-Trading mit echtem Geld (optional)

> ⚠️ Nur mit Geld, dessen **Totalverlust** du verkraften kannst. Im Backtest lag der größte
> zwischenzeitliche Verlust des Bots bei **−45 %**, und die Zukunft kann schlechter sein.
> Der Live-Modus ist programmiert und mit simulierten Börsen getestet, aber **noch nicht mit einem
> echten Börsenkonto**. Gehe deshalb unbedingt über das Testnet (Schritt 13).

### Schritt 12: Vorbereitung

1. Installiere die Börsen-Bibliothek:

   ```bash
   pip install ccxt
   ```

2. **Wähle die richtige Quote-Währung.** In der EU sind USDT-Handelspaare wegen der MiCA-Regulierung bei vielen Börsen eingeschränkt. Alle 17 Coins des Bots gibt es bei Binance auch gegen **USDC**. Für EU-Konten verwendest du deshalb `--quote USDC`.

3. Lege für den Bot ein **eigenes Konto oder Unterkonto** an.
   Der Bot betrachtet **das gesamte USDC-Guthaben und alle Coins seiner Liste im Konto als seine eigenen**. Liegen dort andere Coins, kann er sie verkaufen.
   Mit `--max-capital 500` verwaltet er höchstens 500 USDC.

4. Plane **mindestens 200–500 USDC** ein. Der Bot hält bis zu 5 Coins, und Binance verlangt pro Order einen Mindestbetrag (der Bot handelt erst ab 10 USDC pro Order).

### Schritt 13: Testnet – Spielgeld an der echten Börsen-Schnittstelle

1. Öffne <https://testnet.binance.vision>, melde dich mit GitHub an und erzeuge einen **API-Key** (HMAC).
2. Hinterlege Key und Secret als Umgebungsvariablen. Sie gelten nur für das aktuelle Fenster.

   **Windows (PowerShell)**
   ```powershell
   $env:TB_API_KEY="dein_key"
   $env:TB_API_SECRET="dein_secret"
   ```

   **macOS/Linux**
   ```bash
   export TB_API_KEY="dein_key"
   export TB_API_SECRET="dein_secret"
   ```

3. Starte einen Lauf im Testnet:

   ```bash
   python -m trading_bot paper --live --testnet --i-understand-the-risks --strategy rotation_bot_v1 --interval 1d --quote USDT --once
   ```

   Das Testnet-Guthaben liegt meist in USDT. Prüfe auf der Testnet-Seite, ob die Orders ausgeführt wurden.

### Schritt 14: Echtes Geld

1. Erstelle bei deiner Börse einen **API-Key** mit genau diesen Rechten:
   * ✅ Lesen
   * ✅ **Spot-Handel**
   * ❌ **Auszahlungen NIEMALS erlauben**
   * ✅ Zugriff möglichst auf deine **IP-Adresse beschränken**
2. Setze die Umgebungsvariablen wie in Schritt 13, diesmal mit dem echten Key.
3. Starte zunächst **einen einzelnen Lauf** und kontrolliere die Orders in der Börsen-App:

   ```bash
   python -m trading_bot paper --live --i-understand-the-risks --strategy rotation_bot_v1 --interval 1d --quote USDC --max-capital 500 --once
   ```

4. Passt alles, richtest du den Dauerbetrieb wie in Schritt 10 ein, mit denselben Zusätzen (`--live --i-understand-the-risks --quote USDC --max-capital 500`).
   Für die Aufgabenplanung bzw. cron müssen die Umgebungsvariablen dauerhaft gesetzt sein.

   *Windows:* `setx TB_API_KEY "dein_key"` und `setx TB_API_SECRET "dein_secret"` ausführen, danach ab- und wieder anmelden.

   *Linux/macOS:* Lege **außerhalb** des Projektordners ein Startskript an, zum Beispiel `~/start_bot.sh`:

   ```bash
   #!/bin/bash
   export TB_API_KEY="dein_key"
   export TB_API_SECRET="dein_secret"
   cd /pfad/zu/Trading-Bot-V1.0
   .venv/bin/python -m trading_bot paper --live --i-understand-the-risks --strategy rotation_bot_v1 \
       --interval 1d --quote USDC --max-capital 500 --once >> bot.log 2>&1
   ```

   Mach es mit `chmod 700 ~/start_bot.sh` nur für dich lesbar und trag in `crontab -e` diese Zeile ein:
   `15 2 * * * /home/DEINNAME/start_bot.sh`

   Speichere die Keys **niemals** in Dateien, die du auf GitHub hochlädst.

5. **Kontrolle im Live-Betrieb:** `python -m trading_bot status` zeigt nur Paper-Konten. Den Live-Stand siehst du in der Börsen-App, die Aktionen des Bots in `bot.log` bzw. im Fenster.

### Schritt 15: Stoppen und Aussteigen

* **Bot anhalten:** Strg+C im Fenster bzw. die geplante Aufgabe deaktivieren.
* **Wichtig:** Ein angehaltener Bot **verkauft nichts automatisch**. Willst du komplett aussteigen, verkaufst du die Coins selbst in der Börsen-App.
* **API-Key löschen**, wenn du den Bot nicht mehr nutzt.

---

## Wartung

| Was | Wie |
|---|---|
| Neue Version des Bots holen | `git pull` im Projektordner |
| Marktdaten aktualisieren (nur für Backtests nötig) | `python -m trading_bot fetch --intervals 1d` |
| Ergebnis-Bericht lesen | `reports/ERGEBNISSE.md` |
| Steuern | In Deutschland sind Gewinne aus Coins, die du weniger als ein Jahr hältst, steuerpflichtig (private Veräußerungsgeschäfte). Der Bot handelt wöchentlich, also bewahre die Trade-Historie auf: die Börsen-Export-Funktion bzw. `state/*.json` beim Paper-Trading. Im Zweifel fragst du eine Steuerberatung. |

## Häufige Probleme

| Problem | Lösung |
|---|---|
| `python` wird nicht gefunden (Windows) | Python neu installieren und den Haken „Add python.exe to PATH“ setzen. Alternativ `py -3.12` statt `python` verwenden. |
| `No module named trading_bot` | Du bist nicht im Ordner `Trading-Bot-V1.0` oder die Umgebung ist nicht aktiv (Schritt 3). |
| PowerShell: „Ausführung von Skripts deaktiviert“ | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Fehler beim Datenabruf (`451`, Zeitüberschreitung) | Internetverbindung prüfen. Binance ist in manchen Ländern gesperrt; der Bot nutzt zuerst den offiziellen Daten-Spiegel `data-api.binance.vision`. |
| „Kein neuer Umschichtungstermin“ | Normal: Der Bot schichtet nur einmal pro Woche um (Donnerstagnacht). |
| Uhrzeit stimmt nicht | Die Systemuhr muss korrekt sein (automatische Zeitsynchronisierung einschalten). |
| `Bitte zuerst die Umgebungsvariablen TB_API_KEY …` | Die Keys wurden im aktuellen Fenster nicht gesetzt (Schritt 13). |
| macOS: Fehler mit `lightgbm` beim ML-Benchmark | `brew install libomp`. Für die beiden eigenen Bots wird lightgbm nicht gebraucht. |

## Befehlsübersicht

```bash
python -m trading_bot list                                   # alle Bots
python -m trading_bot fetch --intervals 1d                   # Daten laden
python -m trading_bot portfolio --strategy rotation_bot_v1   # Backtest Portfolio-Bot
python -m trading_bot backtest --strategy trend_bot_v1 --symbol BTCUSDT --interval 1d
python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once   # ein Paper-Schritt
python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d          # Paper dauerhaft
python -m trading_bot status                                 # Paper-Kontostand
python -m trading_bot paper --help                           # alle Optionen
```
