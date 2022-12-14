print("Starting chatting.py")
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os
import traceback
import logging
from ipcqueue import sysvmq
from flask import Flask

app = Flask(__name__)
app.logger.root.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL') or 'DEBUG'))
app.logger.info("Logger started")

class chatting:
    def __init__(self, chats_home):
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-large")
        self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-large")
        self.chats_home = chats_home

    def _chatfile(self, id: int):
        return os.path.join(self.chats_home, f"chat_{id}.pt")

    def _history(self, id: int, contents: str):
        chatfile = self._chatfile(id)
        user_input = self.tokenizer.encode(contents + self.tokenizer.eos_token, return_tensors="pt")
        if os.path.exists(chatfile):
            return torch.cat([torch.load(chatfile), user_input], dim=-1)
        else:
            return user_input

    def reply(self, id: int, contents: str):
        chatbot_input = self._history(id, contents)
        # print(f"Got history = {chatbot_input}")

        # generate a response
        chat_history = self.model.generate(
            chatbot_input,
            max_length=1000,
            do_sample=True,
            top_k=70,
            top_p=0.95,
            temperature=0.7,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        # print(f"Got new history = {chat_history}, saving...")

        torch.save(chat_history, self._chatfile(id))

        # print(f"Responding")

        return self.tokenizer.decode(chat_history[:, chatbot_input.shape[-1]:][0], skip_special_tokens=True)

def run():
    app.logger.info("Starting chatbot...")
    chatbot = chatting(os.getenv('CHATS_HOME'))
    while True:
        try:
            chatbot_queue_req = sysvmq.Queue(1022)
            chatbot_queue_rep = sysvmq.Queue(1023)
            app.logger.info("Waiting for messages")
            while True:
                try:
                    queue_msg = chatbot_queue_req.get()
                    msg_author = queue_msg[0]
                    app.logger.debug(f"Received msg from {msg_author}")
                    response = chatbot.reply(msg_author, queue_msg[1])
                    app.logger.debug(f"Responding {msg_author} with '{response}'")
                    chatbot_queue_rep.put(response, msg_type=msg_author)
                except KeyboardInterrupt:
                    app.logger.info("\nClean exit")
                    exit(0)
                except sysvmq.QueueError:
                    app.logger.debug("Recreating queues!")
                    break
                except Exception as e:
                    app.logger.error(f"Exception! {e}")
                    app.logger.debug(traceback.format_exc())
                    pass
        except sysvmq.QueueError:
            app.logger.debug("Recreating queues!")

run()
