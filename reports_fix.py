lines = open('index.html', encoding='utf-8').readlines()

# Find start and end of entire reports block
start = next((i for i,l in enumerate(lines) if '/* reports view */' in l.lower() or 'REPORTS VIEW' in l), None)
end   = next((i for i,l in enumerate(lines) if '/* therapy view */' in l.lower() or 'THERAPY VIEW' in l), None)
print(f'Reports block: {start} to {end}')

reports_js = '''/* ── REPORTS VIEW ────────────────────────────────────── */
let currentReport = null;
let reportDate = new Date();
let reportWeekStart = (function(){ var d=new Date(); d.setDate(d.getDate()-d.getDay()); return d; })();

function renderReports() {
  var el = document.getElementById('reports-content');
  if (!el) return;
  if (currentReport) { renderReport(currentReport, el); return; }
  var html = '<h2 style="font-size:17px;font-weight:700;margin-bottom:14px">Reports</h2>';
  html += makeReportCard('daily', 'Daily Schedule', 'All scheduled items for any day with completion status');
  html += makeReportCard('mar', 'Medication Administration Record', 'Weekly MAR showing each med given or missed by day');
  html += makeReportCard('weekly', 'Weekly Summary', 'Overview of care activities for the week');
  html += makeReportCard('handoff', 'Caregiver Handoff', 'Shift summary for incoming caregiver');
  el.innerHTML = html;
}
function makeReportCard(type, title, desc) {
  return '<div class="report-card" onclick="openReport(\\'' + type + '\\')">'
    + '<div style="flex:1"><div class="report-title">' + title + '</div>'
    + '<div class="report-desc">' + desc + '</div></div>'
    + '<div style="font-size:18px;color:var(--muted)">&#8250;</div></div>';
}
window.openReport  = function(type) { currentReport=type; reportDate=new Date(); renderReports(); };
window.closeReport = function()     { currentReport=null; renderReports(); };
function renderReport(type, el) {
  if (type==='daily')   renderDailySchedule(el);
  if (type==='mar')     renderMAR(el);
  if (type==='weekly')  renderWeeklySummary(el);
  if (type==='handoff') renderHandoff(el);
}

function reportHeader(title, subtitle) {
  return '<div class="report-header"><div><h2>' + title + '</h2>'
    + '<div class="report-header-sub">Becky Nelson &middot; ' + subtitle + '</div></div>'
    + '<button class="print-btn" onclick="window.print()">Print</button></div>';
}
function backBtn() {
  return '<button class="back-to-reports" onclick="closeReport()">&#8249; Reports</button>';
}

function renderDailySchedule(el) {
  var items = getDayItems(reportDate);
  var dateStr = fmtDate(reportDate);
  var isToday = dateStr === fmtDate(new Date());
  items.sort(function(a,b){ return a.scheduledTs - b.scheduledTs; });

  var rows = '';
  items.forEach(function(item) {
    var cfg = CATS[item.cat] || {icon:'*', label:item.cat, color:'#888'};
    var done = !!item.logEntry;
    var doneLabel = done
      ? ('Done by ' + item.logEntry.caregiver + ' at ' + fmt12(item.logEntry.givenTime||item.logEntry.timeStr))
      : (isToday && item.status==='late' ? 'Overdue' : 'Pending');
    var doneColor = done ? 'var(--ok)' : (isToday && item.status==='late' ? 'var(--warn)' : 'var(--muted)');
    var medNames = (item.medList && item.medList.length)
      ? item.medList.map(function(m){ return m.name; }).join(' | ') : '';

    rows += '<div style="background:#fff;border-radius:8px;padding:10px 12px;margin-bottom:8px;box-shadow:0 1px 4px rgba(0,0,0,.06)">';
    rows += '<div style="display:flex;align-items:baseline;gap:10px">';
    rows += '<div style="font-family:monospace;font-size:13px;font-weight:700;color:var(--teal);flex-shrink:0;min-width:72px">' + fmt12(item.time) + '</div>';
    rows += '<div style="flex:1"><span style="font-size:14px;font-weight:700">' + item.name + '</span>';
    rows += '<span style="font-size:10px;color:' + cfg.color + ';font-weight:700;margin-left:6px">' + cfg.icon + ' ' + cfg.label + '</span></div></div>';
    rows += '<div style="padding-left:82px;margin-top:4px">';
    rows += '<div style="font-size:12px;color:' + doneColor + ';font-weight:600">' + doneLabel + '</div>';
    if (item.dose) rows += '<div style="font-size:11px;color:var(--muted);margin-top:1px">' + item.dose + '</div>';
    if (medNames) rows += '<div style="font-size:11px;color:var(--muted);margin-top:2px">' + medNames + '</div>';
    if (item.logEntry && item.logEntry.notes) rows += '<div style="font-size:11px;color:#4a6070;font-style:italic;margin-top:2px">Note: ' + item.logEntry.notes + '</div>';
    rows += '</div></div>';
  });

  var dateNav = '<div class="report-date-nav">'
    + '<button onclick="reportDate=new Date(reportDate.getTime()-86400000);renderReports()">&#8249;</button>'
    + '<input type="date" value="' + dateStr + '" onchange="reportDate=new Date(this.value+\'T12:00:00\');renderReports()">'
    + '<button onclick="reportDate=new Date(reportDate.getTime()+86400000);renderReports()">&#8250;</button>'
    + '</div>';

  var dateLabel = reportDate.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
  var completed = items.filter(function(i){ return i.logEntry; }).length;

  el.innerHTML = backBtn()
    + '<div class="report-view">'
    + reportHeader('Daily Schedule', dateLabel)
    + '<div class="report-body">' + dateNav
    + (items.length === 0 ? '<div style="text-align:center;padding:32px;color:var(--muted)">No items scheduled.</div>' : rows)
    + '<div style="margin-top:16px;font-size:11px;color:var(--muted);text-align:center">' + completed + ' of ' + items.length + ' items completed</div>'
    + '</div></div>';
}

function renderMAR(el) {
  var weekStart = new Date(reportWeekStart);
  var days = [];
  for (var i=0; i<7; i++) { var d=new Date(weekStart); d.setDate(d.getDate()+i); days.push(d); }
  var dayLabels = days.map(function(d){ return d.toLocaleDateString('en-US',{weekday:'short',month:'numeric',day:'numeric'}); });
  var medItems = schedule.filter(function(s){ return s.cat==='med'; });
  medItems.sort(function(a,b){ return ((a.times||[''])[0]).localeCompare((b.times||[''])[0]); });

  var tableRows = '';
  medItems.forEach(function(s) {
    var cells = '';
    days.forEach(function(day) {
      var dow = day.getDay();
      var active = false;
      if (s.days==='daily') active=true;
      else if (s.days==='weekday') active=dow>=1&&dow<=5;
      else if (s.days==='weekend') active=dow===0||dow===6;
      else if (s.days==='once') active=s.onceDate===fmtDate(day);
      else if (Array.isArray(s.customDays)) active=s.customDays.includes(dow);
      if (!active) { cells+='<td style="background:#f8f8f8;text-align:center;color:#ccc">-</td>'; return; }
      var logged = (s.times||[]).map(function(t){ return getLogEntry(s.id,t,day); }).filter(Boolean);
      if (logged.length > 0) {
        var cg = [...new Set(logged.map(function(e){ return e.caregiver; }))].join(',');
        cells += '<td style="text-align:center"><span style="color:var(--ok);font-weight:700">&#10003;</span><div style="font-size:9px;color:var(--muted)">' + cg + '</div></td>';
      } else {
        cells += day > new Date()
          ? '<td style="text-align:center;color:#ccc">&#183;</td>'
          : '<td style="text-align:center;color:var(--warn);font-weight:700">&#10007;</td>';
      }
    });
    var times = (s.times||[]).map(fmt12).join(', ');
    tableRows += '<tr><td><div style="font-weight:600">' + s.name + '</div><div style="font-size:10px;color:var(--muted)">' + times + '</div></td>' + cells + '</tr>';
  });

  var weekEnd = days[6];
  var weekNav = '<div class="report-week-nav">'
    + '<button onclick="reportWeekStart=new Date(reportWeekStart.getTime()-7*86400000);renderReports()">&#8249; Prev</button>'
    + '<div style="flex:1;text-align:center;font-size:13px;font-weight:600">'
    + weekStart.toLocaleDateString('en-US',{month:'short',day:'numeric'}) + ' - '
    + weekEnd.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) + '</div>'
    + '<button onclick="reportWeekStart=new Date(reportWeekStart.getTime()+7*86400000);renderReports()">Next &#8250;</button></div>';

  var thCells = dayLabels.map(function(l){ return '<th>' + l + '</th>'; }).join('');
  var tableHtml = medItems.length === 0
    ? '<div style="text-align:center;padding:32px;color:var(--muted)">No medications scheduled.</div>'
    : '<div style="overflow-x:auto"><table class="mar-grid"><thead><tr><th>Medication</th>' + thCells + '</tr></thead><tbody>' + tableRows + '</tbody></table></div>'
      + '<div style="margin-top:12px;font-size:11px;color:var(--muted)">&#10003; Given &middot; &#10007; Missed &middot; &middot; Future &middot; - Not scheduled</div>';

  var subtitle = 'Week of ' + weekStart.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
  el.innerHTML = backBtn() + '<div class="report-view">' + reportHeader('Medication Administration Record', subtitle)
    + '<div class="report-body">' + weekNav + tableHtml + '</div></div>';
}

function renderWeeklySummary(el) {
  var weekStart = new Date(reportWeekStart);
  var days = [];
  for (var i=0; i<7; i++) { var d=new Date(weekStart); d.setDate(d.getDate()+i); days.push(d); }
  var weekEnd = days[6];
  var weekLogs = logEntries.filter(function(e){ var d=e.dateStr||''; return d>=fmtDate(weekStart)&&d<=fmtDate(weekEnd); });

  var catSummary = '';
  Object.entries(CATS).forEach(function(entry) {
    var cat=entry[0], cfg=entry[1];
    var catLogs = weekLogs.filter(function(e){ return e.cat===cat&&!e.medGroup; });
    if (!catLogs.length) return;
    catSummary += '<div class="report-row"><div class="report-time" style="color:' + cfg.color + '">' + cfg.icon + '</div>'
      + '<div style="flex:1;font-weight:600">' + cfg.label + '</div>'
      + '<div style="font-size:13px;font-weight:700">' + catLogs.length + ' records</div></div>';
  });

  var dayRows = '';
  days.forEach(function(day) {
    var dayStr = fmtDate(day);
    var dayLogs = weekLogs.filter(function(e){ return (e.dateStr||'')===dayStr; });
    var dayItems = getDayItems(day);
    var completed = dayItems.filter(function(i){ return i.logEntry; }).length;
    var isFuture = day > new Date();
    var caregivers = [...new Set(dayLogs.map(function(e){ return e.caregiver; }).filter(Boolean))].join(', ');
    dayRows += '<div class="report-row">'
      + '<div class="report-time">' + day.toLocaleDateString('en-US',{weekday:'short',month:'numeric',day:'numeric'}) + '</div>'
      + '<div style="flex:1">' + (isFuture ? '<span style="color:var(--muted)">Future</span>'
        : '<span style="font-weight:600">' + completed + '/' + dayItems.length + ' scheduled</span>'
        + '<span style="font-size:11px;color:var(--muted)"> &middot; ' + dayLogs.length + ' records</span>') + '</div>'
      + (!isFuture ? '<div style="font-size:11px;color:var(--muted)">' + caregivers + '</div>' : '')
      + '</div>';
  });

  var weekNav = '<div class="report-week-nav">'
    + '<button onclick="reportWeekStart=new Date(reportWeekStart.getTime()-7*86400000);renderReports()">&#8249; Prev</button>'
    + '<div style="flex:1;text-align:center;font-size:13px;font-weight:600">'
    + weekStart.toLocaleDateString('en-US',{month:'short',day:'numeric'}) + ' - '
    + weekEnd.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) + '</div>'
    + '<button onclick="reportWeekStart=new Date(reportWeekStart.getTime()+7*86400000);renderReports()">Next &#8250;</button></div>';

  var subtitle = weekStart.toLocaleDateString('en-US',{month:'long',day:'numeric'}) + ' - ' + weekEnd.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
  el.innerHTML = backBtn() + '<div class="report-view">' + reportHeader('Weekly Summary', subtitle)
    + '<div class="report-body">' + weekNav
    + '<div class="report-section-title">By Category</div>'
    + (catSummary || '<div style="color:var(--muted);font-size:13px">No records this week.</div>')
    + '<div class="report-section-title">By Day</div>' + dayRows
    + '<div style="margin-top:14px;font-size:11px;color:var(--muted);text-align:center">Total records this week: ' + weekLogs.length + '</div>'
    + '</div></div>';
}

function renderHandoff(el) {
  var now = new Date();
  var dateStr = fmtDate(reportDate);
  var todayItems = getDayItems(reportDate);
  var done    = todayItems.filter(function(i){ return i.logEntry; });
  var pending = todayItems.filter(function(i){ return !i.logEntry && i.scheduledTs > now.getTime(); });
  var overdue = todayItems.filter(function(i){ return !i.logEntry && i.scheduledTs <= now.getTime(); });
  var recentLogs = logEntries.filter(function(e){ return e.dateStr===dateStr; }).slice(0,8);
  var openTodos  = todos.filter(function(t){ return !t.done; }).slice(0,10);

  function itemRow(i) {
    return '<div class="report-row"><div class="report-time">' + fmt12(i.time) + '</div>'
      + '<div style="flex:1;font-weight:600">' + i.name + '</div></div>';
  }

  var overdueHtml = overdue.length
    ? '<div class="handoff-section" style="background:#fdf0ef;border-left:4px solid var(--warn)">'
      + '<div class="handoff-section-title" style="color:var(--warn)">Overdue (' + overdue.length + ')</div>'
      + overdue.map(itemRow).join('') + '</div>' : '';

  var doneHtml = '<div class="handoff-section"><div class="handoff-section-title">Completed Today (' + done.length + ')</div>'
    + (done.length === 0 ? '<div style="font-size:12px;color:var(--muted)">Nothing completed yet.</div>'
      : done.map(function(i){ return '<div class="report-row"><div class="report-time">' + fmt12(i.time) + '</div>'
        + '<div style="flex:1;font-weight:600">' + i.name + '</div>'
        + '<div style="font-size:11px;color:var(--ok)">' + i.logEntry.caregiver + '</div></div>'; }).join(''))
    + '</div>';

  var pendingHtml = '<div class="handoff-section"><div class="handoff-section-title">Still Pending (' + pending.length + ')</div>'
    + (pending.length === 0 ? '<div style="font-size:12px;color:var(--muted)">All done!</div>' : pending.map(itemRow).join(''))
    + '</div>';

  var todoHtml = openTodos.length
    ? '<div class="handoff-section"><div class="handoff-section-title">Open To-Do (' + openTodos.length + ')</div>'
      + openTodos.map(function(t){ return '<div class="report-row"><div style="flex:1;font-size:13px">' + t.text + '</div></div>'; }).join('')
      + '</div>' : '';

  var logHtml = recentLogs.length
    ? '<div class="handoff-section"><div class="handoff-section-title">Recent Records</div>'
      + recentLogs.map(function(e){
          var cfg = CATS[e.cat] || {icon:'*', color:'#888'};
          return '<div class="report-row"><div class="report-time">' + (e.givenTime?fmt12(e.givenTime):'--') + '</div>'
            + '<div style="flex:1"><span style="font-size:10px;color:' + cfg.color + ';font-weight:700">' + cfg.icon + '</span> ' + e.name + '</div>'
            + '<div style="font-size:11px;color:var(--muted)">' + (e.caregiver||'') + '</div></div>'
            + (e.notes ? '<div class="report-note">' + e.notes + '</div>' : '');
        }).join('') + '</div>' : '';

  var subtitle = now.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'}) + ' &middot; ' + fmt12(nowTime());
  el.innerHTML = backBtn() + '<div class="report-view">' + reportHeader('Caregiver Handoff', subtitle)
    + '<div class="report-body">' + overdueHtml + doneHtml + pendingHtml + todoHtml + logHtml
    + '<div style="margin-top:16px;font-size:11px;color:var(--muted);text-align:center;border-top:1px solid var(--border);padding-top:10px">Becky\'s Care &middot; rnelsonmt.github.io/becky-care</div>'
    + '</div></div>';
}

'''

if start is not None and end is not None:
    new_lines = [l + '\n' for l in reports_js.split('\n')]
    lines = lines[:start] + new_lines + lines[end:]
    with open('index.html', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Done - {len(lines)} lines')
else:
    print(f'Block not found - start:{start} end:{end}')
