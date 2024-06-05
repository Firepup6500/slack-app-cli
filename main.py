import os, sys
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import firepup650 as fp

input = fp.replitInput

fp.replitCursor = (
    fp.bcolors.REPLIT + ">>>" + fp.bcolors.RESET
)  # Totally not hijacking one of my functions to use ;P

load_dotenv()

for requiredVar in ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]:
    if not os.environ.get(requiredVar):
        raise ValueError(
            f'Missing required environment variable "{requiredVar}". Please create a .env file in the same directory as this script and define the missing variable.'
        )

print("Establishing a connection to slack...")
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

userMappings = {}
try:
    if "--no-cache" in sys.argv:
        print("Skipping cache on user request")
        raise ImportError("User requested to skip cache")
    print("Trying to load user mappings from cache...")
    from cache import userMappings

    print(
        "Cache load OK. Reminder: If you need to regenerate the cache, call the script with `--no-cache`"
    )
except ImportError:
    users_list = []
    print("Cache load failed, falling back to full load from slack...")
    cursor = "N/A"
    pages = 0
    while (
        cursor
    ):  # If slack gives us a cursor, then we ain't done loading user data yet
        data = ""
        if cursor != "N/A":
            data = client.users_list(cursor=cursor, limit=1000)
        else:
            data = client.users_list(limit=1000)
        cursor = data["response_metadata"]["next_cursor"]
        users_list.extend(data["members"])
        pages += 1
        print(f"Pages of users loaded: {pages}")
    del pages
    print("Building user mappings now, this shouldn't take long...")
    for (
        user
    ) in (
        users_list
    ):  # Map user ID mentions to user name mentions, it's nicer when printing messages for thread selection.
        userMappings[f"<@{user['id']}>"] = (
            f"<@{user['profile']['display_name_normalized']}>"
            if user["profile"]["display_name_normalized"]
            else (  # User is missing a display name for some reason, fallback to real names
                f"<@{user['profile']['real_name_normalized']}>"
                if user["profile"]["real_name_normalized"]
                else f"<@{user['id']}>"  # User is missing a real name too... Fallback to ID
            )
        )
    print("All mappings generated, writing cache file now...")
    with open(
        "cache.py", "w"
    ) as cacheFile:  # It is many times faster to load from a local file instead of from slack
        cacheFile.write(f"userMappings = {userMappings}")
    print("Cache saved.")

print("User mappings loaded. User count:", len(userMappings))

if __name__ == "__main__":
    print("^D at any time to terminate program")
    while 1:
        chan = input("Channel ID")
        try:
            print("^C to change channel")
            while 1:
                thread = input("Reply to a thread? (y|N)").lower().startswith("y")
                ts = None
                if thread:
                    hasID = (
                        input("Do you have the TS ID? (y|N))").lower().startswith("y")
                    )
                    if not hasID:
                        try:
                            print(
                                "Getting the last 50 messages for threading options..."
                            )
                            res = client.conversations_history(
                                channel=chan, inclusive=True, limit=50
                            )
                            messages = res["messages"]
                            texts = {}
                            print("Building messages, this might take a little bit...")
                            for i in range(len(messages)):
                                label = f'{messages[i]["text"]} ({messages[i]["ts"]})'
                                for user in userMappings:
                                    label = label.replace(user, userMappings[user])
                                texts[label] = i
                            found = messages[
                                fp.menu(
                                    texts,
                                    "Please select the message to reply to as a thread",
                                )
                            ]
                            ts = found["ts"]
                        except Exception as E:
                            print(f"Exception: {E}")
                            break
                    else:
                        ts = input("TS ID")
                    print(
                        "^C to change/exit thread (^C twice if you want to change channel)"
                    )
                    try:
                        while 1:
                            msg = input(
                                "[THREAD] Message (Raw text, not blocks)"
                            ).replace("\\n", "\n")
                            try:
                                client.chat_postMessage(
                                    channel=chan, text=msg, thread_ts=ts
                                )
                                print("Message sent (to the thread)!")
                            except Exception as E:
                                print(f"Exception: {E}")
                    except KeyboardInterrupt:
                        print()
                if ts:
                    continue
                msg = input("[CHANNEL] Message (Raw text, not blocks)").replace(
                    "\\n", "\n"
                )
                try:
                    client.chat_postMessage(channel=chan, text=msg)
                    print("Message sent (to the channel)!")
                except Exception as E:
                    print(f"Exception: {E}")
        except KeyboardInterrupt:
            print()
