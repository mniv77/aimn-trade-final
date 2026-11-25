
/*
 AIMn SHORT Entry / Exit Visual Research V4.2
 Research only. NO REAL ORDERS.
 Compatible with existing V4 browser storage.
*/
(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const next = $('next');
  const main = document.querySelector('main');
  if (!next || !main) return;

  const oldForm = $('aiResponse')?.closest('section');
  if (oldForm) oldForm.style.display = 'none';
  $('trendNoiseResearch')?.remove();

  const VERSION = 'aimn-enter-short-visual-v4';
  const PREFIX = 'aimn_enter_short_visual_v4:';

  const entryReasons = [
    'MAJOR_LONG_TO_SHORT',
    'EARLY_PEAK_REVERSAL',
    'OTHER'
  ];

  const exitReasons = [
    'REPEATED_SUPPORT',
    'PROTECT_PROFIT',
    'SHORT_TO_LONG',
    'STOP_LOSS',
    'OTHER'
  ];

  const rejectReasons = [
    'LATE_ENTRY',
    'MID_TREND',
    'MINOR_V_NOISE',
    'SIDEWAYS',
    'OTHER'
  ];

  const panel = document.createElement('section');
  panel.id = 'trendNoiseResearch';

  panel.innerHTML = `
    <h2>AIMn — SHORT Entry / Exit Research V4.2</h2>
    <p>
      Blind visual research only.
      Decisions are saved before the next five candles appear.
      No real trading orders.
    </p>

    <h3 id="simplePosition">Loading chart...</h3>
    <p id="v4TradeStatus">Research position: loading...</p>

    <div class="row" style="gap:12px;flex-wrap:wrap">
      <button id="v4Wait" type="button">
        WAIT · Next 5
      </button>
      <button id="v4Enter" type="button"
        style="background:#176b56">
        ENTER_SHORT · Next 5
      </button>
      <button id="v4Exit" type="button"
        style="background:#8b3651">
        EXIT_SHORT · Next 5
      </button>
      <button id="v4Reject" type="button"
        style="background:#91511d">
        REJECT · Next 5
      </button>
    </div>

    <div class="row"
      style="margin-top:12px;gap:12px;flex-wrap:wrap">
      <label>
        Decision reason
        <select id="v4Reason">
          <option value="MAJOR_LONG_TO_SHORT">
            Major LONG to SHORT transition
          </option>
          <option value="EARLY_PEAK_REVERSAL">
            Early peak reversal
          </option>
          <option value="REPEATED_SUPPORT">
            Repeated support / possible V-LONG
          </option>
          <option value="PROTECT_PROFIT">
            Protect SHORT profit
          </option>
          <option value="SHORT_TO_LONG">
            Possible SHORT to LONG transition
          </option>
          <option value="STOP_LOSS">
            Protective stop
          </option>
          <option value="LATE_ENTRY">
            Entry too late
          </option>
          <option value="MID_TREND">
            Mid-trend entry
          </option>
          <option value="MINOR_V_NOISE">
            Minor V / noise
          </option>
          <option value="SIDEWAYS">
            Sideways / uncertain
          </option>
          <option value="OTHER">
            Other
          </option>
        </select>
      </label>

      <label>
        Optional observation
        <input id="v4Note" type="text" size="44"
          placeholder="Visible evidence only">
      </label>
    </div>

    <div class="row"
      style="margin-top:12px;gap:12px;flex-wrap:wrap">
      <label>
        Commission per side (%)
        <input id="v4Commission" type="number"
          value="0.10" min="0" max="10"
          step="0.01" style="width:85px">
      </label>
    </div>

    <p id="v4ReasonHint"></p>

    <div class="row" style="margin-top:12px;gap:12px">
      <button id="v4Export" type="button">
        Export Research JSON
      </button>
      <button id="v4Reset" type="button">
        Start New Session
      </button>
      <span id="v4Count"></span>
    </div>

    <p id="v4Message" role="status"
      style="color:#ffd37c"></p>

    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>UTC cutoff</th>
            <th>Decision</th>
            <th>Reason</th>
            <th>Evidence / Trade result</th>
            <th>Next 5 candles</th>
            <th>Audit</th>
          </tr>
        </thead>
        <tbody id="v4History"></tbody>
      </table>
    </div>

    <small>
      Browser storage is dataset-specific.
      Export JSON regularly.
      Results are research estimates, not broker fills.
    </small>
  `;

  main.appendChild(panel);

  const storage = (() => {
    try {
      const k = '__aimn_storage_test__';
      localStorage.setItem(k, '1');
      localStorage.removeItem(k);
      return localStorage;
    } catch {
      return null;
    }
  })();

  let records = [];
  let busy = false;
  let sessionKey = null;
  let datasetId = null;
  let lastObservedDataset = null;
  let restoring = false;
  let pending = null;

  const message = s => {
    $('v4Message').textContent = s;
  };

  function position() {
    if (typeof candles === 'undefined' ||
        !Array.isArray(candles) ||
        !candles.length ||
        typeof visible !== 'number' ||
        visible < 1 ||
        visible > candles.length) return null;

    const c = candles[visible - 1];

    return {
      time: c.time,
      utc: new Date(c.time * 1000).toISOString(),
      close: Number(c.close),
      count: visible
    };
  }

  function identity() {
    if (typeof candles === 'undefined' ||
        !Array.isArray(candles) ||
        !candles.length) return null;

    const first = candles[0];
    const last = candles[candles.length - 1];

    // EXACT original V4 identity format.
    return JSON.stringify([
      selectedSymbol,
      selectedBroker,
      selectedTimeframe,
      typeof sourceName === 'string' ? sourceName : '',
      candles.length,
      first.time,
      first.open,
      first.high,
      first.low,
      first.close,
      last.time,
      last.open,
      last.high,
      last.low,
      last.close
    ]);
  }

  function keyFor(id) {
    return PREFIX + encodeURIComponent(id);
  }

  function persist() {
    if (!storage || !sessionKey) {
      message('Browser storage unavailable.');
      return false;
    }

    try {
      storage.setItem(sessionKey, JSON.stringify({
        schema: VERSION,
        dataset_id: datasetId,
        visible_candles: visible,
        records: records,
        updated_at_utc: new Date().toISOString()
      }));
      return true;
    } catch (e) {
      message('Save failed: ' + e.message);
      return false;
    }
  }

  // Reconstruct research position from saved judgments.
  // Accidental records do not count.
  function activeEntry() {
    let entry = null;

    for (const r of records) {
      if (r.accidental_click?.excluded_from_scoring) {
        continue;
      }

      if (r.decision === 'ENTER_SHORT' && !entry) {
        entry = r;
      }

      if (r.decision === 'EXIT_SHORT') {
        entry = null;
      }
    }

    return entry;
  }

  function signed(n) {
    return (n >= 0 ? '+' : '') + n.toFixed(3) + '%';
  }

  function history() {
    const tbody = $('v4History');
    tbody.replaceChildren();

    records.forEach(r => {
      const tr = document.createElement('tr');
      const outcome = r.outcome;

      let evidence = r.human_evidence || '—';

      if (r.trade_result) {
        const t = r.trade_result;
        evidence +=
          ' | SHORT ' +
          t.entry_close.toFixed(2) +
          ' to ' +
          t.exit_close.toFixed(2) +
          ' | Gross ' + signed(t.gross_pct) +
          ' | Net ' + signed(t.net_pct);
      }

      const values = [
        r.cutoff_utc,
        r.decision,
        r.reason || '—',
        evidence,
        outcome
          ? outcome.revealed_candles +
            ' candles; ' +
            signed(outcome.price_change_pct)
          : 'Not revealed'
      ];

      values.forEach(value => {
        const td = document.createElement('td');
        td.textContent = value;
        tr.appendChild(td);
      });

      const audit = document.createElement('td');

      if (r.decision !== 'WAIT') {
        const annotate = document.createElement('button');
        annotate.type = 'button';
        annotate.textContent = 'Annotate';

        annotate.onclick = () => {
          const proposed = prompt(
            'Post-reveal reason annotation:',
            r.reason
          );

          if (!proposed || !proposed.trim()) return;

          if (!confirm(
            'Original blind decision remains unchanged. Continue?'
          )) return;

          const previous = r.post_reveal_annotations;

          r.post_reveal_annotations = [
            ...(previous || []),
            {
              original_reason: r.reason,
              proposed_reason: proposed.trim(),
              annotated_at_utc: new Date().toISOString(),
              classification: 'POST_REVEAL_NOT_BLIND'
            }
          ];

          if (!persist()) {
            if (previous === undefined) {
              delete r.post_reveal_annotations;
            } else {
              r.post_reveal_annotations = previous;
            }
            return;
          }

          history();
        };

        audit.appendChild(annotate);
      }

      if (r.post_reveal_annotations?.length) {
        const flag = document.createElement('span');
        flag.textContent =
          ' · post-reveal note (' +
          r.post_reveal_annotations.length + ')';
        audit.appendChild(flag);
      }

      if (r.accidental_click?.excluded_from_scoring) {
        const flag = document.createElement('strong');
        flag.textContent = ' · ACCIDENTAL — EXCLUDE';
        flag.style.color = '#ffd37c';
        audit.appendChild(flag);
      } else {
        const mark = document.createElement('button');
        mark.type = 'button';
        mark.textContent = 'Mark Accidental';
        mark.style.background = '#76503b';
        mark.style.marginLeft = '6px';

        mark.onclick = () => {
          const explanation = prompt(
            'Explain the accidental decision:',
            'Unintended click. Exclude from scoring.'
          );

          if (!explanation || !explanation.trim()) return;

          if (!confirm(
            'Flag candle ' + r.visible_candles +
            ' as accidental? Original record remains.'
          )) return;

          const previous = r.accidental_click;

          r.accidental_click = {
            excluded_from_scoring: true,
            classification: 'ACCIDENTAL_INPUT_POST_REVEAL',
            explanation: explanation.trim(),
            marked_at_utc: new Date().toISOString(),
            original_decision: r.decision,
            original_reason: r.reason
          };

          if (!persist()) {
            if (previous === undefined) {
              delete r.accidental_click;
            } else {
              r.accidental_click = previous;
            }
            return;
          }

          history();
          refresh();
        };

        audit.appendChild(mark);
      }

      tr.appendChild(audit);
      tbody.appendChild(tr);
    });

    const excluded = records.filter(
      r => r.accidental_click?.excluded_from_scoring
    ).length;

    $('v4Count').textContent =
      records.length + ' saved judgments (' +
      excluded + ' excluded)';

    $('v4Export').disabled = !records.length;
  }

  function restoreForDataset() {
    const id = identity();

    if (!id || id === lastObservedDataset) return;

    lastObservedDataset = id;
    datasetId = id;
    sessionKey = keyFor(id);
    records = [];

    if (!storage) {
      busy = true;
      history();
      message('Browser storage unavailable. Research blocked.');
      refresh();
      return;
    }

    try {
      const raw = storage.getItem(sessionKey);

      if (!raw) {
        history();
        message('New blind research session.');
        refresh();
        return;
      }

      const saved = JSON.parse(raw);

      if (saved.schema !== VERSION ||
          saved.dataset_id !== id ||
          !Array.isArray(saved.records) ||
          !Number.isInteger(saved.visible_candles) ||
          saved.visible_candles < 20 ||
          saved.visible_candles > candles.length) {
        throw Error('Invalid saved session');
      }

      records = saved.records;

      if (visible > saved.visible_candles) {
        busy = true;
        history();
        message(
          'Recovery blocked: chart is ahead of saved cutoff. ' +
          'Do not rewind a revealed chart.'
        );
        refresh();
        return;
      }

      if (visible < saved.visible_candles) {
        restoring = true;
        visible = saved.visible_candles;
        render();
        restoring = false;
      }

      history();
      refresh();

      message(
        'Recovered ' + records.length +
        ' judgments at candle ' + visible + '.'
      );

    } catch (e) {
      busy = true;
      records = [];
      history();
      message(
        'Recovery error: ' + e.message +
        '. Existing browser data was not deleted.'
      );
      refresh();
    }
  }

  function selectReason(action) {
    const select = $('v4Reason');

    const allowed =
      action === 'ENTER_SHORT' ? entryReasons :
      action === 'EXIT_SHORT' ? exitReasons :
      action === 'REJECT_SHORT_CANDIDATE'
        ? rejectReasons : [];

    for (const option of select.options) {
      option.hidden = !allowed.includes(option.value);
      option.disabled = option.hidden;
    }

    if (action === 'ENTER_SHORT') {
      select.value = 'MAJOR_LONG_TO_SHORT';
    } else if (action === 'EXIT_SHORT') {
      select.value = 'REPEATED_SUPPORT';
    } else if (action === 'REJECT_SHORT_CANDIDATE') {
      select.value = 'LATE_ENTRY';
    }

    select.disabled = action === 'WAIT';

    $('v4ReasonHint').textContent =
      action === 'WAIT'
        ? 'WAIT saves NO_ENTRY_YET automatically.'
        : 'Review the reason, then confirm ' + action + '.';
  }

  function refresh() {
    if (restoring) return;

    const p = position();
    const entry = activeEntry();

    $('simplePosition').textContent = p
      ? selectedSymbol + ' · ' + p.utc +
        ' · Candle ' + p.count + ' / ' + candles.length
      : 'Waiting for chart...';

    const blocked =
      busy || !p || p.count >= candles.length;

    $('v4Wait').disabled = blocked;
    $('v4Reject').disabled = blocked;
    $('v4Enter').disabled = blocked || !!entry;
    $('v4Exit').disabled = blocked || !entry;

    $('v4TradeStatus').textContent = entry
      ? 'OPEN RESEARCH SHORT — candle ' +
        entry.visible_candles +
        ' at $' + Number(entry.cutoff_close).toFixed(2)
      : 'Research position: none';

    next.disabled = true;

    for (const id of ['back', 'reset', 'step', 'initial']) {
      if ($(id)) $(id).disabled = true;
    }

    if ($('file')) {
      $('file').disabled = records.length > 0;
    }

    $('v4Export').disabled = !records.length;
  }

  function recordAndReveal(decision) {
    if (busy) return;

    const before = position();
    const entry = activeEntry();

    if (!before || before.count >= candles.length) {
      message('End of dataset.');
      return;
    }

    if (!sessionKey || !storage) {
      message('Storage is not ready.');
      return;
    }

    if (decision === 'EXIT_SHORT' && !entry) {
      message('No open research SHORT to exit.');
      return;
    }

    if (decision === 'ENTER_SHORT' && entry) {
      message('A research SHORT is already open.');
      return;
    }

    const reason = decision === 'WAIT'
      ? 'NO_ENTRY_YET'
      : $('v4Reason').value;

    const allowed =
      decision === 'ENTER_SHORT' ? entryReasons :
      decision === 'EXIT_SHORT' ? exitReasons :
      decision === 'REJECT_SHORT_CANDIDATE'
        ? rejectReasons : [];

    if (decision !== 'WAIT' &&
        !allowed.includes(reason)) {
      message('Select a valid reason.');
      return;
    }

    const note = $('v4Note').value.trim();

    if (reason === 'OTHER' && !note) {
      message('Please describe the OTHER reason.');
      return;
    }

    const commission = Number($('v4Commission').value);

    if (decision === 'EXIT_SHORT' &&
        (!Number.isFinite(commission) ||
         commission < 0 || commission > 10)) {
      message('Invalid commission percentage.');
      return;
    }

    const record = {
      schema: VERSION,
      symbol: selectedSymbol,
      broker_id: selectedBroker,
      timeframe: selectedTimeframe,
      source_file:
        typeof sourceName === 'string' ? sourceName : '',
      research_direction: 'SHORT',
      cutoff_unix: before.time,
      cutoff_utc: before.utc,
      cutoff_close: before.close,
      visible_candles: before.count,
      decision,
      reason,
      human_evidence: note,
      frozen_at_utc: new Date().toISOString(),
      ai_assessment: null,
      outcome: null
    };

    if (decision === 'EXIT_SHORT') {
      const entryPrice = Number(entry.cutoff_close);
      const exitPrice = before.close;

      if (!(entryPrice > 0 && exitPrice > 0)) {
        message('Invalid trade prices.');
        return;
      }

      const gross =
        100 * (entryPrice - exitPrice) / entryPrice;

      record.trade_result = {
        research_only: true,
        entry_cutoff_unix: entry.cutoff_unix,
        entry_cutoff_utc: entry.cutoff_utc,
        entry_visible_candles: entry.visible_candles,
        entry_close: entryPrice,
        exit_close: exitPrice,
        exit_cutoff_unix: before.time,
        exit_cutoff_utc: before.utc,
        commission_pct_per_side: commission,
        gross_pct: gross,
        net_pct: gross - 2 * commission,
        execution_assumption:
          'Candle-close paper prices; no slippage, ' +
          'borrow fees or actual fills'
      };
    }

    busy = true;
    refresh();

    try {
      // Save the decision BEFORE revealing future candles.
      records.push(record);

      if (!persist()) {
        records.pop();
        return;
      }

      const revealCount = Math.min(
        5,
        candles.length - before.count
      );

      visible = before.count + revealCount;
      render();

      const after = position();

      if (!after || after.count <= before.count) {
        throw Error('Replay did not advance');
      }

      const pct =
        100 * (after.close - before.close) / before.close;

      record.outcome = {
        revealed_to_unix: after.time,
        revealed_to_utc: after.utc,
        revealed_candles: after.count - before.count,
        start_close: before.close,
        end_close: after.close,
        price_change_pct: pct,
        direction:
          pct > 0 ? 'Price rose' :
          pct < 0 ? 'Price fell' :
          'Price unchanged',
        recorded_at_utc: new Date().toISOString()
      };

      if (!persist()) {
        message(
          'Outcome save failed. Export research now.'
        );
        return;
      }

      history();
      $('v4Note').value = '';
      pending = null;
      selectReason('WAIT');

      message(
        decision +
        ' saved. Next five candles revealed.'
      );

    } catch (e) {
      message(
        'Replay error: ' + e.message +
        '. Export before refreshing.'
      );
    } finally {
      busy = false;
      refresh();
    }
  }

  function confirmDecision(action) {
    if (pending === action) {
      pending = null;
      recordAndReveal(action);
      return;
    }

    pending = action;
    selectReason(action);

    message(
      action +
      ' selected. Review the reason, then click ' +
      action + ' AGAIN to save and reveal.'
    );
  }

  $('v4Wait').onclick = () => {
    pending = null;
    selectReason('WAIT');
    recordAndReveal('WAIT');
  };

  $('v4Enter').onclick = () => {
    confirmDecision('ENTER_SHORT');
  };

  $('v4Exit').onclick = () => {
    confirmDecision('EXIT_SHORT');
  };

  $('v4Reject').onclick = () => {
    confirmDecision('REJECT_SHORT_CANDIDATE');
  };

  $('v4Reason').onchange = () => {
    if (pending) {
      message(
        'Reason updated. Click ' +
        pending + ' again to confirm.'
      );
    }
  };

  $('v4Export').onclick = () => {
    if (!records.length) return;

    const payload = {
      schema: VERSION,
      research_only: true,
      ai_inference_performed: false,
      dataset_id: datasetId,
      exported_at_utc: new Date().toISOString(),
      records
    };

    const blob = new Blob(
      [JSON.stringify(payload, null, 2)],
      { type: 'application/json' }
    );

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');

    a.href = url;
    a.download =
      'aimn_' + (selectedSymbol || 'symbol') +
      '_enter_short_visual_v4.json';

    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(() => URL.revokeObjectURL(url), 5000);

    message('Exported ' + records.length + ' judgments.');
  };

  $('v4Reset').onclick = () => {
    if (!confirm(
      'Start a NEW session? Export your research first.'
    )) return;

    if (records.length && !confirm(
      'Confirm again: clear ' +
      records.length + ' saved judgments?'
    )) return;

    if (storage && sessionKey) {
      storage.removeItem(sessionKey);
    }

    records = [];
    history();

    // Never rewind revealed candles.
    busy = true;
    refresh();

    message(
      'Session cleared. Chart was NOT rewound.'
    );
  };

  next.addEventListener('click', e => {
    e.preventDefault();
    e.stopImmediatePropagation();
    message('Use a research decision button.');
  }, true);

  if ($('direction')) {
    $('direction').value = 'SHORT';
    $('direction').disabled = true;
  }

  const observer = new MutationObserver(() => {
    if (!next.disabled) next.disabled = true;
  });

  observer.observe(next, {
    attributes: true,
    attributeFilter: ['disabled']
  });

  const positionEl = $('position');

  if (positionEl) {
    new MutationObserver(() => {
      restoreForDataset();
      refresh();
    }).observe(positionEl, {
      childList: true,
      characterData: true,
      subtree: true
    });
  }

  selectReason('WAIT');
  restoreForDataset();
  history();
  refresh();
})();
