import re, sys
content = open('index.html', encoding='utf-8').read()
match = re.search(r'<script type="module">(.*?)</script>', content, re.DOTALL)
if not match:
    print("ERROR: No script tag found")
    sys.exit(1)
js = match.group(1)
opens = js.count("{")
closes = js.count("}")
backticks = js.count("`")
print(f"Braces: {opens} open, {closes} close, diff={opens-closes}")
print(f"Backticks: {backticks}, even={backticks%2==0}")
if opens != closes:
    print("ERROR: Unbalanced braces!")
    sys.exit(1)
if backticks % 2 != 0:
    print("ERROR: Unbalanced backticks!")
    sys.exit(1)
print("OK: JS syntax looks clean")
