TYRETRACK — MANAGEMENT BRIEFINGS

WHAT IS INCLUDED
Daily management email after the 17:05 Brisbane close, Monday-Friday.
Friday also sends a separate Monday-Friday weekly production briefing.
Existing compact hourly emails and no-count supervisor reply handling remain.
Uses the existing sender/app-password and management recipient in email_config.ini.
No new account, online service, credit subscription or remote report hosting.

The email has a formatted summary, estimated kg/EPU and a timestamped dashboard
image when available. PDF and UTF-8 CSV files are attached directly for download.
The report folder also keeps a JSON audit snapshot of the calculated figures.

PDF CONTENT
Tyrecycle/Ozcom heading; total tyres, estimated tonnes, EPU, average production,
best daily total and all-time OAK counts; hourly production bars; five weekday
bars; tyre classification doughnut; hour-by-hour detail; no-count gaps;
supervisor reasons/replies; recorded live foreign alerts; recording filenames.
Uses tyrecycle_logo.png when supplied beside the source/bundled application.
Normal report is two pages; longer operational detail continues onto extra pages.
The included preview PDF is explicitly marked DEMONSTRATION DATA.

EXPORT WITHOUT EMAIL
Admin Settings > Reports:
- Export today's management PDF + CSV
- Export this week's management PDF + CSV
The folder opens after export on Windows. Reports are saved in reports/management.
Exports during the shift are labelled provisional; the comparison with a full
previous day/week is omitted until the current production period has closed.
Test/video/manual counts do not enter production reports.

METRICS AND LIMITS
Passenger 8 kg / 1 EPU; SUV/4x4 16 kg / 2 EPU; truck 45 kg / 5 EPU.
Weights are estimates. Unknown tyres retain their count but no weight/EPU.
The current model still needs truck-labelled count data for truck figures.
The average per hour is normalised over elapsed scheduled production time,
including the final five-minute slot; it may differ from an unweighted mean of
completed dashboard slots. Weekly hourly bars combine matching clock hours.
No-count gaps do not establish camera availability or conveyor stoppage.
Foreign alerts are from a trial model; test alarms are excluded. No recorded
alerts do not prove monitoring was enabled. Recording file references do not
verify continuous camera coverage. The full reference list is in the CSV.

AUTOMATION AND RETRIES
The app must be running, with its existing production/email automation enabled.
Reports use existing counts. Successful daily/weekly sends are marked in the
existing state table; failures are retried by the email worker. SMTP acceptance
is not proof of inbox delivery. New briefing emails start with the next eligible
unsent reporting period; the upgrade does not resend an already-sent daily email.
CSV/PDF generation runs outside the GUI thread and does not access the OAK.

INSTALLATION
This is complete GitHub-ready source, not a compiled Windows EXE.
Extract all files over the matching repository source and run the included
Windows workflow. Install the newly built portable release with TyreTrack closed.
Keep the site's existing data, reports, email_config.ini and private settings.
The dependency list adds ReportLab for PDF generation and pypdf for CI checks;
existing camera/AI dependency pins are retained.

VALIDATION
34 regression scripts passed locally; PDF figures reconcile with the CSV;
Brisbane shift and source filters, legacy timestamps, estimated weights,
weekly summaries, provisional reports, MIME attachments/inline image, mocked
SMTP failures/retries and send deduplication are checked. Real Qt export tested.
The build smoke test now creates a PDF with bundled fonts inside the actual
packaged executable on Windows CI. Local source smoke passed. Real SMTP/inbox
delivery and Windows executable compilation were not performed here.
