
AiMn Trade — KISS Strategy / Development Handoff Report-8-31-26-V1
1. The main idea
We are building a trading system around one simple principle:
KISS — Keep It Simple
We deliberately moved away from the huge collection of indicators that many trading systems use.
The strategy has only three market states:
    • LONG — market is trending upward 
    • SHORT — market is trending downward 
    • FLAT — sideways market 
The important thing is not the shape of the chart.
The important thing is:
When did the market change from one trend to another?
A V shape, inverted V, W, M, U, etc. are simply different visual forms of a transition.
Examples:
    • falling → rising = LONG transition / V-Long 
    • rising → falling = SHORT transition / V-Short 
But the shape itself is NOT the strategy.

2. Entry rules
We enter when the trend changes into a direction we want to trade.
Valid entries
    • SHORT → LONG 
    • LONG → SHORT 
    • FLAT → LONG 
    • FLAT → SHORT 
We do NOT enter
    • LONG → FLAT 
    • SHORT → FLAT 
Those are waiting conditions.
If the market goes from a trend into FLAT, we wait for the next meaningful transition.

3. The major problem we discovered
The original implementation could identify a trend change, but execution was too late.
This became especially obvious with NVDA.
NVDA has many very fast V-type transitions and sudden jumps.
By the time a 30-minute candle confirmed the transition, much of the move had already happened.
That caused:
    • LONG entries near the top 
    • SHORT entries near the bottom 
    • exits after much of the profitable move had disappeared 
The result could be a trade that had the correct direction but terrible execution.
This explains why some results looked irrational.

4. The new experiment
We decided to separate:
Major decision timeframe
30-minute candles
Used to determine:
What is the major/global trend?
Execution timeframe
5-minute candles
Used to determine:
When should we actually enter or exit?
The theory is simple:
30m tells us WHAT is happening.
5m tells us WHEN to act.
This is an experiment. Only the real backtest can tell us whether it improves results.
We are NOT changing broker, symbol selection, direction selection, or the existing candle-selection system unless we discover that something is actually broken.

5. Confirmation / noise
A major problem is that a trend can temporarily change and then immediately change back.
Example:
LONG
→ small SHORT movement
→ LONG again
We call this minor noise.
We do NOT want a single candle to throw us out of a good trade.
The strategy therefore uses a confirmation zone:
A transition should survive approximately 2–4 candles before being considered real.
The current experiment uses 2 confirmations out of 3 5-minute candles.
The purpose is NOT to delay the trade unnecessarily.
It is only there to prevent one small piece of noise from causing an unnecessary entry or exit.

6. Very important new principle: early is better than late
We have now learned something important from the loser charts:
We were too cautious.
The system sometimes waited so long for confirmation that it entered after the important part of the move was already finished.
Therefore:
We would rather exit slightly too early than exit too late.
Why?
Suppose we are LONG.
The market starts reversing.
If we exit slightly early, we may lose some additional upside.
That is acceptable.
If we exit too late, the market can move through the entire reversal and turn a profitable trade into a substantial loser.
We can always re-enter later if a new transition is confirmed.
So the philosophy is:
Protect the trade first. Re-enter when the market proves itself again.

7. Trailing exit
The trailing mechanism is still important.
The purpose of the trailing mechanism is to detect when the current trend has probably stopped behaving like the trend that justified the trade.
But we don't want one noisy candle to immediately close the trade.
Therefore:
Trailing signal → confirmation → exit
rather than:
Trailing signal → immediate exit
However, we should be careful not to make the confirmation so slow that we repeat the original problem.
This is one of the things the 5m experiment must test.

8. RSI
RSI is NOT the strategy.
It is an emergency safety mechanism.
Normal operation:
Trend transition → trade
RSI is only there for exceptional situations such as:
    • very strong unexpected bad news while LONG 
    • very strong unexpected good news while SHORT 
    • extremely rapid movement where waiting for normal trend-transition confirmation would be dangerous 
So:
Trend decides. RSI protects.
We don't want to turn the system back into an indicator-driven strategy.

9. The loser charts are our most important training material
We deliberately do NOT need to spend much time studying winners.
The winners already show that the basic concept can make money.
The losers tell us where the system is wrong.
The feedback loop is:
Backtest → find losers → display chart → identify why entry/exit was bad → change ONE thing → backtest again
We want to reduce loser trades substantially.

10. The chart requirements
The loser chart should show:
    • real candles 
    • entry 
    • exit 
    • Trade ID 
    • direction 
    • entry price 
    • exit price 
    • transition responsible for entry 
    • exit reason 
    • RSI at entry/exit 
    • maximum favorable movement 
    • maximum adverse movement 
The Trade ID is important because it lets us quickly identify the exact trade and investigate it.
We only need the loser charts for our primary analysis.

11. Important example
One NVDA loser showed essentially:
correct general idea → entry too late → trend nearly finished → exit too late
That is much more useful to us than simply knowing:
"NVDA lost 2%."
The chart tells us why.
Another important discovery was that some trades were effectively doing the reverse of what logic requires:
entering high and exiting low.
Those cases need special attention because they can indicate an execution/timing problem rather than a bad symbol or bad direction.

12. The "go backward" idea
Another important part of the strategy is how we discover transitions.
Instead of repeatedly scanning the entire historical dataset from the beginning, we want the engine to:
Start at the newest candle and work backward to find the most recent meaningful transition.
Once a transition has been identified, remember it.
Then, when new candles arrive, we don't need to rediscover old history.
This is essentially a small memory/notebook for the strategy.

13. Separate memories
The strategy itself should be one common brain.
But each application gets its own memory:
    • Live trading → live memory 
    • Backtest → backtest memory 
    • Tuner → tuner memory 
We do NOT want the tuner or backtest contaminating live-trading state.
The strategy is shared.
The memory is separate.

14. Current implementation status
We created an independent experimental engine:
engine/kiss_execution_5m.py
Purpose:
Test 30m trend decisions with 5m execution without disturbing the existing system.
It was deliberately written separately so that we don't have to contaminate the existing tuner/backtest architecture.
The latest GitHub update was pulled into PythonAnywhere successfully.
Current commit:
c14b81c
The new engine contains the 30m/5m experiment and the KISS transition logic.

15. What we should NOT do
This is extremely important.
Do NOT:
    • rebuild broker selection 
    • rebuild symbol selection 
    • change direction selection 
    • add dozens of indicators 
    • turn this into another giant parameter grid 
    • optimize specifically for one stock 
    • assume a backtest improvement is automatically real 
    • change five things at once 
Especially:
If it isn't broken, don't touch it.
The broker/symbol/direction/candle selection was working and should remain untouched.

16. What we are testing now
The immediate question is very simple:
Does 30m + 5m execution improve entry and exit timing?
We need to test it on several symbols, especially difficult ones such as:
NVDA
because NVDA contains:
    • many V transitions 
    • rapid reversals 
    • sudden jumps 
    • fast trend changes 
If the new execution method cannot improve NVDA, we have learned something important.
If it does improve NVDA and improves other symbols without destroying the good results, then we have evidence that the architecture is better.

17. The most important philosophy
We are not trying to predict the future.
We are trying to recognize:
The market has changed direction.
Then act quickly enough to participate.
And when the evidence says the direction has changed again:
Get out before the reversal becomes expensive.
We don't have to catch the exact top or bottom.
We need to avoid being late.

18. Current working rule
Entry
30m identifies the major transition.
5m finds the practical execution point.
Do not chase a move that has already traveled too far.
During trade
Ignore small noise.
Allow the major trend to continue.
Exit
Use the 5m execution timeframe to react faster to a meaningful reversal.
Prefer slightly early over too late.
Emergency
RSI can override normal patience when the market makes an extreme unexpected move.
After exit
Do not immediately chase the market.
Wait for the next confirmed transition.

19. The goal
The goal is NOT:
"Make every trade a winner."
That is impossible.
The goal is:
Stop making the same losing trade over and over.
If we can turn:
    • late entries into timely entries 
    • late exits into timely exits 
    • unnecessary noise exits into held trades 
    • catastrophic reversals into controlled losses 
then the system can improve dramatically without becoming complicated.

Final principle
One strategy.
Three states.
Transitions matter.
30m decides the major direction.
5m executes.
RSI protects.
Trailing protects.
Losers teach us.
And when in doubt between early and late:
Early is better than late.
That is the context I would give the new chat. It should be enough for us to continue without you having to retell the whole history.



***************************************************************************************************
***************************************************************************************************
***************************************************************************************************




AiMn Trade — Handoff Report for New Chat
1. The project

We are developing AiMn Trade at:

~/aimn-trade-final

GitHub repository:

mniv77/aimn-trade-final

The application runs on PythonAnywhere.

Important: The existing broker / symbol / direction / candle-selection system is working. Do not change it unless there is clear evidence that it is broken.

2. The central idea — KISS strategy

The strategy deliberately moves away from the huge collection of technical indicators and complicated trading formulas.

KISS = Keep It Simple.

The market is viewed primarily as three states:

LONG — upward trend
SHORT — downward trend
FLAT — sideways

The important thing is the transition between trends, not the exact shape of the chart.

Examples:

falling → rising = V-Long
rising → falling = V-Short
W, M, U, etc. are only different shapes of the same underlying idea.

Shape is not the strategy. The transition is the strategy.

3. Entry rules

Entries happen when the market changes into a tradable trend:

SHORT → LONG = enter LONG
LONG → SHORT = enter SHORT
FLAT → LONG = enter LONG
FLAT → SHORT = enter SHORT

We do not enter merely because:

LONG → FLAT
SHORT → FLAT

Those are waiting states.

The philosophy is:

Do not predict the market. Detect that the market has actually changed.

4. Exit rules

While in a trade, we continue following the trend.

A transition in the opposite direction can cause an exit.

A trailing mechanism is used to protect the trade.

However, there is an important problem we discovered:

Noise

A market can do:

LONG → SHORT → LONG

very quickly.

That may be only minor noise and should not immediately close a good LONG trade.

Therefore, a trend transition should be confirmed over approximately 2–4 candles before treating it as a real transition.

But if the movement is a genuine major reversal and passes the safety/confirmation zone, we exit.

5. RSI

RSI is not the strategy.

It exists as an emergency protection mechanism.

Example:

LONG + extremely weak RSI → emergency exit
SHORT + extremely strong RSI → emergency exit

The reason is that unexpected events can cause a reversal much faster than the normal transition-detection process.

So:

Trend = brain
Trailing protection = normal trade protection
RSI = emergency brake
Stop loss = final protection

6. Major discovery from backtesting

The first KISS implementation produced useful results but exposed a major weakness:

entries and exits were often too late.

The charts made this visually obvious.

In several losing trades:

the system recognized the transition,
waited too long,
entered after much of the move had already happened,
and then exited after much of the reversal had already happened.

This was especially obvious with NVDA, whose chart contains many rapid V-type reversals and sharp jumps.

Despite the bad timing, some tests still made money, which strongly suggested that the basic strategy direction was useful but execution timing needed improvement.

7. Important conclusion

We believe the problem is not primarily broker/symbol/direction selection.

The main problem is:

How quickly can we execute after the 30-minute market decision becomes clear?

This led to the next experiment.

8. Current experiment: 30m decision + 5m execution

We decided not to change everything at once.

The current experiment is:

30-minute candles

Used to determine the major/global trend.

5-minute candles

Used to determine the actual entry and exit timing.

The idea is simple:

30m tells us WHAT is happening.
5m tells us WHEN to act.

This should potentially reduce the delay by approximately a factor of six compared with waiting for another 30-minute candle.

We specifically chose this approach because we want a real test, not theoretical arguments.

9. Current new code

A separate experimental engine was created:

engine/kiss_execution_5m.py

It is intentionally separated from the existing system.

The purpose is to allow comparison between:

old KISS execution

versus

KISS 30m trend + 5m execution

without contaminating the existing system.

The latest GitHub pull reported:

c14b81c

and added:

engine/kiss_execution_5m.py

The system was successfully compiled with:

python -m py_compile engine/kiss_execution_5m.py kiss_backtest_routes.py
10. Very important design principle

We do not want to reinvent the strategy every time we test a stock.

We want:

ONE strategy → ONE consistent engine → different memories/data for live trading, backtesting and tuning.

The strategy must be explicit enough that an ordinary person—or another AI—can understand exactly what constitutes:

LONG
SHORT
FLAT
transition
noise
confirmed transition
entry
exit
emergency exit
11. The backtest display

The new KISS backtest page is:

/kiss_backtest

It already displays:

total trades
total P&L
win rate
number of losers
detected transitions
losing trades
individual Trade IDs
entry
exit
transition
exit reason
maximum favorable movement
maximum adverse movement
RSI at entry/exit

A chart displays the individual losing trade with the entry and exit markers.

This is extremely important because the purpose is not simply to see whether the strategy made money.

The chart lets Meir look at a loser and say:

"This entered too late."

or:

"This exited too late."

or:

"This was just noise and should not have caused an exit."

That human feedback will eventually be valuable for improving/training the AI.

12. We deliberately focus on losers

We don't need to spend much time studying winners right now.

There are already enough losing trades to teach us what is wrong.

The goal is:

Reduce unnecessary losing trades and improve entry/exit timing.

If the system can eliminate even a portion of the obvious bad entries/exits, profitability should improve substantially.

13. One particularly important observation

NVDA is a valuable test case because its chart contains:

many V-shaped reversals,
rapid transitions,
sudden jumps,
fast movement from one trend to another.

That makes NVDA a good stress test for transition speed.

The previous NVDA SHORT test was described as a disaster because:

entry was much too late and exit was much too late.

Therefore NVDA should be tested again using the 30m decision / 5m execution approach.

14. What NOT to do

Do not:

change broker selection
change symbol selection
change direction selection
replace the KISS strategy with a pile of indicators
add MACD/EMA/Bollinger/etc. simply because they are popular
optimize dozens of parameters simultaneously
destroy the working existing system
judge the new approach from one theoretical argument

Do:

change one important thing at a time
run real backtests
compare results
inspect losing trades
use the chart
record Trade IDs
identify whether entry or exit was too early/late
test NVDA and other symbols
let the actual results decide
15. Current next step

Run the 30m + 5m execution experiment on NVDA and compare it directly with the previous KISS result.

The key measurements are:

Number of losers
Total P&L
Win rate
Average trade
Entry timing
Exit timing
Whether minor noise is being ignored
Whether major reversals are caught faster

Do not declare the new method better until the real backtest demonstrates it.

16. Philosophy

The most important principle of the entire project is:

Most trades do not necessarily make money. We want to understand why—and get on the other side of that problem.

We are not trying to make the system complicated.

We are trying to make it simple, consistent, fast enough, and difficult to fool by noise.

KISS. One strategy. One brain. Real tests. Learn from the losers.


#################################################################################
#################################################################################
AiMn Trade — Project Handoff Report
For continuation in a new ChatGPT conversation
1. The main idea
The most important part of this project is the trading strategy, not adding more indicators.
The strategy is intentionally KISS — Keep It Simple.
We moved away from the idea that adding RSI, MACD, Bollinger Bands, volume indicators, etc. will magically make trading profitable.
The core question is:
Has the market changed direction?
There are only three market states:
    • LONG — generally moving up 
    • SHORT — generally moving down 
    • FLAT — sideways 
The important thing is the transition between states, not the visual shape of the chart.
Examples:
    • SHORT → LONG = possible LONG entry 
    • LONG → SHORT = possible SHORT entry 
    • FLAT → LONG = possible LONG entry 
    • FLAT → SHORT = possible SHORT entry 
    • LONG → FLAT = do NOT enter 
    • SHORT → FLAT = do NOT enter 
A V shape is simply an easy visual example:
    • falling → rising = V-LONG 
    • rising → falling = V-SHORT 
But there can be W, M, U, irregular shapes, sudden jumps, etc.
The shape is not the strategy. The transition is the strategy.

2. Entry philosophy
We want to enter near the beginning of the new trend, not after the market has already traveled a large distance.
This became a major problem in our testing.
The previous implementation could recognize the transition too late.
We saw this very clearly in NVDA.
The system would essentially say:
"Yes, the trend changed."
But by the time it acted, the price had already moved significantly.
Then it could enter near the end of the trend and become the loser.
The user's conclusion was:
We were too cautious.
The objective now is therefore:
Detect the major trend on 30-minute candles, but execute the actual entry/exit using 5-minute candles.
The reasoning:
30m = major/global decision
5m = execution timing
This should potentially allow the system to react approximately six times closer to the actual transition than using only 30m candles.
But we are not assuming it works.
Only a real backtest will tell us.

3. Exit philosophy
The same problem exists on exits.
We do not want:
trend changed → wait too long → exit at the bottom/top.
The system should follow the trend and use a trailing mechanism to protect the trade.
We discussed:
    • trailing take profit / trailing trend protection 
    • confirmation of approximately 2–4 candles 
    • ignoring small local noise 
    • exiting when a genuine transition becomes established 
    • RSI only as an emergency escape mechanism 
    • stop loss as the final safety mechanism 
The important distinction is:
Minor noise
Example:
LONG → small SHORT movement → LONG again
Do not immediately exit.
Major reversal
If the change persists through the safety/confirmation zone, then it is treated as a real transition and we exit.
The purpose is to avoid being shaken out of a good trade by one or two noisy candles.

4. RSI
RSI is not the strategy.
It is only there because:
The unexpected always happens.
For example:
    • We are LONG. 
    • Extremely bad news appears. 
    • The market collapses suddenly. 
Waiting for the normal trend-transition process could take too long.
RSI is therefore an emergency mechanism to get us out quickly.
Similarly:
    • SHORT + extraordinary positive move → emergency protection. 
So:
Trend transition = normal decision
RSI = emergency protection
Stop loss = final protection

5. The most important lesson from the loser charts
We built a KISS backtest page that shows losing trades only.
This was deliberate.
We do NOT need to waste time studying winners right now.
We have enough losers to learn from.
Each losing trade has:
    • Trade ID 
    • direction 
    • entry time 
    • exit time 
    • entry price 
    • exit price 
    • transition 
    • exit reason 
    • maximum favorable movement 
    • maximum adverse movement 
    • RSI at entry/exit 
The chart displays the actual candles and marks the entry and exit.
This allows a human to immediately see things such as:
"That entry was obviously too late."
or:
"That exit was obviously too late."
This is exactly the feedback we want to eventually use for AI training.

6. Very important observation about NVDA
NVDA became particularly important because its chart contains many rapid reversals — lots of V-like transitions and sudden jumps.
That makes it an excellent stress test for the strategy.
We tested NVDA SHORT and saw a disaster caused by entering and exiting too late.
This does NOT mean NVDA itself is bad.
It means the execution timing was bad.
The user specifically said that NVDA has:
    • many V transitions 
    • very fast transitions 
    • sudden jumps 
    • situations where entering too late means arriving near the end of the trend 
    • situations where entering too early could also be dangerous 
Therefore NVDA is a very useful test case for the new 30m/5m approach.

7. The existing broker / symbol / direction / candle selection
DO NOT CHANGE THIS.
The user explicitly said:
"the selection of broker/symbol/direction/candle works fine — if it is not broke do not touch it."
That existing functionality should remain untouched.
The current work is about:
Correct strategy + correct execution timing + useful loser visualization.
Do not reinvent the rest of the system.

8. Existing project
GitHub repository:
mniv77/aimn-trade-final
PythonAnywhere application:
aimn-trade-final
The project is deployed on PythonAnywhere.
Normal workflow:
cd ~/aimn-trade-final
git pull origin main
Then compile/check the relevant Python files.
The user strongly prefers:
Give complete Bash commands/files whenever possible.
Avoid giving little code patches that require the user to figure out where to insert them.
The user has repeatedly said:
Keep it easy. Only list the Bash commands I need to execute.

9. Strategy documentation
We already rewrote the strategy documentation into a single understandable strategy document with difficult subjects explained simply.
The strategy documentation is intended to explain the system almost as if explaining it to a very young person:
    • simple language 
    • no unnecessary complexity 
    • one strategy 
    • one brain 
    • separate memory for each application 
The user liked this approach.
The strategy document should remain the source of truth for the strategy.

10. Important architecture idea: separate memory
One particularly important concept:
One strategy, one engine, different memories.
Live trading, backtesting, and tuning should use the same strategy logic, but each should have its own stored state/memory.
Think of each application as having its own notebook.
For example:
    • Live trading → its own memory 
    • Backtest → its own memory 
    • Tuner → its own memory 
They should not overwrite one another.
This prevents the system from having to repeatedly travel backward through old data to rediscover what it already knew.

11. "Start from the newest candle and go backward"
This is another important optimization/concept.
Instead of repeatedly scanning the entire history forward:
candle 1 → candle 2 → candle 3 → ... → newest candle
the system can start at the newest candle and work backward to find the most recent meaningful transition.
Once it knows:
"The previous trend was LONG and the transition happened here."
it remembers that.
When new candles arrive, it only needs to examine what is new.
This is both conceptually cleaner and more efficient.

12. Existing KISS files
Recent project work created:
engine/kiss_backtest.py
kiss_backtest_routes.py
templates/kiss_backtest.html
and later:
engine/kiss_execution_5m.py
The KISS backtest page is accessible through:
/kiss_backtest
The page displays:
    • total trades 
    • total P&L 
    • win rate 
    • losers 
    • fresh candle count 
    • detected transitions 
    • losing-trade list 
    • selectable Trade IDs 
    • candle chart 
    • entry marker 
    • exit marker 
    • detailed trade information 
The user likes this display because it is easy to understand.

13. Latest experimental file
We created a separate experimental engine specifically for the 30m/5m execution experiment:
engine/kiss_execution_5m.py
The purpose is to keep this experiment independent from the existing system rather than contaminating the working parts.
Its intended architecture is:
30-minute candles
       ↓
major/global trend decision
       ↓
transition detected
       ↓
5-minute candles
       ↓
entry / exit timing
It uses the same KISS philosophy.
It does NOT introduce a giant indicator system.
The file contains the experimental logic for:
    • 30m market state 
    • 5m execution 
    • transition confirmation 
    • V-shape recognition 
    • trailing protection 
    • RSI emergency exit 
    • stop/position protection 
    • trade IDs 
    • loser information 

14. Latest Git status
The user most recently ran:
cd ~/aimn-trade-final
git pull origin main
python -m py_compile engine/kiss_execution_5m.py kiss_backtest_routes.py
touch /var/www/meirniv_pythonanywhere_com_wsgi.py
The pull succeeded.
The latest change pulled was:
engine/kiss_execution_5m.py
kiss_backtest_routes.py
with the new experimental 5m execution engine.
The Python compile command succeeded.

15. Current objective
The immediate objective is NOT to redesign the entire trading application.
We are experimenting.
The current experiment is:
30m decides the trend.
5m decides the execution.
Then compare the results against the previous KISS implementation.
Especially compare:
    • entry timing 
    • exit timing 
    • number of losers 
    • size of losses 
    • total P&L 
    • whether rapid NVDA reversals are handled better 
The key question is:
Does 5m execution actually reduce the late entries and late exits we saw in the loser charts?
We do not assume the answer.
We test it.

16. The user's philosophy
The user wants the system to stop "reinventing the wheel."
Once the strategy is clearly defined, every trade should follow the same rules.
The system should not invent a different interpretation every time.
The goal is:
One clear strategy → one implementation → repeatable decisions → measurable results.
And the user wants the AI to learn primarily from the losers, because that is where the biggest opportunities for improvement are.

17. Very important development rule
Before changing something, ask:
Is this actually broken?
If it works:
DO NOT TOUCH IT.
Especially:
    • broker selection 
    • symbol selection 
    • direction selection 
    • candle/timeframe selection 
    • existing working dashboard functions 
The current experiment should be isolated as much as reasonably possible.

18. Where we left off
We are now at the point where the new 30m/5m experiment has been added to GitHub and pulled into PythonAnywhere.
The next step is to test it with real data, particularly NVDA.
The user wants to compare the new result against the previous KISS result.
The user will then inspect the loser charts and give human feedback.
That feedback is valuable because the chart can reveal things the raw statistics cannot.

19. Communication preference
The user prefers the assistant to take the lead technically.
When there is work to do:
    • don't repeatedly ask what to do 
    • inspect the project 
    • make the changes 
    • keep working toward the objective 
    • when the user asks "progress", give a concise status 
    • when something must be executed on PythonAnywhere, give only the Bash commands needed 
    • prefer full files over patches whenever practical 
    • explain complicated concepts simply 
    • don't unnecessarily change working components 
The user may disappear for a while and return later asking:
progress
At that point, continue from this project state.

20. Guiding principle
The ultimate objective is not to make the backtest look good.
It is:
Reduce losing trades by getting the entry and exit timing right while remaining faithful to the simple KISS trend-transition strategy.
And the most important test is whether the real loser charts improve, not whether we can make the statistics look attractive.
Do not optimize for a pretty backtest. Optimize for correct behavior.

Current starting point for the new chat
Start here:
We have implemented the independent engine/kiss_execution_5m.py experiment. It is supposed to use 30m for major trend decisions and 5m for execution timing. The next job is to make sure it is correctly connected to the KISS backtest/display, run NVDA, and compare the loser charts against the previous implementation. Do not change broker/symbol/direction selection. Keep the existing system intact wherever it works. Use the KISS strategy as the source of truth.


=======================================================================================================
=========================================================================================================

========================================================================================================
==========================================================================================================

AiMn Trade — Project Handoff Report
KISS Strategy / Trend Transition / 5-Minute Execution Experiment
1. The main idea

The most important part of this project is the trading strategy, not adding more indicators.

The philosophy is:

KISS — Keep It Simple.

We deliberately moved away from the common approach of combining many indicators and parameters.

The strategy sees the market primarily as having only three states:

LONG — upward trend
SHORT — downward trend
FLAT — sideways

The important event is the transition from one trend to another.

The shape of the chart can be:

V
inverted V
W
M
U
inverted U
or many other shapes.

The exact shape is not the strategy.

The change of trend is the strategy.

2. Entry rules

We enter when the market changes into a tradable trend.

Valid entries:

SHORT → LONG = enter LONG
LONG → SHORT = enter SHORT
FLAT → LONG = enter LONG
FLAT → SHORT = enter SHORT

We do not enter:

LONG → FLAT
SHORT → FLAT

Those are situations where we wait rather than immediately opening another trade.

A classic:

falling → rising = V-Long
rising → falling = V-Short

But V shape recognition is only a useful description. We do not want to build a strategy that depends on recognizing a perfect V.

3. Exit rules

While in a trade, we want to stay with the trend.

A meaningful transition in the opposite direction should cause an exit.

We also use:

Trailing protection

The trailing take-profit/trailing mechanism is intended to protect profit when the trend has actually weakened.

RSI

RSI is NOT the strategy.

It exists because unexpected events can happen:

bad news while LONG
extremely good news while SHORT
sudden market shock
extremely fast reversal

In those situations, waiting for the normal trend-transition detection may be too slow.

Therefore RSI is an emergency escape mechanism, not an entry signal.

Stop loss

Stop loss is the final protection in case we are simply wrong.

4. The major problem we discovered

The original implementation was often too slow.

The backtest charts made this very obvious.

We examined losing trades rather than spending time studying winners.

That was intentional.

A losing trade tells us:

Where did our logic fail?

Several charts showed:

entry happened after the price had already moved substantially
exit happened after the profitable portion of the move had already disappeared
fast V-shaped reversals were particularly difficult
NVDA was a very good example because it contains many rapid transitions and jumps
sometimes we entered near the end of a trend and exited near the opposite extreme

And the important observation was:

Even with these bad entries/exits, some symbols still made money.

That tells us the underlying direction/selection concept may be valuable, but the execution timing needs improvement.

5. Noise is our biggest enemy

This is now one of the central research problems.

While we are in a LONG trend, the market may temporarily:

LONG → SHORT → LONG

That does not necessarily mean the major trend has changed.

It may simply be noise.

Likewise:

SHORT → LONG → SHORT

may be noise.

We therefore do not want the system to immediately exit every time it sees a tiny reversal.

The current thinking is:

A transition should survive a safety/confirmation period before we treat it as a real transition.

The strategy document describes approximately 2–4 candles of confirmation.

The exact confirmation behavior is still an experimental question.

This is important because we have two competing problems:

Too cautious

We wait too long.

Result:

enter late
buy near the top of a LONG move
short near the bottom of a SHORT move
exit too late
Too sensitive

We react to every little movement.

Result:

noise kicks us out
repeated entries/exits
unnecessary losing trades
strategy becomes a noise detector rather than a trend detector

Finding the balance between these two is currently one of the most important problems.

6. 30-minute decision + 5-minute execution

We reached an important hypothesis:

30-minute candles

Use these to determine the major/global trend.

They answer:

"What is the market doing?"

5-minute candles

Use these to determine execution timing.

They answer:

"When exactly should we enter or exit?"

The reason is simple:

A 30-minute candle is six 5-minute candles.

If we wait for a complete 30-minute candle before executing, we may already be very late.

Especially on something like NVDA, where transitions can happen extremely quickly.

So the experiment is:

30m = strategic decision

5m = execution decision

This should give the system much finer timing without changing the underlying strategy.

7. Important constraint

The broker / symbol / direction / candle selection system was already working.

DO NOT TOUCH IT unless there is a demonstrated bug.

We are not trying to redesign the entire trading system.

We want to improve the strategy execution layer.

8. Backtest feedback system

We added a KISS backtest specifically so we can inspect losing trades.

The result page shows:

total trades
total P&L
win rate
loser count
detected transitions
individual Trade IDs
entry
exit
entry transition
exit reason
RSI
maximum favorable movement
maximum adverse movement
chart showing the actual candles
entry marker
exit marker

The losing trades are especially important.

The user wants to be able to click something like:

KISS-00008

and immediately identify the exact trade.

This is important because the next stage is AI training/feedback.

We don't need to spend much time looking at winners.

We already know winners worked.

We want to understand:

Why did this losing trade happen?

9. Examples of what we learned from the charts

One NVDA example showed:

LONG entry around 196.51
exit around 192.57
approximately -2.0%
transition was SHORT → LONG
trailing trend change eventually caused the exit

The visual inspection made it obvious that the execution was not good enough.

The trade entered after the favorable move had already developed and exited after the adverse move had developed.

Another important observation:

We were sometimes too cautious.

The strategy correctly understood the direction, but waited so long for confirmation that the useful part of the move had already happened.

10. Why NVDA is an important test

NVDA is particularly useful because its chart can contain:

many V-shaped transitions
rapid reversals
large jumps
very fast trend changes

Therefore it is a difficult stress test for the strategy.

The user specifically noticed:

NVDA has many Vs and very fast transitions.

If the new execution method improves NVDA, that would be meaningful evidence.

11. Current experiment

We created a separate experimental engine rather than modifying the whole existing system.

File:

engine/kiss_execution_5m.py

Latest project update was pulled from GitHub successfully.

Latest commit at the time of this handoff:

c14b81c

The experiment is intended to keep the main KISS concept intact while changing execution resolution:

30m trend → 5m execution

It includes:

30m market-state detection
5m execution
transition confirmation
trailing protection
RSI emergency protection
Trade IDs
P&L
maximum favorable/adverse movement
entry/exit information

The intention is to compare this experiment against the existing KISS backtest.

12. Very important: don't reinvent the strategy

The strategy has already been defined.

We do not want every new experiment to invent another strategy.

The question should always be:

Does this implementation execute the KISS strategy better?

Not:

"Can we add another indicator?"

Not:

"Can we optimize 50 parameters?"

Not:

"Can we make another complicated prediction model?"

The goal is consistency.

13. The fundamental research question now

We believe the strategy itself is sound enough to continue testing.

The current problem is:

TIMING

Specifically:

Entry

Can we enter closer to the actual beginning of the new trend instead of after much of the movement has already occurred?

Exit

Can we exit close enough to the real trend reversal without being fooled by noise?

Noise

Can we distinguish:

minor temporary reversal

from

real major trend reversal

without making the system unnecessarily complicated?

14. Current philosophy about noise

The market will always contain unexpected movement.

We cannot eliminate noise.

Therefore the objective is not:

"Predict every candle."

The objective is:

Ignore insignificant noise while reacting quickly enough to meaningful change.

This is the central balance we need to solve.

15. What we should NOT change

Unless a real bug is discovered:

broker selection
symbol selection
direction selection
existing data acquisition
existing working infrastructure
overall KISS philosophy

Do not disturb working parts simply because we are experimenting with execution.

16. What we should compare

For the same:

broker
symbol
direction
historical period

compare:

Existing KISS

30m decision / existing execution

versus

New experiment

30m strategic trend + 5m execution

Compare primarily:

number of losing trades
average losing trade
worst losing trade
total P&L
entry delay
exit delay
maximum adverse movement
maximum favorable movement
number of trades caused by noise

Win rate is useful, but not the only measurement.

A strategy can have a lower win rate and still be better if it cuts its losses and captures larger moves.

17. Long-term goal

The system should eventually have:

ONE KISS strategy

with different "memories/notebooks" for:

live trading
backtesting
tuning
AI analysis/training

They should all follow the same strategy rules.

They should not each invent their own interpretation.

18. The big picture

The project is trying to answer a very simple question:

Can we make money by correctly identifying trend transitions and executing them at the right time, without drowning the system in indicators?

The current answer is promising enough to continue.

The biggest remaining obstacle is:

NOISE + EXECUTION TIMING

We already know that being too late is bad.

Now we need to find the point where we are:

fast enough to catch the move

while still being:

stable enough not to react to noise.

That is the next major experiment.

Starting point for the new chat

When continuing this project, start from this report.

The immediate task is not to redesign the strategy.

It is to test the 30m trend / 5m execution experiment against the existing KISS implementation, especially on NVDA, and inspect the losing trades.

The most important question is:

Did 5-minute execution reduce the late-entry and late-exit problem without creating excessive noise trades?

If yes, we continue refining it.

If no, we learn exactly where and why it failed.

We are not trying to make the system complicated. We are trying to make the simple idea execute correctly.

####################################################################################################
###################################################################################################

AiMn Trade — Project Handoff Report
KISS Strategy / Backtest / 5-Minute Execution Experiment

Date: August 30, 2026

1. What we are building

This is the AiMn trading system. The most important part of the system is the trading strategy.

The guiding philosophy is:

KISS — Keep It Simple, Stupid.

We deliberately moved away from the idea that a trading system needs dozens of indicators and complicated formulas.

The strategy is fundamentally about recognizing only three market states:

LONG — market is trending upward
SHORT — market is trending downward
FLAT — sideways market

The important thing is the transition between trends, not the particular shape of the chart.

Examples:

falling → rising = V-Long
rising → falling = V-Short
But the chart can also make W, M, U, inverted U, etc.

The shape is not the strategy. The transition is the strategy.

2. Core KISS trading rules
Entries

We enter when the market changes into a directional trend:

SHORT → LONG = LONG entry
LONG → SHORT = SHORT entry
FLAT → LONG = LONG entry
FLAT → SHORT = SHORT entry

We do not enter simply because:

LONG → FLAT
SHORT → FLAT

Those are situations where we wait for the next meaningful directional transition.

Exits

While in a trade, we follow the trend.

A meaningful reversal should eventually cause an exit.

A trailing mechanism is used to protect the trade, but minor noise must not immediately throw us out.

The original strategy specifies confirmation of approximately 2–4 candles so that a temporary local reversal does not automatically become an exit.

Protection

RSI is not the strategy.

RSI is an emergency safety mechanism for unexpected events.

For example:

unexpected very bad news while LONG
unexpected extremely good news while SHORT

In those cases, waiting for the normal trend-transition detection may be too slow.

Therefore:

Trend transition = normal decision mechanism.
RSI = emergency protection.
Stop loss = final protection.

3. Very important strategic principle

The goal is not to predict everything.

The goal is to get on the correct side of the transition as early as reasonably possible.

The problem we discovered is that the system can be too cautious.

A trade can be theoretically correct but still lose money because:

We entered too late, after much of the move had already happened.

Then the system may also:

exit too late, after the trend has already reversed significantly.

That is currently one of our biggest concerns.

4. What we discovered from the loser charts

We deliberately decided to concentrate on losing trades, rather than spending our time studying winners.

The reason is simple:

We already know the system can make money.
The losers tell us where the strategy is wasting money.

The new KISS backtest produces a Losers section where individual Trade IDs can be selected and inspected.

The chart shows:

candles
entry
exit
Trade ID
entry/exit prices
transition
exit reason
RSI
maximum favorable movement
maximum adverse movement

This makes it possible to visually ask:

"Why did we enter here?"

and

"Why did we wait until here to exit?"

This is much more useful than simply looking at a total P&L number.

5. Important discovery from NVDA

NVDA became an especially important test because its chart contains many rapid reversals / V-shaped transitions and sudden jumps.

We observed:

The KISS system entered too late and exited too late.

This was particularly obvious in NVDA.

The concern was not that the basic direction-selection system was necessarily wrong.

The concern was execution timing.

The transition can happen very quickly, so a 30-minute candle can cause the system to recognize the move much later than the actual turning point.

6. The timeframe idea

We therefore proposed a very important experiment:

30-minute candles

Use 30m for the major/global trend decision.

This answers:

"What is the market's major direction?"

5-minute candles

Use 5m for execution.

This answers:

"When exactly should I enter or exit?"

The idea is:

30m decides WHAT.
5m decides WHEN.

This should potentially reduce the late-entry and late-exit problem.

But we do not assume it works.

The only real test will tell us.

7. Current experiment

We deliberately decided:

Do not make many changes at once.

The first experiment is simply:

30m trend decision + 5m execution.

We do not want to simultaneously introduce a large collection of indicators, filters, parameters, or optimization tricks.

That would make it impossible to know what actually improved the results.

8. Important existing-system constraint

The following already works and should NOT be changed:

broker selection
symbol selection
direction selection
candle/data selection

The explicit rule is:

If it isn't broken, don't touch it.

The new strategy/execution experiment should therefore be isolated from the existing selection machinery as much as possible.

9. Independent implementation

We decided not to modify the existing complicated machinery unnecessarily.

Instead, the new experiment should be clean and independent.

A new engine was created:

engine/kiss_execution_5m.py

It implements the experimental:

30m major trend / 5m execution

approach.

The intent is to compare the result against the previous KISS implementation without contaminating the existing system.

10. Current Git status

The latest Git pull was:

Already up to date.

The relevant recent commit added:

engine/kiss_execution_5m.py
kiss_backtest_routes.py

The latest successful commands were:

cd ~/aimn-trade-final
git pull origin main
python -m py_compile engine/kiss_execution_5m.py kiss_backtest_routes.py
touch /var/www/meirniv_pythonanywhere_com_wsgi.py

There were no Python compilation errors.

11. Existing KISS backtest

The KISS backtest page is working.

Example:

/kiss_backtest?broker_id=2&symbol=NVDA&direction=LONG&timeframe=30m

It displays:

total trades
total P&L
win rate
losers
detected transitions
list of losing trades
Trade IDs
individual charts
entry/exit markers

This is exactly the kind of report we wanted because it allows the human to inspect the actual bad trades.

12. What we saw in the charts

One NVDA example showed:

KISS-00008
LONG
Entry: 2026-07-06 15:00 @ 196.514
Exit: 2026-07-07 14:30 @ 192.57
P&L: -2.007%
Exit: TRAILING_TREND_CHANGE

The visual conclusion was:

Entry was too late. Exit was too late.

Another important observation was that the system can be too cautious around very fast transitions.

13. The "ScSt" question

There was a chart displaying something called ScSt.

We concluded that this was not important to the KISS strategy and does not need to become part of the strategy.

The strategy should remain simple.

14. Strategy documentation

The strategy has already been documented as the central KISS strategy.

The important document is:

doc/strategy/AiMn-KISS-Strategy-V3-full.md

It explicitly describes:

LONG / SHORT / FLAT
transitions
V-Long / V-Short
transition confirmation
separate memory for live/backtest/tuner
trailing protection
emergency RSI
stop loss
shared strategy engine concept

The guiding architectural idea is:

ONE STRATEGY, ONE ENGINE, DIFFERENT MEMORIES

Live trading, backtesting and tuning should each maintain their own state/history rather than interfering with each other.

15. Why separate memory matters

This was discussed carefully because it is easy for an AI or programmer to misunderstand.

Think of each application as having its own notebook:

Live trading has its notebook.
Backtest has its notebook.
Tuner has its notebook.

They all use the same strategy, but each keeps its own memory of:

what trend was previously detected
when it happened
current trade state
peak/trough information
etc.

This prevents one application from confusing its state with another application.

16. Important "go backward" idea

Another important part of the strategy is how we find the most recent transition.

Instead of repeatedly scanning the entire historical dataset forward from the beginning, the system should:

Start at the newest candle and move backward to find the most recent transition.

Once that transition is known, save it in memory/database.

Next time, start from the newest data and only process what is new.

The purpose is both:

efficiency
avoiding repeatedly rediscovering the same history

This concept should be explained simply in documentation because even an AI/programmer can misunderstand it.

17. Current main problem

The current question is not:

"Can we make a complicated indicator system?"

It is:

Can we execute the correct KISS trend-transition strategy earlier and exit at the correct transition without being fooled by minor noise?

Specifically:

Entry problem

We may recognize the correct transition but enter after the price has already moved too far.

Exit problem

We may recognize the reversal but exit after too much of the move has already been lost.

Noise problem

A temporary local reversal should not immediately close a trade.

We need to distinguish:

minor noise

from

a genuine major trend reversal.

18. Current testing philosophy

We are experimenting scientifically.

Do not change ten things at once.

The process should be:

Establish the KISS baseline.
Test 30m decision + 5m execution.
Compare the results.
Look primarily at losers.
Inspect individual charts.
Identify the reason for each loss.
Make one meaningful strategy change.
Test again.
Compare.

The human visual inspection of the losing charts is an important source of feedback for future AI training.

19. What we ultimately want

The goal is not merely a higher win rate.

We want:

fewer unnecessary losing trades
earlier correct entries
earlier correct exits
protection against sudden unexpected reversals
resistance to minor noise
consistent behavior across symbols
a simple strategy that can be understood and audited
the same strategy used by backtest, tuner and eventually live trading

Most importantly:

We want to be on the other side of the trades that currently lose money.

The system already demonstrated that it can make money even while carrying substantial losers, so reducing the bad trades could potentially make a meaningful difference.

20. Current immediate task

The immediate task is:

Test the new 30m / 5m execution experiment.

Use NVDA as an important test because:

it has rapid transitions
it contains many V-shaped reversals
it has sudden jumps
the old implementation was clearly too late

Then compare the new results with the old KISS results.

Do not modify broker/symbol/direction selection.

Do not add a pile of indicators.

Do not optimize blindly.

First determine whether the simple 30m → 5m change actually solves the timing problem.

The guiding sentence for the new chat

We already know what strategy we want. Now we are trying to make the execution happen at the right time without making KISS complicated.

Current state

The latest code has been pulled successfully and compiled successfully.

engine/kiss_execution_5m.py

is now in the project.

The next job is to run it, inspect the fresh results, especially NVDA losers, and compare them against the previous KISS 30m implementation.

Do not reinvent the strategy. Improve the execution of the strategy we already agreed on.

You can paste this entire report into the new chat. It should give the new chat enough context to pick up the work without you having to tell the whole story again.



#######################################################################################################################
#######################################################################################################################


AiMn Trade — Strategy & Project Handoff Report
Purpose
The most important part of this project is the trading strategy. The guiding principle is KISS — Keep It Simple.
We want substantially fewer losing trades, especially losses caused by entering too late or exiting too late.
Do not change the broker / symbol / direction / candle selection unless testing proves it is broken.
KISS Strategy
The market has three states:
    • LONG = generally moving up
    • SHORT = generally moving down
    • FLAT = sideways
The strategy is based on trend transitions, not a collection of indicators.
Entries
    • SHORT -> LONG = enter LONG
    • LONG -> SHORT = enter SHORT
    • FLAT -> LONG = enter LONG
    • FLAT -> SHORT = enter SHORT
Wait
    • LONG -> FLAT = wait
    • SHORT -> FLAT = wait
The chart shape is not the strategy. V, W, M, U and other shapes are only visual descriptions.
    • V-Long = falling -> rising
    • V-Short = rising -> falling
The transition is what matters.
Why the losing-trade charts matter
We deliberately concentrate on losers, not winners.
The charts have shown two major problems:
    1. Entry too late — the system recognizes the correct direction only after much of the move has already happened.
    2. Exit too late — the system recognizes the reversal after the price has already moved substantially against the position.
NVDA is an important stress test because its chart can contain rapid V-like reversals and large jumps.
The objective is to get onto the correct side of the transition earlier and get off when the real transition occurs.
Timeframe Experiment
The current experiment is:
30m candles = major/global trend decision
5m candles = execution timing
One 30m candle contains six 5m candles. The idea is that the 5m data can locate the actual execution point much closer to the transition instead of waiting for the full 30m candle.
This is an experiment. Only the real backtest can prove whether it improves the results.
Do not assume it is better before testing it.
Noise / Confirmation
Small local reversals can occur while a trade is running.
Example:
LONG -> brief SHORT -> LONG
That can be noise.
We therefore do not want to exit because of one noisy candle. A real transition should survive a safety/confirmation zone of roughly 2–4 candles.
The new implementation uses a 2-of-3 style confirmation for the 5m execution experiment.
A minor reversal that disappears inside the confirmation window should not throw us out. A stronger reversal that survives the safety zone can trigger the exit.
RSI
RSI is emergency protection only.
It is not the normal entry strategy.
Its purpose is to protect against an unexpected violent move, such as bad news while LONG or exceptionally good news while SHORT, where waiting for the normal transition could take too long.
The hierarchy is:
    1. Trend transition = normal decision
    2. Trailing / meaningful transition = normal exit protection
    3. RSI = emergency exit
    4. Stop loss = final protection
Trailing Exit
The KISS design uses approximately a 1.5% trailing distance from the favorable peak/trough.
For LONG, remember the highest favorable price.
For SHORT, remember the lowest favorable price.
A trailing reversal should not immediately exit on one noisy candle; it should be confirmed.
Remembering Transitions
An important implementation idea is to start from the newest candle and move backward to find the most recent meaningful transition rather than repeatedly scanning the whole history from the beginning.
The system remembers:
WHAT = trend/state
WHEN = timestamp
Each application should have its own memory/database area:
    • live trading
    • backtest
    • tuner
They should not overwrite each other's memory.
Backtest / Loser Inspection
A separate KISS backtest was created so the strategy can be tested without unnecessarily disturbing the existing tuner.
Important files include:
    • engine/kiss_backtest.py
    • kiss_backtest_routes.py
    • templates/kiss_backtest.html
    • engine/kiss_execution_5m.py
The KISS backtest displays total trades, P&L, win rate, losers, transitions, and detailed losing trades.
Each loser can be selected by Trade ID so we can quickly inspect:
    • entry time
    • entry price
    • exit time
    • exit price
    • transition
    • exit reason
    • maximum favorable movement
    • maximum adverse movement
    • RSI at entry/exit
The chart is an investigation tool, not a winner showcase.
Current 5m Experiment
A new independent file was added:
engine/kiss_execution_5m.py
It implements:
30m trend decision + 5m execution
It intentionally does not create a new indicator-heavy strategy.
It includes:
    • 30m market-state detection
    • 30m transitions
    • 5m execution confirmation
    • V-shape description
    • trailing protection
    • RSI emergency exit
    • Trade IDs
    • entry/exit data
    • favorable/adverse movement measurements
Latest related Git state reported in the previous session:
c14b81c
Testing Plan
Do not change ten things at once.
First compare the existing KISS backtest with:
30m decision + 5m execution
Keep the same broker, symbol, direction, and historical data.
NVDA is a particularly useful stress test because the previous NVDA SHORT result showed entry and exit were both much too late.
Judge the experiment by more than total profit:
    1. Number of losers
    2. Average losing trade
    3. Maximum adverse movement
    4. Entry timing
    5. Exit timing
    6. Win rate
    7. Total P&L
    8. Whether entry occurs after the move is already exhausted
    9. Whether exit occurs after the reversal is already large
    10. Whether 5m execution actually reduces those problems
Do Not Reinvent the Strategy
The goal is one consistent strategy used by:
    • backtesting
    • tuning
    • eventually live trading
Experiments should initially remain isolated so they can be compared cleanly.
Do not:
    • change broker selection
    • change symbol selection
    • change direction selection
    • add a pile of indicators
    • rewrite working parts unnecessarily
    • assume 5m is better before testing
    • mix the experiment into the existing tuner without comparison
Do:
    • inspect the current repository
    • understand the KISS backtest
    • understand the routes and templates
    • test the 30m/5m experiment
    • concentrate on losing trades
    • compare entry and exit timing
    • make one change at a time
    • use Trade IDs for individual losers
    • keep the strategy simple and explainable
The Core Philosophy
Most trades do not make money.
We want to be on the other side of that statistic.
A strategy should be simple enough that an ordinary person looking at a losing chart can understand why the trade was bad.
KISS — Keep It Simple.
One-sentence version
30m tells us WHAT the market is doing; 5m helps determine WHEN to act; the KISS trend transition remains the strategy.






##########################################################################################################################
##########################################################################################################################




AiMn TRADE — PROJECT HANDOFF

We are developing the AiMn Trade system.

IMPORTANT:
Do NOT reinvent the existing broker / symbol / direction / candle selection.
That part works. If it isn't broken, DO NOT TOUCH IT.

MAIN STRATEGY — KISS
Keep It Simple.

We moved away from the indicator-heavy strategy.

Market has only 3 important states:
LONG
SHORT
FLAT

The important thing is the TRANSITION between states.

ENTER:
FLAT → LONG
FLAT → SHORT
LONG → SHORT
SHORT → LONG

WAIT / DO NOT ENTER:
LONG → FLAT
SHORT → FLAT

V shapes, inverted V, W, M, U, etc. are useful descriptions but are NOT the strategy.
The transition is the strategy.

During a trade:
Small reversals are NOISE.
Do not immediately exit because of one candle or a small local reversal.

A real transition should be confirmed over roughly 2–4 candles.
Trailing take profit is used to detect/protect against a meaningful reversal.

RSI is NOT the strategy.
RSI is emergency protection only — especially for a sudden event/news shock where waiting for normal trend detection would be too slow.

Stop loss is the final protection.

MAIN PROBLEM WE ARE SOLVING:
Our entries and exits were often TOO LATE.

This was especially obvious on NVDA, which has many rapid V-shaped transitions and sudden jumps.
We can enter near the end of a move and then exit near the bottom — exactly backwards from what we want.

IMPORTANT NEW EXPERIMENT:
Use two timeframes:

30 MINUTES = major/global trend decision
5 MINUTES = execution timing

The idea:
30m tells us WHAT the market is doing.
5m tells us WHEN to actually enter or exit.

We are deliberately making only one major change at a time so we can compare results.

CURRENT EXPERIMENT FILE:
engine/kiss_execution_5m.py

It is intentionally independent from the old system.

Recent Git commit:
c14b81c

The current experiment uses:
- 30m trend
- 5m execution
- 2-of-3 confirmation
- trailing protection
- RSI emergency exit
- Trade IDs
- loser-focused charts

We have a KISS backtest page:
 /kiss_backtest

The chart displays losing trades and gives each trade an ID so we can inspect individual bad trades.

The user does NOT care about looking at winners right now.
The losers teach us where the strategy is wrong.

OBSERVATIONS:
1. Some previous entries were clearly too late.
2. Some exits were clearly too late.
3. Despite many losers, the strategy can still make money.
4. Therefore the goal is NOT simply "more trades."
5. The goal is to substantially reduce bad/late trades while preserving the good transition logic.
6. NVDA is an especially useful test because its transitions can happen very quickly.
7. The user believes the core KISS strategy is correct and wants execution timing improved.

CURRENT THINKING:
The 30m timeframe should determine the major transition.
The 5m timeframe should allow us to act much closer to the actual transition instead of waiting 30 minutes for the next large candle.

DO NOT:
- add a pile of indicators
- modify broker selection
- modify symbol selection
- modify direction selection
- redesign the whole application
- mix this experiment into the old tuner unnecessarily
- optimize blindly for one symbol

TESTING PHILOSOPHY:
One change at a time.
Run real backtests.
Look primarily at losers.
Compare old KISS versus new KISS 30m/5m.
Use the Trade ID and chart to understand WHY each loser happened.

NEXT LIKELY IMPROVEMENT:
The current 5m experiment waits for confirmation before execution.
Because our main problem is "too late," investigate whether execution should happen on the SECOND confirming 5m candle rather than waiting for the full three-candle window.

This keeps the safety idea (2-candle confirmation) but reduces execution delay.

Do NOT change anything else until that comparison is tested.

The user prefers complete files/code or very simple Bash commands rather than patches.



