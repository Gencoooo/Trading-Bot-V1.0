#!/usr/bin/env bash
# Installiert und testet Trading-Bot-V1.0 auf Ubuntu/Debian – in einem Rutsch.
#
#   git clone -b claude/trading-bot-v1 https://github.com/Gencoooo/Trading-Bot-V1.0.git
#   cd Trading-Bot-V1.0
#   bash scripts/install_ubuntu.sh            # installieren + testen
#   bash scripts/install_ubuntu.sh --cron     # zusätzlich täglichen Paper-Lauf per cron einrichten
#
# Weitere Optionen:  --ccxt     ccxt für Testnet/Live-Handel mitinstallieren
#                    --no-apt   keine Systempakete installieren (kein sudo)
# Umgebungsvariable: PYTHON=python3.12  bestimmten Python-Interpreter verwenden
#
# Das Skript handelt nie mit echtem Geld und fragt nie nach API-Schlüsseln.
# Der Probelauf benutzt ein eigenes Paper-Konto, das danach wieder gelöscht wird.

set -euo pipefail

WITH_CRON=0
WITH_CCXT=0
WITH_APT=1
for arg in "$@"; do
    case "$arg" in
        --cron) WITH_CRON=1 ;;
        --ccxt) WITH_CCXT=1 ;;
        --no-apt) WITH_APT=0 ;;
        -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unbekannte Option: $arg (siehe --help)" >&2; exit 2 ;;
    esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
STEP="Vorbereitung"
CHECK_NAME="install_check"

step() { STEP="$1"; printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok() { printf '\033[32m    OK:\033[0m %s\n' "$1"; }
cleanup_check() { rm -f "$REPO_DIR/state/$CHECK_NAME.json" "$REPO_DIR/state/$CHECK_NAME.runner.json"; }
on_error() {
    cleanup_check
    printf '\n\033[31mFEHLER im Schritt: %s\033[0m\n' "$STEP" >&2
    echo "Die Meldung direkt darüber nennt die Ursache. Häufige Probleme: ANLEITUNG.md, Abschnitt \"Häufige Probleme\"." >&2
}
trap on_error ERR

cd "$REPO_DIR"
if [[ ! -f trading_bot/__main__.py ]]; then
    echo "Das Skript muss im Ordner scripts/ des Trading-Bot-V1.0-Repositorys liegen." >&2
    exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
    echo "Hinweis: Du arbeitest als root. Empfohlen ist ein normales Benutzerkonto (sudo nur für apt)."
fi

# ---------------------------------------------------------------------------
step "1/7 Systempakete (Python, venv, pip, git, libgomp für LightGBM)"
if [[ "$WITH_APT" -eq 1 ]] && command -v apt-get >/dev/null && command -v dpkg >/dev/null; then
    missing=()
    for pkg in python3 python3-venv python3-pip git libgomp1; do
        dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "    Installiere: ${missing[*]}"
        SUDO=""
        [[ "$(id -u)" -ne 0 ]] && SUDO="sudo"
        $SUDO apt-get update
        $SUDO apt-get install -y "${missing[@]}"
    fi
    ok "Systempakete vorhanden"
else
    echo "    Übersprungen (kein apt oder --no-apt)."
fi

# ---------------------------------------------------------------------------
step "2/7 Python-Version prüfen"
if ! command -v "$PYTHON" >/dev/null; then
    echo "$PYTHON wurde nicht gefunden." >&2
    false
fi
"$PYTHON" - <<'EOF'
import sys
if sys.version_info < (3, 10):
    sys.exit(f"Python {sys.version.split()[0]} ist zu alt, nötig ist mindestens 3.10.")
print(f"    Python {sys.version.split()[0]}")
EOF
ok "Python passt"

# ---------------------------------------------------------------------------
step "3/7 Virtuelle Umgebung .venv und Pakete"
if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON" -m venv .venv
fi
VPY="$REPO_DIR/.venv/bin/python"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r requirements.txt
if [[ "$WITH_CCXT" -eq 1 ]]; then
    "$VPY" -m pip install --quiet ccxt
fi
"$VPY" -c "import numpy, pandas, sklearn, lightgbm, scipy, matplotlib; print('    pandas', pandas.__version__, '| numpy', numpy.__version__, '| lightgbm', lightgbm.__version__)"
ok "Pakete installiert"

# ---------------------------------------------------------------------------
step "4/7 Testsuite (dauert etwa eine Minute)"
"$VPY" -m pytest -q -p no:cacheprovider
ok "Alle Tests bestanden"

# ---------------------------------------------------------------------------
step "5/7 Marktdaten laden (Tageskerzen, etwa eine Minute)"
"$VPY" -m trading_bot fetch --intervals 1d
ok "Daten in data/cache/"

# ---------------------------------------------------------------------------
step "6/7 Backtest des empfohlenen Bots rotation_bot_v1"
"$VPY" -m trading_bot portfolio --strategy rotation_bot_v1
ok "Backtest gelaufen"

# ---------------------------------------------------------------------------
step "7/7 Probelauf Paper-Trading mit Live-Kursen (Testkonto, wird danach gelöscht)"
cleanup_check
"$VPY" -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once --name "$CHECK_NAME"
"$VPY" -m trading_bot status --name "$CHECK_NAME" --trades 5
cleanup_check
ok "Paper-Trading funktioniert"

# ---------------------------------------------------------------------------
if [[ "$WITH_CRON" -eq 1 ]]; then
    STEP="cron einrichten"
    step "Zusatz: täglicher Paper-Lauf per cron"
    if ! command -v crontab >/dev/null; then
        echo "crontab fehlt. Installieren mit: sudo apt install -y cron" >&2
        false
    fi
    # 01:15 UTC in Ortszeit: bleibt bei Sommer-/Winterzeit-Wechsel nach dem Kerzenschluss um 00:00 UTC.
    read -r CRON_MIN CRON_HOUR < <(date -d "01:15 UTC" +"%-M %-H")
    MARK="# trading-bot-v1 (scripts/install_ubuntu.sh)"
    LINE="$CRON_MIN $CRON_HOUR * * * cd \"$REPO_DIR\" && .venv/bin/python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once >> bot.log 2>&1 $MARK"
    { crontab -l 2>/dev/null | grep -vF "$MARK" || true; echo "$LINE"; } | crontab -
    ok "cron-Eintrag gesetzt: täglich um $(printf '%02d:%02d' "$CRON_HOUR" "$CRON_MIN") Uhr Ortszeit, Protokoll in bot.log"
    echo "    Entfernen mit: crontab -l | grep -vF 'trading-bot-v1' | crontab -"
fi

trap - ERR
cat <<EOF

$(printf '\033[32m\033[1m')Fertig: Trading-Bot-V1.0 ist installiert und getestet.$(printf '\033[0m')

Nächste Schritte (im Ordner $REPO_DIR):
  source .venv/bin/activate
  python -m trading_bot paper --strategy rotation_bot_v1 --interval 1d --once   # eigenes Paper-Konto starten
  python -m trading_bot status                                                   # Kontostand ansehen
Dauerbetrieb: bash scripts/install_ubuntu.sh --cron   (oder ANLEITUNG.md, Schritt 10)
Live-Handel mit echtem Geld: erst nach 2–3 Monaten Paper-Trading, siehe ANLEITUNG.md, Teil 4.
EOF
