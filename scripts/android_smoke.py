"""Exercise the installed NextRole debug build on the named Android emulator.

Uses observed UI accessibility bounds, and captures unmodified runtime screenshots.
"""
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERIAL='emulator-5554'
def adb(*args):return subprocess.check_output(['adb','-s',SERIAL,*args])
def nodes():
    for _ in range(4):
        path=f'/sdcard/nextrole-window-{time.time_ns()}.xml'
        result=adb('shell','uiautomator','dump',path)
        if b'dumped to:' in result:
            content=adb('shell','cat',path)
            adb('shell','rm',path)
            return list(ET.fromstring(content).iter('node'))
        time.sleep(.5)
    raise RuntimeError('Could not obtain a fresh UI hierarchy; refusing stale bounds')
def find(value,attr='content-desc',partial=False):
    for n in nodes():
        text=n.get(attr,'')
        if (value in text if partial else value==text):return n
    return None
def tap(value,attr='content-desc',partial=False):
    n=find(value,attr,partial)
    if n is None:raise AssertionError(f'Control absent: {value}')
    x1,y1,x2,y2=map(int,re.findall(r'\d+',n.attrib['bounds']))
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
    time.sleep(.5)
def shot(name):
    (ROOT/'evidence'/name).write_bytes(adb('exec-out','screencap','-p'))
def main():
    # Restart this app only. Saved data is preserved.
    adb('shell','am','force-stop','edu.nextrole.nextrole')
    adb('shell','am','start','-n','edu.nextrole.nextrole/.MainActivity')
    time.sleep(2)
    tap('Role or skills','hint');adb('shell','input','text','Engineer');adb('shell','input','keyevent','4')
    tap('Find my next role ↗');time.sleep(1)
    assert find('Opportunities (',partial=True) is not None,'API results missing'
    shot('android-search.png')
    for _ in range(4):
        if find('Why this role? ↗') is not None:break
        adb('shell','input','swipe','550','1900','550','950','300')
    tap('Why this role? ↗');time.sleep(.4)
    assert find('Why this role appeared') is not None,'Explanation missing'
    shot('android-detail.png');tap('Close details')
    # Locate a visible save button by its actual accessibility label.
    save=next((n.get('content-desc') for n in nodes() if n.get('content-desc','').startswith('Save ')),None)
    if save:tap(save)
    tap('Saved (',partial=True);time.sleep(.3)
    assert find('Your shortlist') is not None
    shot('android-saved.png')
    tap('العربية');time.sleep(.3)
    assert find('قائمتك المختصرة') is not None
    shot('android-arabic.png')
    tap('English');tap('Discover',partial=True)
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'serial':SERIAL,'device':adb('shell','getprop','ro.product.model').decode().strip(),'android':adb('shell','getprop','ro.build.version.release').decode().strip(),'runtime':'Android emulator, debug APK','checks':['public API search','ranked results','explanation dialog','saved shortlist','Arabic layout'],'physical_device_tested':False}
    (ROOT/'evidence/android-smoke.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
