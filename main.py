import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import firepup650 as fp

input = fp.replitInput

fp.replitCursor = fp.bcolors.REPLIT + ">>>" + fp.bcolors.RESET

load_dotenv()

print(dir(fp))

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

# Start your app
if __name__ == "__main__":
    while 1:
        chan = input("Channel")
        try:
            print("^C to change channel")
            while 1:
                thread = input("Reply to a thread?").lower().startswith("y")
                ts = None
                if thread:
                    hasID = input("Do you have the TS ID?").lower().startswith("y")
                    if not hasID:
                        try:
                            res = client.conversations_history(
                                channel=chan, inclusive=True, limit=1
                            )
                            found = res["messages"][0]
                            print(found)
                            ts = found["ts"]
                        except Exception as E:
                            print(f"Exception: {E}")
                    else:
                        ts = input("TS ID")
                    print("^C to change thread/channel")
                    while 1:
                        msg = input("Message")
                        try:
                            print(
                                client.chat_postMessage(
                                    channel=chan, text=msg, thread_ts=ts
                                )
                            )
                        except Exception as E:
                            print(f"Exception: {E}")
                msg = input("Message")
                try:
                    print(client.chat_postMessage(channel=chan, text=msg))
                except Exception as E:
                    print(f"Exception: {E}")
        except KeyboardInterrupt:
            print()
