(function () {
  'use strict';

  var panel = document.getElementById('cgm-viz-panel');
  if (!panel || panel.dataset.cgmVizReady === '1') { return; }
  panel.dataset.cgmVizReady = '1';

  /* ------------------------------------------------------------------ setup
     The panel is fed by the local preprocessing API. Nothing about a participant's
     glucose values is compiled into this file: every trace on screen came from a
     request, and the run it came from is reported in Provenance. */

  var API = '/api';

  var SENSORS = [
    /* Dexcom first: this order is used by the checkboxes, the key strip and the
       readout. The wider navy trace is drawn underneath so the teal line reads against
       a navy edge where the two sensors agree. */
    { key: 'dexcom', label: 'Dexcom GL', color: '#12324c', toggle: 'cgm-viz-toggle-dexcom', width: 2.4, opacity: 1 },
    { key: 'libre', label: 'Libre GL', color: '#0e7c86', toggle: 'cgm-viz-toggle-libre', width: 1.5, opacity: 0.88 }
  ];
  var MEAL_COLOR = '#8d5710';
  /* Warm translucent wash marking stretches where the record holds no rows at all. It sits
     below the traces and is deliberately faint: it must read as absence, not as data. */
  var GAP_FILL = 'rgba(196,116,58,0.13)';
  /* Meal markers ride a hidden secondary axis, in a fixed lane labelled in the key
     strip and ruled with a hairline so they cannot be read as glucose values. */
  var MEAL_LANE_Y = 0.045;

  var FILTERS = [
    { key: 'all', label: 'All participants', range: '' },
    { key: 'normal', label: 'Normal', range: '&lt;5.7%' },
    { key: 'prediabetes', label: 'Prediabetes', range: '5.7–6.4%' },
    { key: 'diabetes', label: 'Diabetes', range: '&gt;6.4%' }
  ];

  var HOVERLABEL = {
    bgcolor: '#ffffff',
    bordercolor: '#d9e0e7',
    font: { color: '#17222c', size: 12 }
  };

  /* Adaptive density: the API is asked for roughly this many points across whatever
     the current zoom shows, so a 14-day view and a 6-hour view both stay legible and
     a zoomed view is never silently decimated. */
  var TARGET_POINTS_PER_WINDOW = 2400;
  var MIN_REQUEST_POINTS = 400;

  var el = {
    filter: document.getElementById('cgm-viz-filter'),
    list: document.getElementById('cgm-viz-subject-list'),
    reset: document.getElementById('cgm-viz-reset'),
    chart: document.getElementById('cgm-viz-chart'),
    current: document.getElementById('cgm-viz-current'),
    currentStatus: document.getElementById('cgm-viz-current-status'),
    currentCounts: document.getElementById('cgm-viz-current-counts'),
    status: document.getElementById('cgm-viz-status'),
    error: document.getElementById('cgm-viz-error'),
    provSource: document.getElementById('cgm-viz-prov-source'),
    provDecimation: document.getElementById('cgm-viz-prov-decimation'),
    provGaps: document.getElementById('cgm-viz-prov-gaps'),
    provFresh: document.getElementById('cgm-viz-prov-fresh'),
    provTime: document.getElementById('cgm-viz-prov-time'),
    provScope: document.getElementById('cgm-viz-prov-scope'),
    provCounts: document.getElementById('cgm-viz-prov-counts'),
    provRuntime: document.getElementById('cgm-viz-prov-runtime'),
    lede: document.getElementById('cgm-viz-lede')
  };

  var state = {
    meta: null,
    subjects: [],
    filter: 'all',
    subjectId: null,
    series: null,
    meals: [],
    visible: { dexcom: true, libre: true, meals: true, held: false },
    plotlyReady: false,
    plotted: false,
    booted: false,
    requestToken: 0,
    range: null
  };

  var integerFormat = new Intl.NumberFormat('en-US');
  var decimalFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

  function fmtInt(value) { return integerFormat.format(value); }
  function a1cLabel(value) { return value === null || value === undefined ? '—' : decimalFormat.format(value) + '%'; }
  function gramLabel(value) { return value === null || value === undefined ? '—' : decimalFormat.format(value) + ' g'; }
  function kcalLabel(value) { return value === null || value === undefined ? '—' : fmtInt(value) + ' kcal'; }

  function announce(message) { if (el.status) { el.status.textContent = message; } }
  function showError(message) {
    if (!el.error) { return; }
    el.error.textContent = message;
    el.error.hidden = false;
  }
  function clearError() {
    if (!el.error) { return; }
    el.error.textContent = '';
    el.error.hidden = true;
  }

  function pad(value) { return value < 10 ? '0' + value : String(value); }

  /* Time is always elapsed from the participant's first sample — never a calendar date,
     because upstream shifted every participant's dates by a private offset. */
  function elapsedLabel(minutes) {
    if (minutes === null || minutes === undefined) { return '—'; }
    var total = Math.round(minutes * 60);
    var day = Math.floor(total / 86400) + 1;
    var hour = Math.floor((total % 86400) / 3600);
    var minute = Math.floor((total % 3600) / 60);
    return 'Day ' + day + ' · ' + pad(hour) + ':' + pad(minute);
  }

  function api(path) {
    return fetch(API + path, { headers: { Accept: 'application/json' } }).then(function (response) {
      if (!response.ok) {
        return response.text().then(function (body) {
          var detail = body;
          try { detail = JSON.parse(body).detail || body; } catch (ignore) { /* keep the raw body */ }
          throw new Error(response.status + ' ' + (detail || response.statusText));
        });
      }
      return response.json();
    });
  }

  /* ---------------------------------------------------------------- controls */

  function buildFilters() {
    var subjects = state.subjects;
    FILTERS.forEach(function (filter) {
      var count = filter.key === 'all'
        ? subjects.length
        : subjects.filter(function (s) { return s.a1c_band === filter.key; }).length;

      var label = document.createElement('label');
      label.className = 'cgm-viz__row cgm-viz__row--filter';

      var input = document.createElement('input');
      input.type = 'radio';
      input.name = 'cgm-viz-status-filter';
      input.value = filter.key;
      input.id = 'cgm-viz-filter-' + filter.key;
      input.checked = filter.key === 'all';

      var text = document.createElement('span');
      text.innerHTML = '<span class="cgm-viz__dot" aria-hidden="true"></span>' + filter.label +
        (filter.range ? ' <span class="cgm-viz__range">' + filter.range + '</span>' : '');

      var countNode = document.createElement('span');
      countNode.className = 'cgm-viz__count';
      countNode.textContent = String(count);

      label.appendChild(input);
      label.appendChild(text);
      label.appendChild(countNode);
      el.filter.appendChild(label);

      input.addEventListener('change', function () {
        if (input.checked) { applyFilter(filter.key, true); }
      });
    });
  }

  function subjectById(id) {
    for (var i = 0; i < state.subjects.length; i++) {
      if (state.subjects[i].subject_id === id) { return state.subjects[i]; }
    }
    return null;
  }

  function bandLabel(band) {
    return band === 'normal' ? 'Normal'
      : band === 'prediabetes' ? 'Prediabetes'
      : band === 'diabetes' ? 'Diabetes'
      : 'Unclassified';
  }

  function buildSubjectList() {
    var subjects = state.subjects.slice().sort(function (a, b) {
      return a.subject_id < b.subject_id ? -1 : a.subject_id > b.subject_id ? 1 : 0;
    });

    subjects.forEach(function (subject) {
      var label = document.createElement('label');
      label.className = 'cgm-viz__row cgm-viz__row--subject';
      label.setAttribute('data-status', subject.a1c_band || 'unknown');
      label.setAttribute('data-subject', subject.subject_id);

      var input = document.createElement('input');
      input.type = 'radio';
      input.name = 'cgm-viz-subject';
      input.value = subject.subject_id;
      input.id = 'cgm-viz-subject-' + subject.subject_id;

      var idNode = document.createElement('span');
      idNode.className = 'cgm-viz__id';
      idNode.textContent = subject.label;

      var statusNode = document.createElement('span');
      statusNode.className = 'cgm-viz__status';
      statusNode.innerHTML = '<span class="cgm-viz__dot" aria-hidden="true"></span>' + bandLabel(subject.a1c_band);

      var a1cNode = document.createElement('span');
      a1cNode.className = 'cgm-viz__a1c';
      a1cNode.textContent = a1cLabel(subject.a1c_percent);

      label.appendChild(input);
      label.appendChild(idNode);
      label.appendChild(statusNode);
      label.appendChild(a1cNode);
      el.list.appendChild(label);

      input.addEventListener('change', function () {
        if (input.checked) { selectSubject(subject.subject_id); }
      });
    });
  }

  function addHeldToggle() {
    /* Freshness is the finding that shaped the pipeline: the CGMacros files carry each
       sensor's reading forward until it refreshes, so a plotted point may be a new
       measurement or a held copy. The chart hides held values by default and this
       control makes the distinction inspectable rather than invisible. */
    var container = document.getElementById('cgm-viz-toggle-held');
    if (container) { return; }
    var fieldset = document.querySelector('#cgm-viz-series-legend');
    if (!fieldset || !fieldset.parentElement) { return; }
    var rows = fieldset.parentElement.querySelector('.cgm-viz__rows');
    if (!rows) { return; }

    var label = document.createElement('label');
    label.className = 'cgm-viz__row cgm-viz__row--toggle';
    label.innerHTML =
      '<input type="checkbox" id="cgm-viz-toggle-held">' +
      '<span class="cgm-viz__swatch cgm-viz__swatch--held" aria-hidden="true"></span>' +
      '<span>Held readings <span class="cgm-viz__unit">(carried forward between sensor refreshes, not new samples)</span></span>';
    rows.appendChild(label);

    var input = label.querySelector('input');
    input.addEventListener('change', function () {
      state.visible.held = input.checked;
      refreshSeries('held values ' + (input.checked ? 'shown' : 'hidden'));
    });
  }

  function bindToggles() {
    SENSORS.forEach(function (sensor) {
      var input = document.getElementById(sensor.toggle);
      if (!input) { return; }
      input.addEventListener('change', function () {
        state.visible[sensor.key] = input.checked;
        render();
        announce(sensor.label + ' series ' + (input.checked ? 'shown' : 'hidden') + '. ' + summarySentence());
      });
    });

    var meals = document.getElementById('cgm-viz-toggle-meals');
    if (meals) {
      meals.addEventListener('change', function () {
        state.visible.meals = meals.checked;
        render();
        announce('Meal markers ' + (meals.checked ? 'shown' : 'hidden') + '. ' + summarySentence());
      });
    }

    if (el.reset) {
      el.reset.addEventListener('click', function () {
        if (!state.plotted || !window.Plotly) { return; }
        state.range = null;
        window.Plotly.relayout(el.chart, { 'xaxis.autorange': true, 'yaxis.autorange': true });
        refreshSeries('zoom reset');
      });
    }
  }

  function visibleRows() {
    return Array.prototype.filter.call(el.list.children, function (row) { return !row.hidden; });
  }

  function applyFilter(key, announceChange) {
    state.filter = key;
    Array.prototype.forEach.call(el.list.children, function (row) {
      row.hidden = key !== 'all' && row.getAttribute('data-status') !== key;
    });

    var rows = visibleRows();
    var filter = FILTERS.filter(function (f) { return f.key === key; })[0];
    var stillVisible = rows.some(function (row) {
      return row.getAttribute('data-subject') === state.subjectId;
    });

    if (!stillVisible && rows.length) {
      var firstId = rows[0].getAttribute('data-subject');
      var input = document.getElementById('cgm-viz-subject-' + firstId);
      if (input) { input.checked = true; }
      selectSubject(firstId);
    }

    if (announceChange) {
      announce('Filter: ' + filter.label + ' — ' + rows.length + ' participant' +
        (rows.length === 1 ? '' : 's') + ' listed. ' + summarySentence());
    }
  }

  /* ---------------------------------------------------------------- requests */

  function windowForRequest() {
    /* Ask for what is actually visible. Zoomed in, this is the whole point: the API
       serves a window rather than the browser holding the entire record. */
    if (!state.range || !isFinite(state.range[0]) || !isFinite(state.range[1])) {
      return { start: 0, end: null, maxPoints: TARGET_POINTS_PER_WINDOW };
    }
    var span = Math.max(1, state.range[1] - state.range[0]);
    /* ~1 point per 2.5 plotted minutes, so a 5-minute sensor keeps every real sample. */
    var desired = Math.ceil(span / 2.5);
    return {
      start: Math.max(0, state.range[0]),
      end: state.range[1],
      maxPoints: Math.max(MIN_REQUEST_POINTS, Math.min(desired, 20000))
    };
  }

  function refreshSeries(reason) {
    if (!state.subjectId) { return; }
    var subject = subjectById(state.subjectId);
    var window_ = windowForRequest();
    var token = ++state.requestToken;
    var query = '?start=' + encodeURIComponent(window_.start) +
      (window_.end === null ? '' : '&end=' + encodeURIComponent(window_.end)) +
      '&max_points=' + window_.maxPoints +
      '&include_held=' + (state.visible.held ? 'true' : 'false');

    announce('Loading ' + (subject ? subject.label : state.subjectId) + '…');

    Promise.all([
      api('/series/' + state.subjectId + query),
      api('/meals/' + state.subjectId)
    ]).then(function (results) {
      if (token !== state.requestToken) { return; }
      state.series = results[0];
      state.meals = results[1].meals || [];
      clearError();
      updateReadout();
      render();
      announce(summarySentence() + (reason ? ' (' + reason + ')' : ''));
    }).catch(function (error) {
      if (token !== state.requestToken) { return; }
      showError('Could not load participant ' + state.subjectId + ' from the local API: ' + error.message +
        '. Confirm the dashboard server is running.');
      announce('Could not load participant ' + state.subjectId + '.');
    });
  }

  function selectSubject(id) {
    if (id === state.subjectId && state.series) { return; }
    state.subjectId = id;
    state.series = null;
    state.meals = [];
    state.range = null;
    state.plotted = false;
    clearError();

    var input = document.getElementById('cgm-viz-subject-' + id);
    if (input) { input.checked = true; }
    scrollRowIntoView(id);
    updateReadoutLoading(id);

    if (window.Plotly) {
      window.Plotly.purge(el.chart);
    }
    refreshSeries();
  }

  function scrollRowIntoView(id) {
    var row = el.list.querySelector('[data-subject="' + id + '"]');
    if (!row || !el.list.clientHeight) { return; }
    var listBox = el.list.getBoundingClientRect();
    var rowBox = row.getBoundingClientRect();
    if (rowBox.top < listBox.top) { el.list.scrollTop -= listBox.top - rowBox.top; }
    else if (rowBox.bottom > listBox.bottom) { el.list.scrollTop += rowBox.bottom - listBox.bottom; }
  }

  /* ---------------------------------------------------------------- readouts */

  function updateReadoutLoading(id) {
    var subject = subjectById(id);
    if (!el.current) { return; }
    el.current.textContent = subject ? subject.label : id;
    el.currentStatus.textContent = subject
      ? bandLabel(subject.a1c_band) + ' · HbA1c ' + a1cLabel(subject.a1c_percent)
      : '—';
    el.currentCounts.textContent = 'loading from the local API…';
  }

  function updateReadout() {
    var series = state.series;
    if (!series || !el.current) { return; }
    var subject = subjectById(series.subject_id);
    var window_ = series.window;

    el.current.textContent = subject ? subject.label : series.subject_id;
    el.currentStatus.textContent = subject
      ? bandLabel(subject.a1c_band) + ' · HbA1c ' + a1cLabel(subject.a1c_percent)
      : '—';

    var parts = [
      'Window ' + elapsedLabel(window_.start) + ' → ' + elapsedLabel(window_.end),
      fmtInt(window_.rows_in_window) + ' rows in window',
      fmtInt(window_.points_returned) + ' points returned'
    ];
    SENSORS.forEach(function (sensor) {
      var data = series.streams[sensor.key];
      if (!data) { return; }
      parts.push(sensor.label + ' ' + fmtInt(data.fresh_count) + ' new / ' +
        fmtInt(data.observed_count) + ' observed');
    });
    parts.push(fmtInt(state.meals.length) + ' logged meals');
    var gaps = series.gap_report;
    if (gaps) {
      if (!gaps.count && !gaps.short_count) {
        parts.push('no missing minutes');
      } else {
        var gapText = fmtInt(gaps.count) + (gaps.count === 1 ? ' gap' : ' gaps') +
          ' ≥ ' + fmtInt(gaps.major_minutes) + ' min' +
          (gaps.count ? ' (longest ' + gapLabel(gaps.longest_minutes) + ')' : '');
        if (gaps.short_count) {
          gapText += ' + ' + fmtInt(gaps.short_count) + ' shorter absence' +
            (gaps.short_count === 1 ? '' : 's');
        }
        parts.push(gapText);
      }
    }
    el.currentCounts.textContent = parts.join(' · ');
  }

  function updateCounts() {
    var series = state.series;
    if (!el.provCounts || !series) { return; }
    var subject = subjectById(series.subject_id);
    var parts = [
      subject ? subject.label : series.subject_id,
      'window ' + fmtInt(series.window.rows_in_window) + ' rows, ' +
        fmtInt(series.window.points_returned) + ' points' +
        (series.window.decimated ? ' (decimated 1 in ' + series.window.stride + ')' : ' (every row)')
    ];
    SENSORS.forEach(function (sensor) {
      var data = series.streams[sensor.key];
      if (!data) { return; }
      parts.push(sensor.label + ' ' + fmtInt(data.fresh_count) + ' new of ' +
        fmtInt(data.observed_count) + ' observed');
    });
    parts.push(fmtInt(state.meals.length) + ' logged meals');
    el.provCounts.textContent = parts.join(' · ') + '.';
  }

  function summarySentence() {
    var series = state.series;
    var subject = state.subjectId ? subjectById(state.subjectId) : null;
    if (!series) {
      return subject ? subject.label + ' selected.' : 'No participant selected.';
    }
    var dexcom = series.streams.dexcom || {};
    var libre = series.streams.libre || {};
    return (subject ? subject.label : series.subject_id) + ' · ' + bandLabel(subject && subject.a1c_band) +
      ' · HbA1c ' + a1cLabel(subject && subject.a1c_percent) +
      '. Dexcom GL ' + fmtInt(dexcom.fresh_count || 0) + ' new readings, Libre GL ' +
      fmtInt(libre.fresh_count || 0) + ' new readings, ' + fmtInt(state.meals.length) +
      ' meals. Missing samples stay missing; the shifted timeline is shown as elapsed time.';
  }

  function applyProvenance() {
    var meta = state.meta;
    if (!meta) { return; }
    if (el.provSource) {
      el.provSource.textContent =
        'Served live from preprocessing run ' + meta.run_id + ' by the local API. ' +
        fmtInt(meta.counts.cgm_rows) + ' canonical rows across ' +
        meta.dataset.participant_count + ' participants, from a ' + meta.dataset.kind +
        ' at ' + meta.dataset.root + '.';
    }
    if (el.provDecimation) {
      el.provDecimation.textContent =
        'Stored at the file\'s own cadence — one row per recorded minute, never resampled onto ' +
        'a grid. The API decimates per request to fit the current zoom (' + fmtInt(TARGET_POINTS_PER_WINDOW) +
        ' points across the view), so a zoomed-in view keeps every real sample.';
    }
    if (el.provGaps) {
      el.provGaps.textContent =
        'No value is interpolated, filled, or forward-filled. A missing sample stays null. A run of at ' +
        'least ' + fmtInt(meta.thresholds.min_gap_seconds / 60) + ' min with no rows at all breaks the ' +
        'trace and is shaded; shorter absences are counted in the readout but not drawn, so the curve is ' +
        'never joined across an outage. The same run length starts a new segment.';
    }
    if (el.provFresh) {
      el.provFresh.textContent =
        'The CGMacros files record one row per minute, though some minutes are absent, and each ' +
        'sensor\'s reading is carried forward until it refreshes, so a listed value may be a new ' +
        'measurement or a held copy of the previous one. Traces draw new readings only; ' +
        '"Held readings" reveals the carried values. This is a reconstruction: a genuine ' +
        're-reading of an identical value is marked held.';
    }
    if (el.provTime) {
      el.provTime.textContent =
        'Upstream shifted every participant\'s dates by a private offset of 365–720 days. ' +
        'The axis and hover text show elapsed time from each participant\'s first sample and ' +
        'never a calendar date.';
    }
    if (el.provScope) {
      el.provScope.textContent =
        'Raw CGM and logged meals only: no detection bands, method overlays, or PPGR ' +
        'annotations. Eligibility, flags, gaps, and segments come from the preprocessing run; ' +
        'screening flags never remove a value from this view.';
    }
    if (el.provRuntime) {
      var conventions = meta.conventions || {};
      el.provRuntime.textContent =
        'Plotly served locally, no CDN. ' + (conventions.sensor_handling || '') +
        (conventions.eligibility ? ' ' + conventions.eligibility : '');
    }
    if (el.lede) {
      el.lede.textContent =
        'Raw CGM traces with logged meals · served from the local preprocessing run · ' +
        'one participant at a time';
    }
  }

  /* ------------------------------------------------------------------ render */

  function ensurePlotly(callback, failure) {
    if (window.Plotly) { state.plotlyReady = true; callback(); return; }
    var script = document.createElement('script');
    script.src = '/static/plotly.min.js';
    script.async = false;
    script.onload = function () {
      state.plotlyReady = !!window.Plotly;
      if (state.plotlyReady) { callback(); } else { failure('Plotly did not register.'); }
    };
    script.onerror = function () {
      var message = 'Could not load /static/plotly.min.js from the dashboard server.';
      showError(message);
      failure(message);
    };
    document.head.appendChild(script);
  }

  function traceFor(sensor) {
    var series = state.series;
    var data = series.streams[sensor.key];
    if (!data) { return null; }

    var x = [];
    var y = [];
    var customdata = [];
    var fresh = data.is_fresh;
    var values = data.glucose_mgdl;
    var elapsed = series.elapsed_minutes;
    /* Break at the same threshold the spans are shaded at, so the drawn breaks and the
       shaded outages always agree. */
    var threshold = (series.gap_report && series.gap_report.major_minutes) || 15;

    for (var i = 0; i < values.length; i++) {
      var value = values[i];
      var isNew = fresh[i];
      if (i > 0 && elapsed[i] - elapsed[i - 1] >= threshold) {
        /* The file holds no row whatsoever across this interval. Insert an explicit break
           so the trace cannot imply continuity over time that was never recorded. */
        x.push(elapsed[i]);
        y.push(null);
        customdata.push([
          'no samples for ' + gapLabel(elapsed[i] - elapsed[i - 1]),
          elapsedLabel(elapsed[i - 1]) + ' → ' + elapsedLabel(elapsed[i])
        ]);
      }
      if (value === null || value === undefined) {
        /* A real gap: an explicit null breaks the line. Nothing is filled. */
        x.push(elapsed[i]);
        y.push(null);
        customdata.push(['no sample (gap)', elapsedLabel(elapsed[i])]);
        continue;
      }
      if (!isNew && !state.visible.held && state.visible.held !== undefined) {
        /* A held reading is not a new measurement. Break the line here as well, so the
           trace shows only sensor refreshes rather than a staircase of carried values. */
        x.push(elapsed[i]);
        y.push(null);
        customdata.push(['held reading (not drawn)', elapsedLabel(elapsed[i])]);
        continue;
      }
      x.push(elapsed[i]);
      y.push(value);
      customdata.push([
        isNew ? 'new reading' : 'held reading (carried forward)',
        elapsedLabel(elapsed[i]) + ' · ' + value.toFixed(1) + ' mg/dL'
      ]);
    }

    return {
      type: 'scatter',
      mode: 'lines',
      name: sensor.label,
      x: x,
      y: y,
      customdata: customdata,
      connectgaps: false,
      line: { color: sensor.color, width: sensor.width, simplify: false, shape: 'linear' },
      opacity: sensor.opacity,
      hovertemplate: sensor.label + ' · %{customdata[0]}<br>Shifted timeline · %{customdata[1]}<extra></extra>',
      hoverlabel: HOVERLABEL,
      visible: state.visible[sensor.key] ? true : false
    };
  }

  function mealTrace() {
    if (!state.meals.length) { return null; }
    var x = [];
    var y = [];
    var customdata = [];

    state.meals.forEach(function (meal) {
      var at = meal.elapsed_minutes;
      x.push(at);
      y.push(MEAL_LANE_Y);
      var detail = [meal.meal_type_raw || 'Meal'];
      detail.push(gramLabel(meal.carbs_g) + ' carbs');
      detail.push(kcalLabel(meal.calories));
      customdata.push([detail.join(' · '), elapsedLabel(at)]);
    });

    return {
      type: 'scatter',
      mode: 'markers',
      name: 'Meal markers',
      x: x,
      y: y,
      yaxis: 'y2',
      customdata: customdata,
      cliponaxis: false,
      marker: {
        symbol: 'triangle-up',
        size: 11,
        color: MEAL_COLOR,
        line: { color: '#ffffff', width: 0.8 }
      },
      hovertemplate: '<b>%{customdata[0]}</b><br>Shifted timeline · %{customdata[1]}<extra></extra>',
      hoverlabel: HOVERLABEL,
      visible: state.visible.meals ? true : false
    };
  }

  function gapLabel(minutes) {
    /* Missing time is stated in the unit a reader can act on: minutes, hours, or days. */
    if (minutes === null || minutes === undefined || !isFinite(minutes)) { return '—'; }
    if (minutes < 90) { return fmtInt(Math.round(minutes)) + ' min'; }
    if (minutes < 60 * 48) { return (minutes / 60).toFixed(1) + ' h'; }
    return (minutes / 1440).toFixed(1) + ' days';
  }

  function gapShapes() {
    /* Shade stretches where the record holds no rows at all, longest first so the most
       consequential outage is the one that reads. Overlapping per-stream spans are merged
       so a hole present in both streams is shaded once, not twice. */
    var series = state.series;
    if (!series || !series.gap_breaks) { return []; }
    var threshold = (series.gap_report && series.gap_report.major_minutes) || 15;
    var spans = [];
    SENSORS.forEach(function (sensor) {
      (series.gap_breaks[sensor.key] || []).forEach(function (span) {
        if (span[1] - span[0] >= threshold) { spans.push([span[0], span[1]]); }
      });
    });
    if (!spans.length) { return []; }
    spans.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [spans[0].slice()];
    for (var i = 1; i < spans.length; i++) {
      var last = merged[merged.length - 1];
      if (spans[i][0] <= last[1]) {
        last[1] = Math.max(last[1], spans[i][1]);
      } else {
        merged.push(spans[i].slice());
      }
    }
    return merged.map(function (span) {
      return {
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: span[0],
        x1: span[1],
        y0: 0,
        y1: 1,
        fillcolor: GAP_FILL,
        line: { width: 0 },
        layer: 'below'
      };
    });
  }

  function glucoseRange(traces) {
    var min = Infinity;
    var max = -Infinity;
    traces.forEach(function (trace) {
      if (trace.yaxis === 'y2') { return; }
      trace.y.forEach(function (value) {
        if (value === null || value === undefined) { return; }
        if (value < min) { min = value; }
        if (value > max) { max = value; }
      });
    });
    if (!isFinite(min) || !isFinite(max)) { return null; }
    return [Math.floor(min - 10), Math.ceil(max + 10)];
  }

  function xTicks(startMinutes, endMinutes) {
    var span = Math.max(1, endMinutes - startMinutes);
    var days = Math.max(1, Math.ceil(span / 1440));
    var stride = Math.max(1, Math.ceil(days / 12));
    var values = [];
    var labels = [];
    for (var day = 0; day < days; day += stride) {
      var at = startMinutes + day * 1440;
      if (at > endMinutes) { break; }
      values.push(at);
      labels.push('Day ' + (Math.floor(at / 1440) + 1) + (strutFor(day, startMinutes)));
    }
    return { values: values, labels: labels };
  }

  function strutFor(day, startMinutes) {
    /* When the window starts mid-day the first tick is still day 1; keep the label tidy. */
    return day === 0 && startMinutes >= 1440 ? '' : '';
  }

  function segmentShapes() {
    /* Segments are contiguous eligible runs from the preprocessing run. Shading them
       would compete with the traces, so they are reported in the readout instead and
       only drawn when they are few enough to read as structure rather than noise. */
    var series = state.series;
    if (!series || !series.segments || series.segments.length === 0 || series.segments.length > 12) {
      return [];
    }
    return series.segments.map(function (segment) {
      return {
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: segment.start_elapsed_minutes,
        x1: segment.end_elapsed_minutes,
        y0: 0,
        y1: 1,
        fillcolor: 'rgba(14,124,134,0.05)',
        line: { width: 0 },
        layer: 'below'
      };
    });
  }

  function render() {
    if (!state.series) { return; }
    ensurePlotly(draw, function () {});
  }

  /* The Visualization tab may start hidden, where the chart container has no width yet.
     Wait for a real layout width before plotting, with a bounded fallback. */
  function whenLaidOut(callback, attempt) {
    var tries = attempt || 0;
    if (!el.chart || el.chart.clientWidth >= 40 || tries > 120) { callback(); return; }
    window.requestAnimationFrame(function () { whenLaidOut(callback, tries + 1); });
  }

  function captureRange() {
    /* Record the user's zoom so a change can re-anchor and so a re-request can ask for
       exactly the visible window. The proxy keeps the last explicit property write. */
    if (!window.Plotly || !el.chart || !el.chart.layout) { return; }
    var axis = el.chart.layout.xaxis || {};
    var range = null;
    if (Array.isArray(axis.range)) { range = axis.range.slice(0, 2); }
    else if (Array.isArray(axis._input) === false && axis.autorange !== false) { range = null; }
    state.range = range && isFinite(range[0]) && isFinite(range[1]) ? range : null;
  }

  function draw() {
    var series = state.series;
    if (!series || !window.Plotly) { return; }

    var traces = [];
    SENSORS.forEach(function (sensor) {
      var trace = traceFor(sensor);
      if (trace) { traces.push(trace); }
    });
    var meals = mealTrace();
    if (meals) { traces.push(meals); }

    var subject = subjectById(series.subject_id);
    var windowStart = series.window.start === null ? 0 : series.window.start;
    var windowEnd = series.window.end === null ? windowStart + 1440 : series.window.end;
    var range = state.range ? null : glucoseRange(traces);
    var ticks = xTicks(windowStart, windowEnd);
    var shapes = meals && state.visible.meals ? [{
      type: 'line',
      xref: 'paper',
      x0: 0,
      x1: 1,
      yref: 'y2',
      y0: MEAL_LANE_Y,
      y1: MEAL_LANE_Y,
      line: { color: '#dfe5ea', width: 1 },
      layer: 'below'
    }] : [];
    shapes = shapes.concat(segmentShapes());
    shapes = shapes.concat(gapShapes());

    var layout = {
      margin: { l: 58, r: 14, t: 6, b: 54 },
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      showlegend: false,
      shapes: shapes,
      hovermode: 'closest',
      hoverdistance: 24,
      dragmode: 'zoom',
      transition: { duration: 0, easing: 'linear' },
      uirevision: 'cgm-viz-' + series.subject_id,
      font: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        size: 12,
        color: '#17222c'
      },
      xaxis: {
        title: { text: 'Elapsed time from first sample (shifted timeline)', font: { size: 12, color: '#5a6a79' } },
        tickmode: 'array',
        tickvals: ticks.values,
        ticktext: ticks.labels,
        tickfont: { size: 11, color: '#5a6a79' },
        showgrid: true,
        gridcolor: '#eceff3',
        zeroline: false,
        ticks: 'outside',
        ticklen: 4,
        tickcolor: '#d9e0e7',
        linecolor: '#b7c3cf',
        automargin: true,
        range: state.range || [windowStart, windowEnd]
      },
      yaxis: {
        title: { text: 'Glucose (mg/dL)', font: { size: 12, color: '#5a6a79' } },
        tickfont: { size: 11, color: '#5a6a79' },
        showgrid: true,
        gridcolor: '#eceff3',
        zeroline: false,
        rangemode: 'normal',
        automargin: true
      },
      yaxis2: {
        overlaying: 'y',
        side: 'right',
        range: [0, 1],
        fixedrange: true,
        showgrid: false,
        zeroline: false,
        visible: false
      },
      modebar: {
        bgcolor: 'rgba(255,255,255,0)',
        color: '#5a6a79',
        activecolor: '#0e7c86',
        orientation: 'h'
      }
    };
    if (range) { layout.yaxis.range = range; layout.yaxis.autorange = false; }
    else { layout.yaxis.autorange = true; }

    var config = {
      responsive: true,
      displaylogo: false,
      scrollZoom: true,
      doubleClick: 'reset',
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines'],
      toImageButtonOptions: {
        format: 'png',
        filename: 'cgmacros-' + series.subject_id + '-glucose-traces',
        width: 1400,
        height: 800,
        scale: 2
      }
    };

    whenLaidOut(function () {
      if (state.series !== series) { return; }
      if (state.plotted) {
        window.Plotly.react(el.chart, traces, layout, config);
      } else {
        window.Plotly.newPlot(el.chart, traces, layout, config).then(bindZoomEvents);
        state.plotted = true;
      }
      window.Plotly.Plots.resize(el.chart);
    });

    if (el.chart && el.chart.setAttribute) {
      el.chart.setAttribute(
        'aria-label',
        'Glucose traces for ' + (subject ? subject.label : series.subject_id) + ', ' +
        bandLabel(subject && subject.a1c_band) + ', HbA1c ' + a1cLabel(subject && subject.a1c_percent) +
        ': ' + fmtInt(series.window.points_returned) + ' points across the visible window, ' +
        fmtInt(state.meals.length) + ' logged meals drawn as markers in a fixed lane ' +
        '(not glucose values), on an elapsed shifted timeline.'
      );
    }
    updateCounts();
  }

  var refreshTimer = 0;

  function bindZoomEvents() {
    if (!el.chart || !el.chart.on) { return; }
    el.chart.on('plotly_relayout', function (event) {
      var touched = false;
      Object.keys(event || {}).forEach(function (key) {
        if (key.indexOf('xaxis') === 0 || key === 'autosize' || key === 'width') { touched = true; }
      });
      var autoranged = event && (event['xaxis.autorange'] === true || event['xaxis.range[0]'] === undefined && event['xaxis.autorange']);
      if (event && event['xaxis.autorange'] === true) { state.range = null; }
      else if (event && event['xaxis.range'] && event['xaxis.range'].length === 2) {
        state.range = [event['xaxis.range'][0], event['xaxis.range'][1]];
      } else if (event && event['xaxis.range[0]'] !== undefined) {
        state.range = [event['xaxis.range[0]'], event['xaxis.range[1]']];
      }

      if (!autoranged && !touched) { return; }
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(function () {
        refreshSeries('view updated to the visible window');
      }, 220);
    });
  }

  /* -------------------------------------------------------------------- boot */

  function start() {
    applyProvenance();
    addHeldToggle();
    bindToggles();

    if (el.chart && window.ResizeObserver) {
      var observer = new ResizeObserver(function () {
        if (state.plotted && window.Plotly) { window.Plotly.Plots.resize(el.chart); }
      });
      observer.observe(el.chart);
    }
  }

  function loadSubjects() {
    api('/participants').then(function (payload) {
      state.subjects = payload.participants || [];
      if (!state.subjects.length) {
        showError('The preprocessing run contains no participants.');
        return;
      }
      buildFilters();
      buildSubjectList();

      var rows = visibleRows();
      if (rows.length) {
        var firstId = rows[0].getAttribute('data-subject');
        var input = document.getElementById('cgm-viz-subject-' + firstId);
        if (input) { input.checked = true; }
        selectSubject(firstId);
      }
    }).catch(function (error) {
      showError('Could not reach the local API: ' + error.message +
        '. Start it with `cgm serve` from the project directory.');
      announce('The dashboard could not reach the local API.');
    });
  }

  function whenVisible(callback) {
    if (!panel.hidden) { callback(); return; }
    var observer = new MutationObserver(function () {
      if (!panel.hidden) {
        observer.disconnect();
        callback();
      }
    });
    observer.observe(panel, { attributes: true, attributeFilter: ['hidden'] });
  }

  function boot() {
    clearError();
    whenVisible(function () {
      if (state.booted) { return; }
      state.booted = true;
      api('/meta').then(function (meta) {
        state.meta = meta;
        start();
        loadSubjects();
      }).catch(function (error) {
        showError('Could not reach the local API at ' + API + ': ' + error.message +
          '. Start the dashboard with `cgm serve` and reload this page.');
        announce('The dashboard could not reach the local API.');
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
