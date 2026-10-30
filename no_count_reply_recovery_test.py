"""Reproduce self-sent alert template imports and recover genuine read replies."""
import email,sqlite3,unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock,patch
from test_resources import DatabaseTemporaryDirectory
import no_count_replies as m
ID='NC-20261030-050000'
SUBJECT='TYRETRACK NO COUNT '+ID+' - Supervisor response required'
TEMPLATE='TYRECYCLE | TYRETRACK - SUPERVISOR NO COUNT REPORT\n\nIncident ID: '+ID+'\nSUPERVISOR: Please REPLY to this email.\nReason: [Waiting for tyres / Scheduled break / Conveyor stopped / Maintenance / Camera issue / Other]\nSupervisor: [Your name]\nComments: [Optional details]\n'
ANSWER='Reason: Other\nSupervisor: Greg\nComments: TEST ONLY - checking dashboard reception.\n\n'

def message(mid,body,reply=False,sender='tyrecounter@gmail.com'):
 msg=EmailMessage();msg['From']=sender;msg['To']='tyrecounter@gmail.com'
 msg['Subject']=('Re: ' if reply else '')+SUBJECT;msg['Message-ID']=mid
 if reply:msg['In-Reply-To']='<alert>'
 msg.set_content(body);return msg.as_bytes()

class RecoveryTests(unittest.TestCase):
 def test_original_and_unfilled_forms_rejected(self):
  for body in [TEMPLATE,'Reason: [Other]\nSupervisor: [Your name]', 'Reason: Other\nSupervisor: [Your name]', 'Reason: [Waiting for tyres / Scheduled break / Conveyor stopped]\nSupervisor: Greg']:
   self.assertIsNone(m.parse_reply('Re: '+SUBJECT,body))
 def test_reply_above_unquoted_template(self):
  self.assertEqual(m.parse_reply('Re: '+SUBJECT,ANSWER+TEMPLATE),(ID,'Other','Greg','TEST ONLY - checking dashboard reception.'))
 def test_quoted_template_cannot_complete_incomplete_answer(self):
  self.assertIsNone(m.parse_reply('Re: '+SUBJECT,'Reason: Other\n\n'+TEMPLATE))
 def test_optional_comment_placeholder_removed(self):
  self.assertEqual(m.parse_reply('Re: '+SUBJECT,'Reason: Maintenance\nSupervisor: Greg\nComments: [Optional details]')[-1],'')
 def test_historical_repair_audit_and_idempotency(self):
  with DatabaseTemporaryDirectory() as folder:
   db=Path(folder)/'test.db';m.create_incident(db,ID,'2026-10-30 05:00:00','2026-10-30 05:14:24')
   with m.db_connection(db) as con:
    con.execute("UPDATE supervisor_no_count SET status='COMPLETED',reason=?,supervisor=?,comments=?,message_id=?,received_utc=?,ended_brisbane=?",('[Waiting for tyres / Scheduled break / Conveyor stopped]','[Your name]','[Optional details]','<bad>','old-time','2026-10-30 06:00:00'))
   self.assertIn('0 completed, 1 awaiting',m.summary(db,'2026-10-30'))
   with m.db_connection(db) as con:
    self.assertEqual(con.execute('SELECT message_id,supervisor FROM supervisor_no_count_reply_audit').fetchone(),('<bad>','[Your name]'))
    self.assertEqual(con.execute('SELECT ended_brisbane FROM supervisor_no_count').fetchone()[0],'2026-10-30 06:00:00')
   self.assertTrue(m.record_reply(db,ID,'Other','Greg','TEST ONLY','<real>'))
   self.assertFalse(m.record_reply(db,ID,'Other','Greg','TEST ONLY','<real>'))
   self.assertIn('1 completed, 0 awaiting',m.summary(db,'2026-10-30'))
   with m.db_connection(db) as con:
    m.ensure_table(con);self.assertEqual(con.execute('SELECT COUNT(*) FROM supervisor_no_count_reply_audit').fetchone()[0],1)
    self.assertEqual(con.execute('SELECT supervisor FROM supervisor_no_count').fetchone()[0],'Greg')
 def test_read_reply_recovered_and_unrelated_sender_ignored(self):
  with DatabaseTemporaryDirectory() as folder:
   db=Path(folder)/'test.db';m.create_incident(db,ID,'2026-10-30 05:00:00','2026-10-30 05:14:24')
   raw={b'1':message('<alert>',TEMPLATE),b'2':message('<wrong>',ANSWER,True,'untrusted@example.com'),b'3':message('<real>',ANSWER+TEMPLATE,True)}
   client=MagicMock();client.__enter__.return_value=client
   client.search.return_value=('OK',[b'1 2 3'])
   client.fetch.side_effect=lambda uid,*a:('OK',[(b'RFC822',raw[uid])])
   with patch.object(m.imaplib,'IMAP4_SSL',return_value=client):
    self.assertEqual(m.check_gmail(db,'tyrecounter@gmail.com','TEST_PASSWORD','tyrecounter@gmail.com'),1)
    self.assertEqual(m.check_gmail(db,'tyrecounter@gmail.com','TEST_PASSWORD','tyrecounter@gmail.com'),0)
   self.assertNotIn('UNSEEN',repr(client.search.call_args))
   client.select.assert_called_with('INBOX',readonly=True)
   self.assertIn('Greg',m.summary(db,'2026-10-30'))
   with m.db_connection(db) as con:self.assertEqual(con.execute('SELECT comments,message_id FROM supervisor_no_count').fetchone(),('TEST ONLY - checking dashboard reception.','<real>'))
 def test_record_api_rejects_placeholders_and_unknown_incidents(self):
  with DatabaseTemporaryDirectory() as folder:
   db=Path(folder)/'test.db';m.create_incident(db,ID,'2026-10-30 05:00:00','2026-10-30 05:14:24')
   self.assertFalse(m.record_reply(db,ID,'Other','[Your name]','','<bad>'))
   self.assertFalse(m.record_reply(db,'NC-20260101-050000','Other','Greg','','<unknown>'))

if __name__=='__main__':unittest.main()
