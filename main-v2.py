import os, sys
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import firepup650 as fp
from traceback import format_exc

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

print("[INFO] Establishing a connection to slack...")
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client


def buildThreadedMessages(messages: dict) -> dict:
    print("[INFO] Building messages, this might take a little bit...")
    texts = {}
    for i in range(len(messages)):
        if not messages[i].get("user") and messages[i].get(
            "username"
        ):  # Workflows don't have a userid, obviously
            messages[i]["user"] = f'{messages[i].get("username")}|WORKFLOW'
        if not messages[i].get("user") and messages[i].get(
            "subtype"
        ):  # Apps sending to channel also don't...
            messages[i]["user"] = messages[i]["root"][
                "user"
            ]  # This is probably technically wrong, but I don't care.
        label = f'[{messages[i]["ts"]}] <@{messages[i]["user"]}>: {messages[i]["text"]}'
        for user in userMappings:
            label = label.replace(user, userMappings[user])
        texts[label] = i
    return texts


def buildMessages(messages: dict) -> str:
    print("[INFO] Building messages, this might take a little bit...")
    for i in range(len(messages) - 1, -1, -1):
        if not messages[i].get("user") and messages[i].get(
            "username"
        ):  # Workflows don't have a userid, obviously
            messages[i]["user"] = f'{messages[i].get("username")}|WORKFLOW'
        if not messages[i].get("user") and messages[i].get(
            "subtype"
        ):  # Apps sending to channel also don't...
            messages[i]["user"] = messages[i]["root"][
                "user"
            ]  # This is probably technically wrong, but I don't care.
        msg = f'[MSGS] [{messages[i]["ts"]}] <@{messages[i]["user"]}>: {messages[i]["text"]}'
        for user in userMappings:
            msg = msg.replace(user, userMappings[user])
        print(msg)
    return messages[0]["ts"]


userMappings = {}
try:
    if "--no-cache" in sys.argv:
        print("[INFO] Skipping cache on user request")
        raise ImportError("User requested to skip cache")
    print("[INFO] Trying to load user mappings from cache...")
    from cache import userMappings

    print(
        """[INFO] Cache load OK.
[INFO] Reminder: If you need to regenerate the cache, call the script with `--no-cache`"""
    )
except ImportError:
    users_list = []
    print("[WARN] Cache load failed, falling back to full load from slack...")
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
        print(
            f"[INFO] Pages of users loaded: {pages} (Estimated user count: {pages}000)"
        )
    del pages
    print("[INFO] Building user mappings now, this shouldn't take long...")
    # print(users_list[38])
    for (
        user
    ) in (
        users_list
    ):  # Map user ID mentions to user name mentions, it's nicer when printing messages for thread selection.
        userMappings[f"<@{user['id']}>"] = (
            f"<@{user['id']}|{user['profile']['display_name_normalized']}>"
            if user["profile"]["display_name_normalized"]
            else (  # User is missing a display name for some reason, fallback to real names
                f"<@{user['id']}|{user['profile']['real_name_normalized']}>"
                if user["profile"]["real_name_normalized"]
                else f"<@{user['id']}>"  # User is missing a real name too... Fallback to ID
            )
        )
    print("[INFO] All mappings generated, writing cache file now...")
    with open(
        "cache.py", "w"
    ) as cacheFile:  # It is many times faster to load from a local file instead of from slack
        cacheFile.write(f"userMappings = {userMappings}")
    print("[INFO] Cache saved.")

print("[INFO] User mappings loaded. User count:", len(userMappings))

global inChannel
inChannel = False

if __name__ == "__main__":
    print("[INFO] ^D at any time to terminate program")
    while 1:
        chan = input("Channel ID")
        try:
            oldest_ts = ""
            try:
                print(
                    "[INFO] Trying to load the last 50 messages sent in this channel..."
                )
                res = client.conversations_history(
                    channel=chan, inclusive=True, limit=50
                )
                buildMessages(res["messages"])
                oldest_ts = res["messages"][0]["ts"]
                del res
            except Exception as E:
                print("[WARN] Exception")
                for line in format_exc().split("\n")[:-1]:
                    print(f"[WARN] {line}")
                print(
                    "[HELP] The bot probably isn't in this channel. If it's public you can likely send anyways, but this will fail otherwise."
                )
            print("[INFO] ^C to change channel")
            while 1:
                thread = input("Reply to a thread? (y|N)").lower().startswith("y")
                ts = None
                if thread:
                    hasID = (
                        input("Do you have the TS ID? (y|N)").lower().startswith("y")
                    )
                    if not hasID:
                        try:
                            print(
                                "[INFO] Getting the last 50 messages for threading options..."
                            )
                            res = client.conversations_history(
                                channel=chan, inclusive=True, limit=50
                            )
                            messages = res["messages"]
                            texts = buildThreadedMessages(messages)
                            found = messages[
                                fp.menu(
                                    texts,
                                    "Please select the message to reply to as a thread",
                                )
                            ]
                            ts = found["ts"]
                        except Exception as E:
                            print("[WARN] Exception:")
                            for line in format_exc().split("\n")[:-1]:
                                print(f"[WARN] {line}")
                            print(
                                "[HELP] Does the bot have access to the channel you're trying to see?"
                            )
                            break
                    else:
                        ts = input("TS ID")
                    print(
                        "[INFO] ^C to change/exit thread (^C twice if you want to change channel)"
                    )
                    try:
                        while 1:
                            msg = input(
                                "[THRD] Message (Raw text, not blocks)"
                            ).replace("\\n", "\n")
                            try:
                                client.chat_postMessage(
                                    channel=chan, text=msg, thread_ts=ts
                                )
                                print("[INFO] Message sent (to the thread)!")
                            except Exception as E:
                                print("[WARN] Exception:")
                                for line in format_exc().split("\n")[:-1]:
                                    print(f"[WARN] {line}")
                                break
                    except KeyboardInterrupt:
                        print()
                if ts:
                    try:
                        print(f"[INFO] Trying to load messages since {oldest_ts}...")
                        res = client.conversations_history(
                            channel=chan, inclusive=True, limit=200, oldest=oldest_ts
                        )
                        if len(res["messages"]) > 1:
                            buildMessages(res["messages"][:-1])
                            oldest_ts = res["messages"][0]["ts"]
                        else:
                            print("[INFO] No new messages")
                        del res
                    except Exception as E:
                        print("[WARN] Exception")
                        for line in format_exc().split("\n")[:-1]:
                            print(f"[WARN] {line}")
                        print(
                            "[HELP] Does the bot have access to the channel you're trying to see?"
                        )
                    continue
                msg = input("[CHAN] Message (Raw text, not blocks)").replace(
                    "\\n", "\n"
                )
                try:
                    if msg != "":
                        ts = client.chat_postMessage(channel=chan, text=msg)["ts"]
                        print(f"[INFO] Message sent (to the channel)! (TS ID: {ts})")
                    try:
                        print(f"[INFO] Trying to load messages since {oldest_ts}...")
                        res = client.conversations_history(
                            channel=chan, inclusive=True, limit=200, oldest=oldest_ts
                        )
                        if len(res["messages"]) > 1:
                            buildMessages(res["messages"][:-1])
                            oldest_ts = res["messages"][0]["ts"]
                        else:
                            print("[INFO] No new messages")
                        del res
                    except Exception as E:
                        print("[WARN] Exception")
                        for line in format_exc().split("\n")[:-1]:
                            print(f"[WARN] {line}")
                        print(
                            "[HELP] Does the bot have access to the channel you're trying to see?"
                        )
                except Exception as E:
                    print("[WARN] Exception:")
                    for line in format_exc().split("\n")[:-1]:
                        print(f"[WARN] {line}")
                    break
        except KeyboardInterrupt:
            print()
