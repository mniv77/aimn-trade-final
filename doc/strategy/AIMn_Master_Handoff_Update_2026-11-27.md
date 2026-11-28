AIMn / KISS — Master Handoff Update
Research checkpoint: November 27, 2026 | Steps 203–356
This supplement preserves earlier handoff reports. It records the current research freeze, visual replay deployment, UTC recovery and outstanding work. No authorization for live trading is implied.
1. Mission and operating rules
    • Recognize genuine major LONG→SHORT transitions on NVDA 5-minute candles, enter near the peak and exit near the reverse transition. Distinguish minor V noise from major trend reversal. Retain protective stop-loss and RSI rescue principles; use completed 30-minute context without lookahead.
    • Research first, independent validation second, production changes only after explicit approval. Complete Alpaca before Gemini. Prefer complete Python files and one short PythonAnywhere command per step; do not paste long Bash heredocs.
    • Repository: https://github.com/mniv77/aimn-trade-final ; active branch kiss-transition-detector-v5-6-6-final; PythonAnywhere root ~/aimn-trade-final.
    • Preserve unrelated working tree changes. Do not use git clean, reset, or broad staging.
2. Frozen research milestone
AA1, AA4, AM3 and AP remain frozen. Earlier discovery across Jun–Aug, Sep–Oct and Nov yielded AM3 as a candidate, not an independently validated profitable system.
AM3 combines AE3 early warning, AJ1 next completed candle confirmation and W12 retracement >= 0.60, with the previously frozen causal replay rules. No threshold optimization during prospective validation.
Discovery period	Trades	Winners	Losers	Net percentage points
Jun–Aug	11	6	5	+0.181220
Sep–Oct	5	4	1	+0.322873
November	1	1	0	+0.442076
Total	17	11	6	+0.946169

The unfiltered AM0 baseline had 58 trades and net −7.178589 percentage points. AM3 includes 0.20% round-trip commission. Additional cost of 0.02/0.05/0.10 percentage points per trade reduces net to +0.606169/+0.096169/−0.753831 respectively. Without the July 24 trade (+1.402595), aggregate net is −0.456426. Small sample, selection effects and concentration are major limitations. Do not claim profitability or deploy live.
Frozen AM3 source SHA256: f19067752e1a917da0a277a9bf4e363e57632b9fced7eac8ce4f28a0c382b79f. Frozen summary SHA256: 55a3bf0e544ae668ed4b147e837ec01187dc336cec60e04dcb46dca0119bc547. AP script aimn_exp40ap_forward_validation.py, SHA256 1384d301e56b7465462d02be4b9ba299189a63a8c6ada200d37d875aeb4fad6a. Historical research report: doc/strategy/AIMn_EXP40_AM3_Research_Milestone_2026-11-27.md.
3. Prospective validation — next research priority
Frozen cohort: 20 regular sessions November 30–December 29, 2026, excluding December 24 shortened session and December 25 holiday; November 27 shortened session is outside the cohort. Expected 1,560 five-minute regular-session candles. No interim scoring or tuning. Download data only, no orders. Downloader: aimn_exp40l_alpaca_validation_downloader.py --start YYYY-MM-DD --last YYYY-MM-DD. Use one regular session per invocation and verify the dataset; do not substitute partial sessions. AP without arguments runs benchmark only. Inspect AP's actual CLI before prospective execution. Verify frozen hashes, historical parity, timestamps, session coverage and data integrity before scoring the full cohort. If validation fails, report it without changing frozen rules. The cohort has not yet started at this checkpoint.
4. AM3 visual overlay
Replay URL: https://meirniv.pythonanywhere.com/aimn_ai_vision_replay?broker_id=2&symbol=NVDA&direction=SHORT&timeframe=5m
    • aimn_exp40aq_visual_exporter.py produces static/aimn_visual_lab/aimn_am3_transition_data.json (282 KB on server).
    • static/aimn_am3_transition_panel.js renders research events, disabled by default for blind replay. templates/aimn_ai_vision_replay.html loads it.
    • 4,680 candles and 281 events: 104 AE3_WARNING, 66 AJ1_REJECTED, 38 AJ1_CONFIRMED, 38 AM3_GATE, 13 EXECUTION_DECISION, 11 ENTRY, 11 EXIT. Jun–Aug 11 completed AM3 trades, +0.181220% net. Manual research position is separate from AM3 position.
    • Generated JSON contains market candles; do not publish it in GitHub. The exact file is ignored by .gitignore. Regenerate from the committed exporter and its original research inputs; inspect its CLI before running. Git exclusion is not web access control: the deployed static file may be accessible via the website. Review access and redistribution rights separately.
5. UTC migration and human research recovery
The old browser parsed timezone-naive New York market labels as browser-local Pacific time. For this summer dataset that was three hours late. New York timezone conversion now produces true UTC; explicit timezone/numeric inputs are preserved. Naive local uploads require an explicit timezone. Do not apply a constant three-hour correction to other datasets or seasons.
Check	Result
First candle June 4	13:30 UTC
Last candle August 28	19:55 UTC
AM3 trade #4 June 11 entry	14:50 UTC
Human research records	916, including 3 excluded
Replay position	4680/4680
Open manual research SHORT	Candle 3205, $209.99

A pre-existing corrected identity had only 67 judgments at candle 435. The initial migration silently selected it. Both sessions were located, exported and backed up. A browser recovery script checked original timestamp and price against actual corrected candles, preserved activity timestamps and annotations, archived the older corrected session, retained original legacy storage, and installed the corrected 916-record copy. Console recovery succeeded and subsequent browser reloads displayed the full session correctly.
aimn_utc_migration_install.py and aimn_utc_conflict_guard_install.py are committed installers, already applied on this deployment. Do not rerun unnecessarily. Dry runs precede apply. The conflict guard blocks ambiguous sessions; persistence now retains UTC migration metadata. NVDA recovery after guard installation was verified in Chrome. Future-save metadata persistence, deliberate new-session behavior, other symbol migrations and different browser timezone cases are not fully browser-tested. Do not disturb the completed NVDA session for testing. Use isolated test data.
6. Backups and privacy
    • Original and corrected human research JSON saved by user in local PC/OneDrive templates/SAVED/JSON directory. Original backup name AIMn_NVDA_Both_Sessions_Backup.json; corrected export was requested as AIMn_NVDA_916_Judgments_UTC_Final_2026-11-27.json. User reports saving JSON files; corrected export contents have not been independently verified.
    • Browser original legacy key retained, older corrected session archived under aimn_utc_recovery_archive: prefix. Do not clear browser storage or start a new session casually.
    • ~/AIMn_EXP40_AM3_Backup_2026-11-27.tar.gz: private research backup, gzip test passed; no restore test.
    • ~/AIMn_before_UTC_migration_2026-11-27.tar.gz: pre-migration files.
    • instance/aimn_utc_preinstall_v1/ and instance/aimn_before_utc_conflict_guard.js: installation rollback copies.
    • Never commit private judgment exports, credentials, proprietary holdout data or local backups. Consider access control for deployed market data. Keep independent backup copies outside the repository.
7. GitHub checkpoint
    • 439407184fbc6f082c34922229ad561307f3fd43: EXP40 research milestone, scripts and summary reports.
    • f32e83601af5bedafd1db460611d4e7e60a06704: Add AM3 visual overlay and UTC migration safeguards; six software files, 507 insertions and 5 deletions.
    • 24b064980bd3c97067775d5b79f28244b16ff980: Exclude generated AM3 visualization data; remote branch and exact ignore rule independently verified.
    • The above is the latest verified remote checkpoint before this supplement. Do not confuse it with the main or independent research branches.
8. Next steps and unresolved verification
    1. Save this supplemental handoff under doc/strategy/ and commit only that file after checking its contents. Preserve prior reports.
    2. Independently verify corrected research export, including record counts, timestamps, annotations and open research position; keep private.
    3. Collect the frozen prospective AM3 cohort starting November 30; do not evaluate before the complete cohort is available. No live orders.
    4. Separately test migration conflicts and persistence on disposable sessions, not the completed NVDA dataset. Check other Alpaca symbols and UTC behavior before expanding scope.
    5. Preserve the existing weekly research milestone monitoring. It is not a substitute for data collection or prospective validation.
Final state: visual replay and NVDA UTC recovery verified; six software files and generated-data ignore rule pushed and independently verified. AM3 remains a frozen, unvalidated candidate. No trading strategy changes were made by the visual/UTC work.
