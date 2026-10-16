#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import fcntl,os,pty,re,select,signal,struct,subprocess,sys,termios,time,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'engine').mkdir(exist_ok=True)
fake=ROOT/'engine/test-fake-codex.py'
fake.write_text('''import ctypes,os,signal,termios,tty,time
ctypes.CDLL(None).prctl(15,b"codex",0,0,0)
old=termios.tcgetattr(0)
tty.setraw(0)
signal.signal(signal.SIGWINCH,lambda *x:None)
print("FAKE_READY pid="+str(os.getpid()),flush=True)
try:
 while True: os.read(0,1)
finally: termios.tcsetattr(0,termios.TCSANOW,old)
''')
def stat(pid):
 a=Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()
 return a[0],int(a[5])

def test(mode):
 shell,master=pty.fork()
 if shell==0:
  os.execv('/bin/bash',['bash','--noprofile','--norc','-i'])
 fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',25,80,0,0))
 os.write(master,f'python3 {fake}\n'.encode())
 captured=bytearray();deadline=time.monotonic()+4;cli=None
 while time.monotonic()<deadline:
  if select.select([master],[],[],.1)[0]: captured.extend(os.read(master,65536))
  m=re.search(rb'FAKE_READY pid=(\d+)',captured)
  if m: cli=int(m[1]);break
 assert cli,'fake CLI did not start'
 ttyname=os.readlink(f'/proc/{cli}/fd/0')
 fd=os.open(ttyname,os.O_RDWR|os.O_NOCTTY)
 original=termios.tcgetattr(fd)
 temporary=tempfile.TemporaryDirectory(prefix='codex-doom-terminal-')
 session_root=Path(temporary.name)
 shutil.copyfile(ROOT/'play-in-codex.py',session_root/'play-in-codex.py')
 (session_root/'engine').symlink_to(ROOT/'engine',target_is_directory=True)
 (session_root/'freedoom1.wad').symlink_to(ROOT/'freedoom1.wad')
 arguments=[sys.executable,str(session_root/'play-in-codex.py'),'--pid',str(cli)]
 if mode=='normal':arguments+=['--seconds','2']
 run=subprocess.Popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 start=time.monotonic();sent=False;interrupted=False;long_quit=False
 try:
  while run.poll() is None or mode=='watchdog' and stat(cli)[0]=='T':
   elapsed=time.monotonic()-start
   if elapsed>.6 and not sent:
    os.write(master,b'wf'+(b'q' if mode=='quit' else b''));sent=True
   if mode in ('interrupt','watchdog','stalled') and elapsed>.8 and not interrupted:
    run.send_signal({'interrupt':signal.SIGTERM,'watchdog':signal.SIGKILL,'stalled':signal.SIGSTOP}[mode]);interrupted=True
   if mode=='stalled' and elapsed>2 and stat(cli)[0] not in ('T','t'):
    run.kill();run.wait();break
   if mode=='unlimited' and elapsed>31 and not long_quit:
    assert run.poll() is None,'unlimited session stopped at the old 30-second limit'
    os.write(master,b'q');long_quit=True
   if select.select([master],[],[],.05)[0]:captured.extend(os.read(master,65536))
   assert elapsed<(45 if mode=='unlimited' else 13),'test deadline exceeded'
  out,err=run.communicate()
  state,fg=stat(cli)
  assert state not in ('T','t'),(mode,state)
  assert fg==os.getpgid(cli),(mode,'foreground',fg,os.getpgid(cli))
  assert stat(shell)[0] not in ('T','t'),(mode,'shell stopped')
  assert termios.tcgetattr(fd)==original,(mode,'terminal settings not restored')
  if mode in ('normal','quit','unlimited'):
   assert run.returncode==0,err.decode()
   log=(session_root/'last-run.log').read_text()
   match=re.search(r'frames=(\d+) inputs=(\d+) elapsed_ms=(\d+)',log)
   assert match and int(match[1])>0 and int(match[2])>=2,log
   if mode=='quit':assert int(match[3])<1900
   if mode=='unlimited':assert int(match[3])>=30000 and long_quit
  print(mode,'PASS',state,'foreground restored; terminal settings restored',flush=True)
 finally:
  if run.poll() is None:run.kill();run.wait()
  for pid in (cli,shell):
   try:os.kill(pid,signal.SIGKILL)
   except ProcessLookupError:pass
  os.waitpid(shell,0);os.close(master);os.close(fd);temporary.cleanup()
for mode in ('normal','quit','interrupt','watchdog','stalled','unlimited'):test(mode)
