"""Supervisor email replies for production No Count incidents.

Uses the existing Gmail sender and app password; never stores credentials in source.
Incoming replies are accepted only from configured supervisor recipients.
"""
import email
import imaplib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr

SCHEMA = '''CREATE TABLE IF NOT EXISTS supervisor_no_count (
 incident_id TEXT PRIMARY KEY, started_brisbane TEXT NOT NULL,
 threshold_brisbane TEXT NOT NULL, ended_brisbane TEXT,
 status TEXT NOT NULL DEFAULT 'AWAITING RESPONSE',
 reason TEXT, supervisor TEXT, comments TEXT,
 received_utc TEXT, message_id TEXT UNIQUE,
 emailed_utc TEXT NOT NULL
)'''
ID_RE = re.compile(r'NC-\d{8}-\d{6}', re.I)
FIELD_RE = re.compile(r'^\s*(?:REASON|SUPERVISOR|COMMENTS)\s*:\s*(.*)$', re.I)


@contextmanager
def db_connection(db):
    """Commit/rollback transactions AND close the connection on Windows.

    sqlite3.Connection.__exit__ commits or rolls back but does not close.
    An open connection can lock test.db and prevent TemporaryDirectory cleanup.
    """
    con = sqlite3.connect(db, timeout=15)
    try:
        with con:
            yield con
    finally:
        con.close()


def ensure_table(con):
    con.execute(SCHEMA)
    repair_template_responses(con)


def placeholder(value):
    """Reject instructions and untouched bracketed form fields, not real answers."""
    value=str(value or '').strip()
    folded=value.casefold()
    return bool(value and (
        (value.startswith('[') and value.endswith(']'))
        or folded in ('your name', 'optional details')
        or ('waiting for tyres' in folded and 'scheduled break' in folded and '/' in folded)
        or folded.startswith('please reply to this email')))


def repair_template_responses(con):
    """Reopen only recognisable template imports and keep their original evidence.

    Run inside the caller's transaction. Repeated calls leave genuine responses
    and incident start/end/email timestamps untouched.
    """
    rows=con.execute("SELECT incident_id,reason,supervisor,comments,received_utc,message_id FROM supervisor_no_count WHERE status='COMPLETED'").fetchall()
    bad=[row for row in rows if placeholder(row[1]) or placeholder(row[2])]
    if not bad:return 0
    con.execute('CREATE TABLE IF NOT EXISTS supervisor_no_count_reply_audit (audit_id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL, reason TEXT, supervisor TEXT, comments TEXT, received_utc TEXT, message_id TEXT, repaired_utc TEXT NOT NULL, repair_note TEXT NOT NULL)')
    for row in bad:
        con.execute('INSERT INTO supervisor_no_count_reply_audit (incident_id,reason,supervisor,comments,received_utc,message_id,repaired_utc,repair_note) VALUES (?,?,?,?,?,?,?,?)',
            (*row,datetime.now(timezone.utc).isoformat(),'Reopened automatic template import; awaiting genuine supervisor reply'))
        con.execute("UPDATE supervisor_no_count SET status='AWAITING RESPONSE',reason=NULL,supervisor=NULL,comments=NULL,received_utc=NULL,message_id=NULL WHERE incident_id=?",(row[0],))
    return len(bad)


def create_incident(db, incident_id, start, threshold):
    with db_connection(db) as con:
        ensure_table(con)
        con.execute('INSERT OR IGNORE INTO supervisor_no_count (incident_id,started_brisbane,threshold_brisbane,emailed_utc) VALUES (?,?,?,?)',
                    (incident_id, start, threshold, datetime.now(timezone.utc).isoformat()))


def close_incident(db, when):
    with db_connection(db) as con:
        ensure_table(con)
        con.execute('UPDATE supervisor_no_count SET ended_brisbane=? WHERE ended_brisbane IS NULL', (when,))


def summary(db, day):
    with db_connection(db) as con:
        ensure_table(con)
        rows = con.execute('SELECT incident_id,status,COALESCE(reason,\'Awaiting supervisor reply\'),COALESCE(supervisor,\'\'),started_brisbane,COALESCE(ended_brisbane,\'\') FROM supervisor_no_count WHERE started_brisbane LIKE ? ORDER BY started_brisbane', (day+'%',)).fetchall()
    if not rows:
        return 'Supervisor No Count reports: none recorded.\n'
    lines = [f'Supervisor No Count reports: {len(rows)} ({sum(r[1] == "COMPLETED" for r in rows)} completed, {sum(r[1] != "COMPLETED" for r in rows)} awaiting)']
    for incident,status,reason,supervisor,start,end in rows:
        lines.append(f'{incident} | {status} | {reason} | {supervisor or "Unassigned"} | {start} - {end or "ongoing"}')
    return '\n'.join(lines)+'\n'


def message_text(message):
    if message.is_multipart():
        parts = [p for p in message.walk() if p.get_content_type() == 'text/plain' and p.get_content_disposition() != 'attachment']
        return '\n'.join(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', 'replace') for p in parts)
    if message.get_content_type() != 'text/plain':
        return ''
    raw = message.get_payload(decode=True)
    return raw.decode(message.get_content_charset() or 'utf-8', 'replace') if raw else ''


def parse_reply(subject, body):
    # Only the supervisor's NEW text before quoted email is parsed.
    fresh=[]
    for line in body.splitlines():
        if (line.lstrip().startswith('>') or re.match(r'^On .+ wrote:\s*$', line, re.I)
                or line.strip() in ('-----Original Message-----', 'END OF RESPONSE')
                or 'SUPERVISOR NO COUNT REPORT' in line.upper()
                or re.match(r'^\s*SUPERVISOR:\s*Please REPLY',line,re.I)):
            break
        fresh.append(line)
    fresh='\n'.join(fresh)
    ids = ID_RE.findall(subject)
    if not ids:
        ids = ID_RE.findall(fresh)
    if not ids:
        return None
    fields={}
    for line in fresh.splitlines():
        match=FIELD_RE.match(line)
        if match:
            key=line.split(':',1)[0].strip().lower()
            fields[key]=match.group(1).strip()[:1000]
    if (not fields.get('reason') or not fields.get('supervisor')
            or placeholder(fields['reason']) or placeholder(fields['supervisor'])):
        return None
    if placeholder(fields.get('comments','')):fields['comments']=''
    return ids[0].upper(), fields['reason'][:150], fields['supervisor'][:120], fields.get('comments','')[:1000]


def record_reply(db, incident_id, reason, supervisor, comments, message_id):
    if not reason.strip() or not supervisor.strip() or placeholder(reason) or placeholder(supervisor):return False
    with db_connection(db) as con:
        ensure_table(con)
        cur=con.execute('UPDATE supervisor_no_count SET status=?, reason=?, supervisor=?, comments=?, received_utc=?, message_id=? WHERE incident_id=? AND status != ? AND (message_id IS NULL OR message_id != ?)',
            ('COMPLETED',reason,supervisor,comments,datetime.now(timezone.utc).isoformat(),message_id,incident_id,'COMPLETED',message_id))
        return cur.rowcount == 1


def check_gmail(db, sender, password, supervisor_addresses, logger=lambda message: None):
    """Fetch recent alert-thread replies, including read mail, without changing mailbox flags."""
    allowed={a.lower() for _,a in getaddresses([supervisor_addresses]) if a}
    if not allowed:
        return 0
    # Repair bad historical imports even when no new message is available.
    with db_connection(db) as con:ensure_table(con)
    saved=0
    with imaplib.IMAP4_SSL('imap.gmail.com', 993, timeout=12) as client:
        client.login(sender, password)
        client.select('INBOX', readonly=True)
        typ,data=client.search(None, 'SUBJECT', '"TYRETRACK NO COUNT"')
        if typ != 'OK':
            return 0
        for uid in data[0].split()[-200:]:
            typ,parts=client.fetch(uid, '(RFC822)')
            if typ != 'OK':
                continue
            raw=next((p[1] for p in parts if isinstance(p,tuple) and len(p)>1),None)
            if not raw:
                continue
            msg=email.message_from_bytes(raw)
            from_address=parseaddr(msg.get('From',''))[1].lower()
            if from_address not in allowed:
                continue
            subject=str(make_header(decode_header(msg.get('Subject',''))))
            # Alerts may be sent to the sender's own inbox. They are not replies.
            if not (msg.get('In-Reply-To') or msg.get('References') or re.match(r'^\s*re\s*:',subject,re.I)):
                continue
            parsed=parse_reply(subject,message_text(msg))
            if not parsed:
                continue
            mid=(msg.get('Message-ID') or f'imap-{uid.decode("ascii","replace")}')[:255]
            if record_reply(db,*parsed,mid):
                saved+=1
                logger(f'No Count supervisor response recorded: {parsed[0]}')
    return saved
