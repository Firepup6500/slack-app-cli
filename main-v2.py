from os import environ as env
from sys import argv
from slack_bolt import App
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import firepup650 as fp
from traceback import format_exc
from time import sleep
from base64 import b64encode

input = fp.replitInput

fp.replitCursor = (
    fp.bcolors.REPLIT + ">>>" + fp.bcolors.RESET
)  # Totally not hijacking one of my functions to use ;P

load_dotenv()

for requiredVar in ["SLACK_BOT_TOKEN"]:
    if not env.get(requiredVar):
        raise ValueError(
            f'Missing required environment variable "{requiredVar}". Please create a .env file in the same directory as this script and define the missing variable.'
        )

print("[INFO] Establishing a connection to slack...")
app = App(token=env.get("SLACK_BOT_TOKEN"))
client = app.client


def encode(string: str) -> str:
    return b64encode(string.encode("utf-8")).decode("utf-8")


def __writeCache(userCache, botCache, cursorCache):
    with open(
        "cache.py", "w"
    ) as cacheFile:  # It is many times faster to load from a local file instead of from slack
        cacheFile.writelines(
            [
                f"userMappings = {userCache}\n",
                f"botMappings = {botCache}\n",
                f'cursorCache = "{cursorCache}"\n',
            ]
        )
    print("[INFO] Cache saved.")


def __generateCache(userCache, botCache, cursor):
    users_list = []
    pages = 0
    while (
        cursor
    ):  # If slack gives us a cursor, then we ain't done loading user data yet
        data = None
        while not data:  # Ratelimit logic
            try:
                if cursor != "N/A":
                    data = client.users_list(cursor=cursor, limit=1000)
                else:
                    data = client.users_list(limit=1000)
            except SlackApiError as e:
                retry = e.response.headers["retry-after"]
                print(
                    f"[WARN] Ratelimit hit! Sleeping for {retry} seconds as the retry-after header has specified"
                )
                sleep(int(retry))
                print("[WARN] Resuming..")
        cursor = data["response_metadata"]["next_cursor"]
        users_list.extend(data["members"])
        pages += 1
        print(
            f"[INFO] Pages of users loaded: {pages} ({'User count is less than' if not cursor else 'Estimated user count so far:'} {pages}000)"
        )
    if len(users_list) == 0:
        exit(
            f"[EXIT] Slack returned exactly zero users when given a cursor, which means my cursor is corrupt. Please delete cache.py and re-run the script."
        )
    cursorCache = encode(f"user:{users_list[-1]['id']}")
    if len(users_list) == 1:
        print("[INFO] No new users to load.")
        return userCache, botCache, cursorCache
    del pages
    print("[INFO] Building user and bot mappings now, this shouldn't take long...")
    for (
        user
    ) in (
        users_list
    ):  # Map user ID mentions to user ID + name mentions, it's nicer when printing messages.
        userCache[f"<@{user['id']}>"] = (
            f"<@{user['id']}|{user['profile']['display_name_normalized']}>"
            if user["profile"].get("display_name_normalized")
            else (  # User is missing a display name for some reason, fallback to real names
                f"<@{user['id']}|{user['profile']['real_name_normalized']}>"
                if user["profile"].get("real_name_normalized")
                else f"<@{user['id']}|{user['name']}>"  # User is missing a real name too... Fallback to raw name
            )
        )
        if user["is_bot"]:
            botCache[user["profile"]["bot_id"]] = user["id"]
    return userCache, botCache, cursorCache


def __innerMessageParser(message: dict) -> dict:
    try:
        if not message.get("user") and message.get("bot_id"):  # Apps sometimes don't...
            bot_id = message["bot_id"]
            if botMappings.get(bot_id):
                message["user"] = botMappings[bot_id]
            else:
                print(
                    """[WARN] Unknown bot {bot_id}!
[WARN] Cache may be out of date!"""
                )
                message["user"] = f"{bot_id}|UNKNOWN BOT"
    except Exception:
        print("[WARN] Exception")
        for line in format_exc().split("\n")[:-1]:
            print(f"[WARN] {line}")
        print(f"[HELP] Raw message that caused this error: {message}")
        message["user"] = "AN EXCEPTION OCCURED|UNKOWN USER"
    if not message.get("user"):
        print(message)
        message["user"] = "FALLBACK|UNKNOWN USER"
    return message


def buildThreadedMessages(messages: dict) -> dict:
    print("[INFO] Building messages, this might take a little bit...")
    texts = {}
    for i in range(len(messages)):
        message = __innerMessageParser(messages[i])
        label = f'[{message["ts"]}] <@{message["user"]}>: {message["text"]}'
        for user in userMappings:
            label = label.replace(user, userMappings[user])
        texts[label] = i
    return texts


def buildMessages(messages: dict) -> str:
    print("[INFO] Building messages, this might take a little bit...")
    for i in range(len(messages) - 1, -1, -1):
        message = __innerMessageParser(messages[i])
        msg = f'[MSGS] [{message["ts"]}] <@{message["user"]}>: {message["text"]}'
        for user in userMappings:
            msg = msg.replace(user, userMappings[user])
        print(msg)
    return messages[0]["ts"]


userMappings = {}
botMappings = {}
cursor = "N/A"
try:
    if "--no-cache" in argv:
        print("[INFO] Skipping cache on user request")
        raise ImportError("User requested to skip cache")
    print("[INFO] Trying to load user and app mappings from cache...")
    from cache import userMappings, cursorCache, botMappings

    print(
        """[INFO] Cache load OK.
[INFO] Reminder: If you need to regenerate the cache, call the script with `--no-cache`"""
    )
    print("[INFO] Checking for slack users newer than my cache...")
    userMappings, botMappings, cursor = __generateCache(
        userMappings, botMappings, cursorCache
    )
    if cursor != cursorCache:
        print("[INFO] New user and app mappings generated, writing cache file now...")
        __writeCache(userMappings, botMappings, cursor)
except ImportError:
    print("[WARN] Cache load failed, falling back to full load from slack...")
    userMappings, botMappings, cursor = __generateCache({}, {}, "N/A")
    print("[INFO] All user and app mappings generated, writing cache file now...")
    __writeCache(userMappings, botMappings, cursor)

print("[INFO] User mappings loaded. User count:", len(userMappings))
print("[INFO] Bot  mappings loaded. Bot  count:", len(botMappings))

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
