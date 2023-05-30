import json


# dedupe msg_storage
def dedupe():
    with open("../message_storage.json", "r") as f:
        msg_storage = json.load(f)

    msg_storage = sorted(msg_storage, key=lambda x: x["date"])
    msg_storage = [msg_storage[0]] + [msg for i, msg in enumerate(msg_storage[1:]) if
                                      msg["chat_link"] != msg_storage[i]["chat_link"]]
    with open("msg_storage.json", "w") as f:
        json.dump(msg_storage, f)


if __name__ == '__main__':
    dedupe()
