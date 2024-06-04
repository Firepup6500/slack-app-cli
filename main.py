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

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

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
                            for i in range(len(messages)):
                                texts[f'{messages[i]["text"]} ({messages[i]["ts"]})'] = i
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
