# pylint: disable=redefined-builtin
from sys import argv, exit
from cache import userMappings

# pylint: enable=redefined-builtin

if len(argv) < 2:
    exit("No username specified to lookup")

argv.pop(0)
username = " ".join(argv)

for k, v in userMappings.items():
    if username in v:
        print(f"Found it! {k} ({v})")
