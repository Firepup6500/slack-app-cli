from cache import userMappings
from sys import argv

if len(argv) < 2:
    exit("No username specified to lookup")

argv.pop(0)
username = " ".join(argv)

for k, v in userMappings.items():
    if username in v:
        print(f"Found it! {k} ({v})")
