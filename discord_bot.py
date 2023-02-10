import requests
import json
import time
import socket
import numpy as np
import base64
import queue
import random
import re
import datetime
from config import Config

time_rng = np.random.RandomState()
emoji_rng = np.random.RandomState()
MESSAGE_HISTORY_LIMIT = 5

config = Config()
discord_url = "https://discord.com/api/v9"
discord_headers = {
    "Content-Type": "application/json",
    "Authorization": f"{'Bot ' if config.is_bot() else ''}{config.get_discord_api_key()}"
}

def get_datetime_est():
    return datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

def send_message(message, channel_id, reply_to_id=None):
    hyperlinks = config.get_embed_hyperlinks()
    hyperlink = random.choice(hyperlinks)
    data = {}
    if config.is_bot():
        data["embed"] = {"description": f"[{message}]({hyperlink})"}
    else:
        data["content"] = message
    if reply_to_id:
        data["message_reference"] = {
            "channel_id": channel_id,
            "message_id": reply_to_id
        }
    response = requests.post(f"{discord_url}/channels/{channel_id}/messages", headers=discord_headers, data=json.dumps(data))
    return response.json()

def get_messages(channel_id, before_id=None, limit=None):
    url = discord_url + f"/channels/{channel_id}/messages"
    if before_id:
        url += "?before=" + before_id
    if limit:
        url += "?limit=" + str(limit)
    response = requests.get(url, headers=discord_headers)
    if response.status_code == 200:
        json_messages = json.loads(response.text)
        return json_messages
    else:
        print(response)
        try:
            print(response.json())
        except json.decoder.JSONDecodeError:
            print(response.text)
            
def set_reaction(channel_id, message_id=None, emoji="👍"):
    if not message_id:
        raise Exception("No message id provided")
    url = discord_url + f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
    response = requests.put(url, headers=discord_headers)
    if response.status_code == 204:
        return True
    if response.status_code == 400:
        print(emoji, response.json())
    return False

def timeout_std(timeout, std):
    return timeout + time_rng.randint(-std, std)

def imageurl_to_base64(url):
    return base64.b64encode(requests.get(url).content)

def get_caption_response(base64_image):
    import requests
    def base64_url(base64_image): return f"data:image/png;base64,{base64_image.decode()}"
    def base64_post(url, base64_image): return requests.post(url, json={"data": [base64_url(base64_image)]}).json()["data"]
    caption_list = base64_post("https://nielsr-comparing-captioning-models.hf.space/run/predict", base64_image) # List of captions from different models
    # caption_list += base64_post("https://zayn-image-captioning-using-vision-tr-55b6d7a.hf.space/api/predict", base64_image) # List of a single caption from a different model
    # caption_list.append(requests.post("https://fffiloni-clip-interrogator-2.hf.space/run/clipi2", json={"data": [base64_url(base64_image), "best", 4]}).json()["data"][0]) # CLIP Interrogator
    return caption_list

def discord_prompt(message, attachments_str):
    prompt = \
        f"{config.get_gpt_prompt()}\n" + \
        f"Message:{message}\n" + \
        f"Image Alternative Text:{attachments_str}\n" + \
        f"Reply:"
    return prompt

def images_urls_to_str(images_urls):
    if images_urls:
        image_strings = []
        for i, image_url in enumerate(images_urls):
            base64_image = imageurl_to_base64(image_url)
            captions = get_caption_response(base64_image)
            for j, caption in enumerate(captions):
                captions[j] = remove_duplicate_substrings(caption, " ")
            caption_str = ";".join(captions)
            # caption_str = captions
            image_string = f"<image{i+1}_alt_text:{caption_str}>"
            image_strings.append(image_string)
        attachments_str = ", ".join(image_strings)
        return attachments_str
    else:
        return "None"

def parse_attachments(attachments):
    parsed = {"images": []}
    for attachment in attachments:
        image_types = ["png", "jpeg"]
        is_image = False
        for image_type in image_types:
            if image_type in attachment["content_type"]:
                is_image = True
                break
        if is_image:
            parsed["images"].append(attachment["url"])
    return parsed

def remove_duplicate_substrings(string, separator):
    return separator.join(dict.fromkeys(string.split(separator)))

def get_gpt_response(prompt, max_tokens=500, temperature=0.7, top_p=1, frequency_penalty=0.0, presence_penalty=0.0, stop="", n=1, logit_bias=None):
    gpt_url = "https://api.openai.com/v1/completions"
    gpt_key = config.get_openai_api_key()
    gpt_headers = {"Content-Type": "application/json","Authorization": f"Bearer {gpt_key}"}
    data = {
        "model": "text-davinci-003",
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "stop": stop,
        "n": n,
        "stream": False,
        "logprobs": None,
        "logit_bias": logit_bias
    }
    print("Prompt:")
    print(prompt)
    response = requests.post(gpt_url, headers=gpt_headers, json=data)
    status_code = 0
    while status_code != 200:
        response = requests.post(gpt_url, headers=gpt_headers, json=data)
        status_code = response.status_code
        if response.status_code == 200:
            response = response.json()
            text = response["choices"][0]["text"]
            return text
        else:
            print(response.json())
            gpt_sleep_time = timeout_std(config.get_gpt_request_timeout(), config.get_gpt_request_timeout_dev())
            print(f"{get_datetime_est()}: (GPT loop) Sleeping for {gpt_sleep_time} seconds...")
            time.sleep(gpt_sleep_time)
    return response.json()

def get_gpt_discord_response(discord_message, images_urls=None):
    logit_bias = config.get_gpt_logit_bias()
    return get_gpt_response(discord_prompt(discord_message, images_urls_to_str(images_urls)), max_tokens=500, temperature=0.8, logit_bias=logit_bias)

# Convert emoticons produced by GPT to Discord emojis
EMOJI_TO_DISCORD = {
    ":)": ":slight_smile:",
    ":(": ":frowning:",
    ":D": ":smile:",
    ":P": ":stuck_out_tongue:",
    ":O": ":open_mouth:",
    ":|": ":neutral_face:",
    ":*": ":kissing:",
    ":'(": ":cry:",
    ":')": ":smiling_face_with_tear:",
    ";)": ":wink:",
}

if __name__ == "__main__":
    message_id_history = queue.deque(maxlen=MESSAGE_HISTORY_LIMIT)
    while True:
        try:
            last_id = None
            messages = get_messages(channel_id=config.get_channel_id(), before_id=last_id, limit=MESSAGE_HISTORY_LIMIT)
            already_replied_set = set()
            for message in messages:
                # React to random messages based on message ID
                emoji_rng.seed(int(message["id"][10:]))
                random_float = emoji_rng.random()
                
                is_message_new = message["id"] not in message_id_history
                if random_float < config.get_react_probability() and is_message_new:
                    # Is it already reacted to?
                    reacted = False
                    if "reactions" in message:
                        for reaction in message["reactions"]:
                            if reaction["me"]:
                                reacted = True
                    if not reacted:
                        set_reaction(channel_id=config.get_channel_id(), message_id=message["id"], emoji=emoji_rng.choice(config.get_emojis()))

                message_for_triggers = message["content"].lower() if config.get_convert_messages_to_lowercase() else message["content"]

                # Did the message contain any of the text triggers?
                text_triggers = config.get_text_triggers()
                passed_filter = any(filter in message_for_triggers for filter in text_triggers)

                # Did the message mention any of the users in the mention triggers?
                mention_triggers = config.get_mention_triggers()
                mentioned = False
                for mention in message["mentions"]:
                    if mention["id"] in mention_triggers:
                        mentioned = True

                # Is the message already replied to by one of the users in the reply blacklist?
                reply_blacklist = config.get_reply_blacklist()
                if message["author"]["id"] in reply_blacklist and "referenced_message" in message and message["referenced_message"] is not None:
                    mentioned_message_id = message["referenced_message"]["id"]
                    already_replied_set.add(mentioned_message_id)
                already_replied = message["id"] in already_replied_set

                # Is there an image attached?
                parsed = parse_attachments(message["attachments"])
                images_urls = parsed["images"]
                image_attached = len(images_urls) > 0

                # Is the message by this user?
                message_by_user = message["author"]["id"] in config.get_mention_triggers()

                # Is the message by this user already replied to by this user?
                is_reply = "referenced_message" in message and message["referenced_message"] is not None
                referenced_message_by_user = is_reply and "author" in message["referenced_message"] and message["referenced_message"]["author"]["id"] in config.get_mention_triggers()
                self_replied = message_by_user and is_reply and referenced_message_by_user
                self_mentioned = message_by_user and mentioned
                
                # Condition 1: The user is mentioned (replied to) or a trigger word is used (filter)
                cond_user_mentioned = passed_filter or mentioned
                # Condition 2: There is an image attached and the message is not by this user
                cond_image_attached = (image_attached and not message_by_user) and config.get_reply_to_images()
                # Condition 3: The message is not already replied to by this user. Prevents replying to messages that the bot already replied to.
                cond_not_replied_yet = not already_replied
                # Condition 4: The message isn't by this user as a reply to another message by this user. Prevents replying to itself, prone to repeatedly replying to itself.
                cond_not_self_reply = not self_replied and not self_mentioned or config.get_reply_to_self()

                should_reply = (cond_user_mentioned or cond_image_attached) and cond_not_replied_yet and cond_not_self_reply
                
                if should_reply:
                    discord_message = message["content"]
                    print("Message:" + discord_message)

                    # Remove mentions from message to their names
                    id_to_nicknames = config.get_ids_to_names()
                    for id, nickname in id_to_nicknames.items():
                        discord_message = discord_message.replace(f"@{id}", f"@{nickname}")

                    # Remove @NNN...N and also the space after it if there is one
                    discord_message = re.sub(r"@\d+ ?", "", discord_message)

                    gpt_response = get_gpt_discord_response(discord_message, images_urls).strip()
                    print("GPT Response:" + gpt_response)
                    # Replace emoji codes with emoji
                    for emoji_code, emoji in EMOJI_TO_DISCORD.items():
                        gpt_response = gpt_response.replace(emoji_code, emoji)
                    # Send message
                    response = send_message(gpt_response, channel_id=config.get_channel_id(), reply_to_id=message["id"])
                    # print(response)
                    last_id = message["id"]

                message_id_history.append(message["id"])
                # Sleep for 10 seconds to avoid rate limiting
                between_messages_sleep_time = timeout_std(config.get_between_messages_timeout(), config.get_between_messages_timeout_dev())
                # print(f"{get_datetime_est()}: (Message loop) Sleeping for {between_messages_sleep_time} seconds...")
                time.sleep(between_messages_sleep_time)
        except socket.error as e:
            print("Error:")
            print(e)
        sleep_time = timeout_std(config.get_messages_request_timeout(), config.get_messages_request_timeout_dev())
        print(f"{get_datetime_est()}: (Main loop) Sleeping for {sleep_time} seconds...")
        time.sleep(sleep_time)