# pylint: disable=redefined-builtin
from os import environ as env, get_terminal_size
from sys import argv, exit
from traceback import format_exc
from time import sleep
from base64 import b64encode
from typing import NoReturn, Callable, Union
from slack_bolt import App
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import firepup650 as fp

input = fp.replitInput
# pylint: enable=redefined-builtin

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


def usable_rows(unusable: int = 2) -> int:
    return get_terminal_size()[1] - unusable


def __writeCache(
    userCache: dict, botCache: dict, appCache: dict, cursorCache: str
) -> None:
    with open(
        "cache.py", "w", encoding="utf-8"
    ) as cacheFile:  # It is many times faster to load from a local file instead of from slack
        cacheFile.writelines(
            [
                "# pylint: skip-file\n",
                "# ^ the cache file should not be linted.\n",
                f"userMappings = {userCache}\n",
                f"botMappings = {botCache}\n",
                f"appMappings = {appCache}\n",
                f'cursorCache = "{cursorCache}"\n',
            ]
        )
    print("[INFO] Cache saved.")


def __generateCache(
    userCache: Union[dict, None] = None,
    botCache: Union[dict, None] = None,
    appCache: Union[dict, None] = None,
    cursor: str = "N/A",
) -> tuple[dict, dict, dict, str]:
    if userCache is None:
        userCache = {}
    if botCache is None:
        botCache = {}
    if appCache is None:
        appCache = {}
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
            "[EXIT] Slack returned exactly zero users when given a cursor, which means my cursor is corrupt. Please delete cache.py and re-run the script."
        )
    cursorCache = encode(f"user:{users_list[-1]['id']}")
    if len(users_list) == 1:
        print("[INFO] No new users to load.")
        return userCache, botCache, appCache, cursorCache
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
            if user["profile"].get("api_app_id"):
                # appCache[user["profile"]["bot_id"]] = user["profile"]["api_app_id"]
                appCache[user["profile"]["api_app_id"]] = user["profile"]["bot_id"]
            else:
                print(f'[WARN] Bot ID {user["profile"]["bot_id"]} has no app ID!')
    return userCache, botCache, appCache, cursorCache


def __innerMessageParser(message: dict) -> dict:
    try:
        if not message.get("user") and message.get("bot_id"):  # Apps sometimes don't...
            bot_id = message["bot_id"]
            if botMappings.get(bot_id):
                message["user"] = botMappings[bot_id]
            elif appMappings.get(bot_id):
                if appMappings.get(appMappings[bot_id]):
                    message["user"] = botMappings[appMappings[appMappings[bot_id]]]
                else:
                    print(
                        f"""[WARN] Unknown bot {bot_id}!
[WARN] Cache may be out of date!"""
                    )
                    message["user"] = f"{bot_id}|UNKNOWN BOT"
            else:
                try:
                    print(
                        f"[INFO] Querying slack for info about unknown bot {bot_id}..."
                    )
                    bot = client.bots_info(bot=bot_id)["bot"]
                    appMappings[bot_id] = bot["app_id"]
                    print("[INFO] Writing new app mapping to cache file...")
                    __writeCache(userMappings, botMappings, appMappings, cursor)
                    print("[INFO] Mapping cached.")
                    if appMappings.get(appMappings[bot_id]):
                        message["user"] = botMappings[appMappings[appMappings[bot_id]]]
                    else:
                        print(
                            f"""[WARN] Unknown bot {bot_id}!
[WARN] Cache may be out of date!"""
                        )
                        message["user"] = f"{bot_id}|UNKNOWN BOT"
                except SlackApiError:
                    print("[WARN] Exception")
                    for line in format_exc().split("\n")[:-1]:
                        print(f"[WARN] {line}")

    except Exception:  # pylint: disable=broad-exception-caught
        # ^ I don't know how I got here, I want to log it so it can be fixed
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
    for i, message in enumerate(messages):
        message = __innerMessageParser(message)
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
    if len(messages) > 0:
        return messages[0]["ts"]
    print("[MSGS] No messages exist in this channel.")
    return ""


def message_channel() -> NoReturn:
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
                oldest_ts = buildMessages(res["messages"])
                del res
            except SlackApiError:
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
                        except SlackApiError:
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
                            except SlackApiError:
                                print("[WARN] Exception:")
                                for line in format_exc().split("\n")[:-1]:
                                    print(f"[WARN] {line}")
                                break
                    except KeyboardInterrupt:
                        print()
                if ts:
                    try:
                        print(
                            f"[INFO] Trying to load messages since {oldest_ts if oldest_ts else 'The Very Beginning'}..."
                        )
                        res = client.conversations_history(
                            channel=chan, inclusive=True, limit=200, oldest=oldest_ts
                        )
                        if len(res["messages"]) > 1:
                            buildMessages(res["messages"][:-1])
                            oldest_ts = res["messages"][0]["ts"]
                        elif len(res["messages"]) > 0 and oldest_ts == "":
                            buildMessages(res["messages"])
                            oldest_ts = res["messages"][0]["ts"]
                        else:
                            print("[INFO] No new messages")
                        del res
                    except SlackApiError:
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
                    except SlackApiError:
                        print("[WARN] Exception")
                        for line in format_exc().split("\n")[:-1]:
                            print(f"[WARN] {line}")
                        print(
                            "[HELP] Does the bot have access to the channel you're trying to see?"
                        )
                except SlackApiError:
                    print("[WARN] Exception:")
                    for line in format_exc().split("\n")[:-1]:
                        print(f"[WARN] {line}")
                    break
        except KeyboardInterrupt:
            print()
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def invite_channel() -> NoReturn:
    while 1:
        channel_id = input("Channel ID")
        print("[INFO] ^C to change channel")
        try:
            while 1:
                user_id_or_ids = input("User ID (or IDs, comma-seperated) to invite")
                try:
                    client.conversations_invite(
                        channel=channel_id, users=user_id_or_ids
                    )
                    print("[INFO] User(s) invited successfully!")
                except SlackApiError:
                    print("[WARN] Exception:")
                    for line in format_exc().split("\n")[:-1]:
                        print(f"[WARN] {line}")
        except KeyboardInterrupt:
            print()
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def create_channel() -> NoReturn:
    while 1:
        channel_name = input("Channel name")
        is_private = input("Should this be a private channel? (y|N)").startswith("y")
        try:
            channel = client.conversations_create(
                name=channel_name, is_private=is_private
            )
            print(
                f"[INFO] Channel created successfully! Channel ID: {channel['channel']['id']}"
            )
        except SlackApiError:
            print("[WARN] Exception:")
            for line in format_exc().split("\n")[:-1]:
                print(f"[WARN] {line}")
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def join_channel() -> NoReturn:
    while 1:
        channel_id = input("Channel ID")
        try:
            client.conversations_join(channel=channel_id)
            print("[INFO] Joined channel successfully!")
        except SlackApiError:
            print("[WARN] Exception:")
            for line in format_exc().split("\n")[:-1]:
                print(f"[WARN] {line}")
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def list_channel() -> NoReturn:
    while 1:
        kind = fp.menu(
            {
                "Public channels": "public_channel",
                "Private channels": "private_channel",
                "Group message": "mpim",
                "Direct message": "im",
                "Cancel": "",
            },
            "Please select what type of channels you would like to list",
        )
        if not kind:
            raise KeyboardInterrupt()
        cursor = "N/A"
        while cursor:
            try:
                if cursor == "N/A":
                    data = client.conversations_list(types=kind, limit=usable_rows(3))
                else:
                    data = client.conversations_list(
                        types=kind, limit=usable_rows(3), cursor=cursor
                    )
                channels, cursor = (
                    data["channels"],
                    data["response_metadata"]["next_cursor"],
                )
                print("[INFO] | Archived | Channel  ID |   Creator   | Channel Name")
                for channel in channels:
                    if kind == "im":
                        channel["creator"] = "   N/A   "
                        channel["name"] = "Private Message"
                    cLen = len(channel["id"])
                    if cLen == 9:
                        c = "  "
                    elif cLen == 11:
                        c = " "
                    elif cLen == 13:
                        c = ""
                    elif cLen >= 15:
                        c = ""
                        print(
                            "[WARN] Channel ID too long! Need a mapping for a channel ID length of {cLen}!"
                        )
                    uLen = len(channel["creator"])
                    if uLen == 9:
                        u = "  "
                    elif uLen == 11:
                        u = " "
                    elif uLen == 13:
                        u = ""
                    elif uLen >= 15:
                        u = ""
                        print(
                            "[WARN] User ID too long! Need a mapping for a user ID length of {uLen}!"
                        )
                    print(
                        f"[CHAN] |   {'YES' if channel['is_archived'] else 'NO '}    |{c+channel['id']+c}|{u+channel['creator']+u}| #{channel['name']}"
                    )
                if cursor:
                    print("[INFO] More channels available. View them? (Y|n)")
                    if input().lower().startswith("n"):
                        break
                else:
                    input("Pausing until input recieved (press ENTER)")
            except SlackApiError:
                print("[WARN] Exception:")
                for line in format_exc().split("\n")[:-1]:
                    print(f"[WARN] {line}")
                print("[INFO] Sleeping for 5 seconds")
                sleep(5)
                break
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def archive_channel() -> NoReturn:
    while 1:
        channel_id = input("Channel ID")
        try:
            client.conversations_archive(channel=channel_id)
            print("[INFO] Archived channel successfully!")
        except SlackApiError:
            print("[WARN] Exception:")
            for line in format_exc().split("\n")[
                :-1
            ]:  # pylint: disable=redefined-outer-name
                print(f"[WARN] {line}")
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def unarchive_channel() -> NoReturn:
    while 1:
        channel_id = input("Channel ID")
        try:
            client.conversations_unarchive(channel=channel_id)
            print("[INFO] Unarchived channel successfully!")
        except SlackApiError:
            print("[WARN] Exception:")
            for line in format_exc().split("\n")[
                :-1
            ]:  # pylint: disable=redefined-outer-name
                print(f"[WARN] {line}")
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


def rename_channel() -> NoReturn:
    while 1:
        channel_id = input("Channel ID")
        name = input("New name of channel")
        try:
            client.conversations_rename(channel=channel_id, name=name)
            print("[INFO] Channel renamed successfully!")
        except SlackApiError:
            print("[WARN] Exception:")
            for line in format_exc().split("\n")[
                :-1
            ]:  # pylint: disable=redefined-outer-name
                print(f"[WARN] {line}")
    # The below code will never run, but linters are dumb and need to be assured there is no possible return from a `NoReturn` function.
    exit(1)


userMappings = {}
botMappings = {}
appMappings = {}
cursor = "N/A"
try:
    if "--no-cache" in argv:
        print("[INFO] Skipping cache on user request")
        raise ImportError("User requested to skip cache")
    print("[INFO] Trying to load user, bot, and app mappings from cache...")
    from cache import userMappings, cursorCache, botMappings, appMappings

    print(
        """[INFO] Cache load OK.
[INFO] Reminder: If you need to regenerate the cache, call the script with `--no-cache`"""
    )
    print("[INFO] Checking for slack users newer than my cache...")
    userMappings, botMappings, appMappings, cursor = __generateCache(
        userMappings, botMappings, appMappings, cursorCache
    )
    if cursor != cursorCache:
        print(
            "[INFO] New user, bot, and app mappings generated, writing cache file now..."
        )
        __writeCache(userMappings, botMappings, appMappings, cursor)
except ImportError:
    print("[WARN] Cache load failed, falling back to full load from slack...")
    userMappings, botMappings, appMappings, cursor = __generateCache()
    print("[INFO] All user, bot, and app mappings generated, writing cache file now...")
    __writeCache(userMappings, botMappings, appMappings, cursor)

print("[INFO] User mappings loaded. User count:", len(userMappings))
print("[INFO] Bot  mappings loaded. Bot  count:", len(botMappings))
print("[INFO] Bot  mappings loaded. App  count:", len(appMappings))

cmdMap: dict[str, Callable[[], NoReturn]] = {
    "Message channels": message_channel,
    "Invite user(s) to channels": invite_channel,
    "Create channels": create_channel,
    "Join (public) channels": join_channel,
    "List channels (or DMs)": list_channel,
    "Archive channels": archive_channel,
    "Unarchive channels": unarchive_channel,
    "Rename channels": rename_channel,
    "Exit Program": exit,
}

try:
    while 1:
        print("[INFO] Sleeping for 5 seconds")
        sleep(5)
        print("[INFO] ^D at any time to terminate program")
        cmd = fp.menu(cmdMap, "Please select an operation")
        if cmd != exit:  # pylint: disable=comparison-with-callable
            print("[INFO] ^C to change mode")
        try:
            cmd()
        except KeyboardInterrupt:
            print()
        except EOFError:
            print()
            exit()
        except Exception:  # pylint: disable=broad-exception-caught
            # ^ I don't know what an internal function might throw, and I want to log it so it can be fixed
            print("[WARN] The command you were running threw an unhandled exception!")
            for line in format_exc().split("\n")[:-1]:
                print(f"[WARN] {line}")
except EOFError:
    print()
    exit()
