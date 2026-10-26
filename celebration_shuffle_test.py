import json,random,tempfile,unittest,wave
from pathlib import Path
from celebration_library import plan_shuffle,import_wav,catalog,validate_wav

class ShuffleTest(unittest.TestCase):
 def test_complete_cycles_and_restart(self):
  keys=list('abcdefg');state={};sequence=[]
  for cycle in range(4):
   played=[]
   for _ in keys:
    key,state=plan_shuffle(keys,json.loads(json.dumps(state)),random.Random(len(sequence)))
    played.append(key);sequence.append(key)
   self.assertEqual(set(played),set(keys));self.assertEqual(len(set(played)),len(keys))
  self.assertTrue(all(a!=b for a,b in zip(sequence,sequence[1:])))
 def test_removed_and_added_files(self):
  key,state=plan_shuffle(['a','b'],{})
  key,state=plan_shuffle(['c'],state);self.assertEqual(key,'c')
  key,state=plan_shuffle(['c','d'],state);self.assertEqual(key,'d')
 def test_empty_and_corrupt_state(self):
  with self.assertRaises(ValueError):plan_shuffle([],{})
  for state in [None,[],{'remaining':None},{'remaining':['a','a',{},'missing']}]:
   key,new=plan_shuffle(['a','b'],state);self.assertIn(key,['a','b'])
 def test_custom_pcm_import_restart_duplicate_and_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'Aussie cheer.wav';folder=root/'sounds'
   with wave.open(str(p),'wb') as w:
    w.setparams((1,2,8000,0,'NONE','not compressed'));w.writeframes(b'\x10\x10'*8000)
   key=import_wav(p,folder);self.assertEqual(import_wav(p,folder),key)
   sounds=catalog({},folder);self.assertIn(key,sounds);self.assertEqual(len(sounds),1)
   self.assertTrue(Path(sounds[key][1]).is_file());self.assertIn('Aussie cheer',sounds[key][0])
   broken=root/'broken.wav';broken.write_bytes(b'not audio')
   with self.assertRaises(ValueError):import_wav(broken,folder)
   broken.write_bytes(p.read_bytes()[:-5])
   with self.assertRaises(ValueError):validate_wav(broken)
if __name__=='__main__':unittest.main()
