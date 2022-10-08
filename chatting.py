print("Starting chatting.py")
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os

from ipcqueue import sysvmq

class chatting:
    def __init__(self, chats_home):
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-large")
        self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-large")
        self.chats_home = chats_home

    def _chatfile(self, id: int):
        return os.join(self.chats_home, f"chat_{id}.pt")

    def _history(self, id: int, contents: str):
        chatfile = self._chatfile(id)
        if os.path.exists(chatfile):
            return torch.cat([torch.load(chatfile), contents], dim=-1)
        else:
            return contents

    def reply(self, id: int, contents: str):
        chatbot_input = self._history(id, contents)

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

        torch.save(chat_history, self._chatfile(id))

        return self.tokenizer.decode(chat_history[:, chatbot_input.shape[-1]:][0], skip_special_tokens=True)

if __name__ == "__main__":
    print("Starting chatbot...")
    chatbot = chatting(os.getenv('CHATS_HOME'))
    chatbot_queue_req = sysvmq.Queue(abs(hash('/bottochats_req') % 1024))
    chatbot_queue_rep = sysvmq.Queue(abs(hash('/bottochats_rep') % 1024))
    print("Waiting for messages")
    while True:
        try:
            queue_msg = chatbot_queue_req.get()
            msg_author = queue_msg[0]
            print(f"Received msg from {msg_author}")
            response = chatbot.reply(msg_author, queue_msg[1])
            print(f"Responding {msg_author} with '{response}'")
            chatbot_queue_rep.put([msg_author, response])
        except KeyboardInterrupt:
            print("Clean exit\n")
            exit(0)
        except:
            pass