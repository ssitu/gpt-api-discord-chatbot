import yaml
import requests

CONFIG_FILE = "config.yaml"

class Config:

    def __init__(self):
        self.config = {}
        self.load_config()
    
    def load_config(self):
        with open(CONFIG_FILE, 'r') as f:
            try:
                self.config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(e)

    def type_check(self, key, expected_type, default=None):
        # Check the type of the value of the key in the config file
        # If the key is not of the expected type or if the key is not in the config file, return the default value
        value = self.config.get(key, default)
        if not isinstance(value, expected_type):
            return default
        return value

    def is_bot(self):
        return self.type_check("is_bot", bool, False)

    def get_openai_api_key(self):
        api_key = self.type_check("openai_api_key", str, "")
        # Test if the key is valid
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        response = requests.post("https://api.openai.com/v1/embeddings", headers=headers)
        if response.status_code == 401:
            raise Exception("OpenAI API key is invalid. Please check your config.yaml file.")
        return api_key

    def get_discord_api_key(self):
        api_key = self.type_check("discord_api_key", str, "")
        # Test if the key is valid
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"{'Bot ' if self.is_bot() else ''}{api_key}"
        }
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        if response.status_code == 401:
            raise Exception("Discord API key is invalid. Please check your config.yaml file.")
        return api_key

    def get_embed_hyperlinks(self):
        return self.type_check("hyperlinks", list, [])

    def get_gpt_prompt(self):
        return self.type_check("gpt_prompt", str, "")

    def get_channel_id(self):
        id =  self.type_check("channel_id", str, "")
        if not id:
            raise Exception("Channel ID is not specified. Please check your config.yaml file.")
        return id

    def get_convert_messages_to_lowercase(self):
        return self.type_check("convert_messages_to_lowercase", bool, False)

    def get_mention_triggers(self):
        return self.type_check("mention_triggers", list, [])

    def get_text_triggers(self):
        return self.type_check("text_triggers", list, [])
    
    def get_reaction_triggers(self):
        reaction_dict = self.type_check("reaction_triggers", dict, {})
        new_reaction_dict = {}
        for emoji_code in reaction_dict:
            emoji = chr(int(emoji_code[2:], 16))
            new_reaction_dict[emoji] = reaction_dict[emoji_code]
        return new_reaction_dict

    def get_reply_blacklist(self):
        return self.type_check("reply_blacklist", list, [])

    def get_reply_to_self(self):
        return self.type_check("reply_to_self", bool, False)
    
    def get_ids_to_names(self):
        return self.type_check("ids_to_names", dict, {})

    def get_messages_request_timeout(self):
        return self.type_check("messages_request_timeout", int, 60)

    def get_messages_request_timeout_dev(self):
        return self.type_check("messages_request_timeout_dev", int, 10)

    def get_between_messages_timeout(self):
        return self.type_check("between_messages_timeout", int, 10)

    def get_between_messages_timeout_dev(self):
        return self.type_check("between_messages_timeout_dev", int, 5)

    def get_gpt_request_timeout(self):
        return self.type_check("gpt_timeout", int, 60)

    def get_gpt_request_timeout_dev(self):
        return self.type_check("gpt_timeout_dev", int, 10)

    def get_gpt_logit_bias(self):
        return self.type_check("gpt_logit_bias", dict, {})

    def get_emojis(self):
        emoji_codes = self.config.get("emojis", [])
        emoji_codes = emoji_codes if emoji_codes else []
        emojis = []
        try:
            for emoji_code in emoji_codes:
                unicode_char = chr(int(emoji_code[2:], 16))
                emojis.append(unicode_char)
        except ValueError:
            raise Exception('Invalid hex code. Please check your config.yaml file for the "emojis" field.')
        return emojis

    def get_react_probability(self):
        return self.type_check("react_probability", float, 0.1)

    def get_reply_to_images(self):
        return self.type_check("reply_to_images", bool, False)

if __name__ == "__main__":
    config = Config()
    print(config.get_emojis())