import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import firepup650 as fp

input = fp.replitInput

fp.replitCursor = fp.bcolors.REPLIT + ">>>" + fp.bcolors.RESET  # Totally not hijacking one of my functions to use ;P

load_dotenv()

for requiredVar in ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]:
    if not os.environ.get(requiredVar):
        raise ValueError(f'Missing required environment variable "{requiredVar}". Please create a .env file in the same directory as this script and define it.')

print("Establishing a connection to slack...")
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

print("Building a list of users, please stand by.")
users_list = []
cursor = "N/A"
pages = 0
while cursor:
    data = ""
    if cursor != "N/A":
        data = client.users_list(cursor=cursor, limit=1000)
    else:
        data = client.users_list(limit=1000)
    cursor = data["response_metadata"]["next_cursor"]
    users_list.extend(data["members"])
    pages += 1
    print(f"Pages of users loaded: {pages}")
print("All pages loaded, generating user mappings now.")
del pages
user_mappings = {}
for user in users_list:
    user_mappings[f"<@{user['id']}>"] = f"<@{user['profile']['display_name']}>" if user["profile"]["display_name"] else f"<@{user['id']}>"

print("User mappings loaded. User count:", len(user_mappings))

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
                    hasID = input("Do you have the TS ID? (y|N))").lower().startswith("y")
                    if not hasID:
                        try:
                            print("Getting the last 50 messages for threading options...")
                            res = client.conversations_history(
                                channel=chan, inclusive=True, limit=50
                            )
                            messages = res["messages"]
                            texts = {}
                            print("Building messages, this might take a little bit...")
                            for i in range(len(messages)):
                                label = f'{messages[i]["text"]} ({messages[i]["ts"]})'
                                for user in user_mappings:
                                    label = label.replace(user, user_mappings[user])
                                texts[label] = i
                            found = messages[fp.menu(texts, "Please select the message to reply to as a thread")]
                            ts = found["ts"]
                        except Exception as E:
                            print(f"Exception: {E}")
                            break
                    else:
                        ts = input("TS ID")
                    print("^C to change/exit thread (^C twice if you want to change channel)")
                    try:
                      while 1:
                        msg = input("[THREAD] Message (Raw text, not blocks)")
                        try:
                            print(
                                client.chat_postMessage(
                                    channel=chan, text=msg, thread_ts=ts
                                )
                            )
                        except Exception as E:
                            print(f"Exception: {E}")
                    except KeyboardInterrupt:
                        print()
                if ts:
                    continue
                msg = input("Message (Raw text, not blocks)")
                try:
                    print(client.chat_postMessage(channel=chan, text=msg))
                except Exception as E:
                    print(f"Exception: {E}")
        except KeyboardInterrupt:
            print()
