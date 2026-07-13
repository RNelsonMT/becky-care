import re, sys
content = open('index.html', encoding='utf-8').read()
match = re.search(r'<script type="module">(.*?)</script>', content, re.DOTALL)
if not match:
    print("ERROR: No script tag found")
    sys.exit(1)
js = match.group(1)
opens = js.count("{")
closes = js.count("}")
bt = js.count("`")
print(f"Braces: {opens} open, {closes} close, diff={opens-closes}")
print(f"Backticks: {bt}, even={bt%2==0}")
if opens != closes:
    print("ERROR: Unbalanced braces!")
    sys.exit(1)
if bt % 2 != 0:
    print("ERROR: Unbalanced backticks!")
    sys.exit(1)
# Check for broken onclick patterns
lines = js.split('\n')
bad = []
for i,l in enumerate(lines):
    if "onclick=" in l and "''" in l and "tabBar" in l:
        bad.append(f"Line {i+1}: broken onclick: {l[:80]}")
    if "measView=''" in l or "measFilter=''" in l:
        bad.append(f"Line {i+1}: broken meas onclick: {l[:80]}")
if bad:
    for b in bad: print("ERROR:", b)
    sys.exit(1)
print("OK: JS syntax looks clean")
