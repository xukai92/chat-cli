#!/usr/bin/env python

import os
import sys
import time
import toml

import openai

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

import click

import json

import atexit

from util import num_tokens_from_messages, calculate_expense


HELP_MD = """
Help / TL;DR
- `/q`: **q**uit
- `/h`: show **h**elp
- `/a assistant`: **a**mend **a**ssistant
- `/c context`: **c**hange **c**ontext
- `/m`: toggle **m**ultiline (for the next session only)
- `/M`: toggle **m**ultiline
- `/n`: **n**ew session
- `/N`: **n**ew session (ignoring loaded)
- `/d [1]`: **d**isplay previous response
- `/p [1]`: previous response in **p**lain text
- `/md [1]`: previous response in **M**ark**d**own
- `/s filepath`: **s**ave current session to `filepath`
- `/l filepath`: **l**oad `filepath` and start a new session
- `/L filepath`: **l**oad `filepath` (permanently) and start a new session
"""

CONFIG_FILENAME = "chat-cli.toml"
CONTEXTS = None

CONFIG_FILEPATHS = [
    os.path.expanduser(f"~/.{CONFIG_FILENAME}"),
    os.path.expanduser(f"~/.config/{CONFIG_FILENAME}"),
]

PROMPT_HISTORY_FILEPATH = os.path.expanduser("~/.local/chat-cli.history")

PRICING_RATE = {
    "gpt-3.5-turbo":     {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-16k": {"prompt": 0.003,  "completion": 0.004},
    "gpt-4":             {"prompt": 0.03,   "completion": 0.06},
    "gpt-4-32k":         {"prompt": 0.06,   "completion": 0.12},
}

PROMPT_PREFIX = ">>> "

# TODO Autosave chat history
class ConsoleChatBot():

    def __init__(self, model, vi_mode=False, prompt=True, vertical_overflow="ellipsis", loaded={}):
        
        self.model = model
        self.vi_mode = vi_mode
        self.vertical_overflow = vertical_overflow
        self.loaded = loaded

        self.console = Console()
        self.input = PromptSession(history=FileHistory(PROMPT_HISTORY_FILEPATH)) if prompt else None
        self.multiline = False
        self.multiline_mode = 0

        self.info = {}
        self._reset_session()

    def _reset_session(self, hard=False):
        if hard:
            self.loaded = {}
        self.info["messages"] = [] if hard or ("messages" not in self.loaded) else [*self.loaded["messages"]]
        self.info["tokens"] = {"user": 0, "assistant": 0}

    def _sys_print(self, *args, **kwargs):
        self.console.print(Panel(*args, title="system", **kwargs))

    def greet(self, help=False, new=False, session_name="new session"):
        side_info_str = (" (type `/h` for help)" if help else "") + (f" ({session_name})" if new else "")
        self._sys_print(Markdown(f"Welcome to Chat CLI w/ **{self.model.upper()}**" + side_info_str))

    def display_expense(self):
        total_expense = calculate_expense(
            self.info["tokens"]["user"],
            self.info["tokens"]["assistant"],
            PRICING_RATE[self.model]["prompt"],
            PRICING_RATE[self.model]["completion"],
        )
        self._sys_print(
            f"Total tokens used: [green bold]{self._total_tokens}[/green bold]\n"
            f"Estimated expense: [green bold]${total_expense}[/green bold]",
        )

    @property
    def _total_tokens(self): return self.info["tokens"]["user"] + self.info["tokens"]["assistant"]

    @property
    def _right_prompt(self): return FormattedText([
        ('#85bb65 bold', f"[{self._total_tokens}]"), # dollar green for tokens
        ('#3f7cac bold', f"[{'M' if self.multiline else 'S'}]"), # info blue for multiple
        *([('bold', f"[{self.loaded['name']}]")] if "name" in self.loaded else []), # loaded context/session file
        *([] if openai.proxy is None else [('#d08770 bold', "[proxied]")]), # indicate prox
    ])

    def _handle_quit(self, content):
        raise EOFError

    def _handle_help(self, content):
        self._sys_print(Markdown(HELP_MD))
        raise KeyboardInterrupt

    def _handle_multiline(self, content):
        temp = content == "/m" # soft multilien only for next prompt
        self.multiline = not self.multiline
        self.multiline_mode = 1 if not temp else 2
        raise KeyboardInterrupt
    
    def _handle_amend(self, content):
        self.display_expense()
        cs = content.split()
        if len(cs) < 2:
            self._sys_print(Markdown("**WARNING**: The second argument `assistant` is missing in the `/a assistant` command."))
            raise KeyboardInterrupt
        self.model = cs[1]
        self._reset_session()
        self.greet(new=True)
        raise KeyboardInterrupt
    
    def _handle_context(self, content):
        if CONTEXTS is None:
            self._sys_print(Markdown("**WARNING**: No contexts loaded from the config file."))
            raise KeyboardInterrupt
        self.display_expense()
        cs = content.split()
        if len(cs) < 2:
            self._sys_print(Markdown("**WARNING**: The second argument `context` is missing in the `/c context` command."))
            raise KeyboardInterrupt
        context = cs[1]
        self.loaded["name"] = context
        self.loaded["messages"] = [{"role": "system", "content": CONTEXTS[context]}]
        self._reset_session()
        self.greet(new=True)
        raise KeyboardInterrupt

    def _handle_new_session(self, content):
        hard = content == "/N"  # hard new ignores loaded context/session
        self.display_expense()
        self._reset_session(hard=hard)
        self.greet(new=True)
        raise KeyboardInterrupt

    def __handle_replay(self, content, display_wrapper=(lambda x: x)):
        cs = content.split()
        i = 1 if len(cs) == 1 else int(cs[1]) * 2 - 1
        if len(self.info["messages"]) > i:
            self.console.print(display_wrapper(self.info["messages"][-i]["content"]))
        raise KeyboardInterrupt

    def _handle_display(self, content): 
        return self.__handle_replay(content, display_wrapper=(lambda x: Panel(x)))

    def _handle_plain(self, content): return self.__handle_replay(content)

    def _handle_markdown(self, content):
        return self.__handle_replay(content, display_wrapper=(lambda x: Panel(Markdown(x), subtitle_align="right", subtitle="rendered as Markdown")))

    def _handle_save_session(self, content):
        cs = content.split()
        if len(cs) < 2:
            self._sys_print(Markdown("**WARNING**: The second argument `filepath` is missing in the `/s filepath` command."))
            raise KeyboardInterrupt
        filepath = cs[1]
        with open(filepath, "w") as outfile:
            json.dump(self.info["messages"], outfile, indent=4)
        raise KeyboardInterrupt

    def _handle_load_session(self, content):
        self.display_expense()
        cs = content.split()
        if len(cs) < 2:
            self._sys_print(Markdown("**WARNING**: The second argument `filepath` is missing in the `/l filepath` or `/L filepath` command."))
            raise KeyboardInterrupt
        filepath = cs[1]
        with open(filepath, "r") as session:
            messages = json.loads(session.read())
        if content[:2] == "/L":
            self.loaded["name"] = filepath
            self.loaded["messages"] = messages
            self._reset_session()
            self.greet(new=True)
        else:
            self._reset_session()
            self.info["messages"] = [*messages]
            self.greet(new=True, session_name=filepath)
        raise KeyboardInterrupt

    def _handle_empty():
        raise KeyboardInterrupt

    def _update_conversation(self, content, role):
        assert role in ("user", "assistant")
        message = {"role": role, "content": content}
        self.info["messages"].append(message)
        # If it's user, all history are considered as the prompt
        # If it's assistant, only the recent response is part of completion
        self.info["tokens"][role] += num_tokens_from_messages(
            self.info["messages"] if role == "user" else [message]
        )

    def start_prompt(self, content=None, box=True):
        
        handlers = {
            "/q":      self._handle_quit,
            "/h":      self._handle_help,
            "/a":      self._handle_amend,
            "/c":      self._handle_context,
            "/m":      self._handle_multiline,
            "/n":      self._handle_new_session,
            "/d":      self._handle_display,
            "/p":      self._handle_plain,
            "/md":     self._handle_markdown,
            "/s":      self._handle_save_session,
            "/l":      self._handle_load_session,
        }

        if content is None:
            content = self.input.prompt(PROMPT_PREFIX, rprompt=self._right_prompt, vi_mode=True, multiline=self.multiline)

        # Handle empty
        if content.strip() == "":
            raise KeyboardInterrupt

        # Handle commands
        handler = handlers.get(content.split()[0].lower(), None)
        if handler is not None:
            handler(content)

        # Update message history and token counters
        self._update_conversation(content, "user")

        # Deal with temp multiline
        if self.multiline_mode == 2:
            self.multiline_mode = 0
            self.multiline = not self.multiline

        # Get and parse response
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=self.info["messages"],
                stream=True,
            )
            assert next(response)['choices'][0]['delta']["role"] == "assistant", 'first response should be {"role": "assistant"}'
        except openai.error.AuthenticationError:
            self.console.print("Invalid API Key", style="bold red")
            raise EOFError
        except openai.error.RateLimitError:
            self.console.print("Rate limit or maximum monthly limit exceeded", style="bold red")
            self.info["messages"].pop()
            raise KeyboardInterrupt
        except openai.error.APIConnectionError:
            self.console.print("Connection error, try again...", style="red bold")
            self.info["messages"].pop()
            raise KeyboardInterrupt
        except openai.error.Timeout:
            self.console.print("Connection timed out, try again...", style="red bold")
            self.info["messages"].pop()
            raise KeyboardInterrupt
        except:
            self.console.print("Unknown error", style="bold red")
            raise

        response_content = Text()
        panel = Panel(response_content, title=self.model, subtitle_align="right") if box else response_content
        with Live(panel, console=self.console, refresh_per_second=5, vertical_overflow=self.vertical_overflow) as live:
            start_time = time.time()
            for chunk in response:
                chunk_message = chunk['choices'][0]['delta']
                if 'content' in chunk_message:
                    response_content.append(chunk_message['content'])
                if box:
                    panel.subtitle = f"elapsed {time.time() - start_time:.3f} seconds"

        # Update message history and token counters
        self._update_conversation(response_content.plain, "assistant")

@click.command()
@click.argument(
    "question", nargs=-1, type=click.UNPROCESSED
)
@click.option(
    "-m", "--model", "model", help="Model to use"
)
@click.option(
    "-c", "--context", "context", help="Name of system context in config file", default="default"
)
@click.option(
    "-s", "--session", "session", help="Filepath of a dialog session file", type=click.File("r")
)
@click.option(
    "-qq", "--quick-question", "qq", help="Exist after answering question", is_flag=True
)
def main(question, model, context, session, qq) -> None:
    assert (context is None) or (session is None), "Cannot load context and session in the same time"

    # Load config file
    config = None
    config_filepath = None
    for config_filepath in CONFIG_FILEPATHS:
        file_exists = os.path.isfile(config_filepath)
        if file_exists:
            with open(config_filepath) as file:
                config = toml.load(file)
            break
    if config is None:
        print(f"Config file not found. Please copy {CONFIG_FILENAME} from the repo to any path in {CONFIG_FILEPATHS}.")
        sys.exit(1)

    api_base = config.get("api_base")
    if api_base is not None:
        openai.api_base = api_base
    
    # Read API key
    api_key = os.environ.get("OAI_SECRET_KEY", config.get("api_key"))

    if api_key is None:
        print(f"API key not found. Please set it in the config file ({config_filepath}) or via environment variable `OAI_SECRET_KEY` (higher priority).")
        sys.exit(1)
    if not api_key.startswith("sk-"):
        print('API key incorrect. Please make sure it starts with "sk-".')
        sys.exit(1)

    openai.api_key = api_key

    proxy = config.get("proxy")
    if proxy is not None:
        openai.proxy = {"http": proxy, "https": proxy}

    # Load context/session
    loaded = {}

    # Context config file
    if "contexts" in config:
        global CONTEXTS
        CONTEXTS = config["contexts"]
        if context not in config["contexts"]:
            print(f"Context {context} not found in the config file ({config_filepath}). Using default.")
            context = "default"
        loaded["name"] = context
        loaded["messages"] = [{"role": "system", "content": CONTEXTS[context]}]
    else:
        print(f"No contexts section found in the config file ({config_filepath}). Starting without context.")

    # Session from CLI
    # TODO Print history in session when loaded
    if session is not None:
        loaded["name"] = os.path.basename(session.name).strip(".json")
        loaded["messages"] = json.loads(session.read())

    # Initialize chat bot
    ccb = ConsoleChatBot(config["model"] if model is None else model, 
                         vi_mode=config.get("vi_mode", False),
                         prompt=not qq,
                         vertical_overflow=("visible" if config.get("visible_overflow", False) else "ellipsis"), 
                         loaded=loaded)

    if not qq:
        # Greet
        ccb.greet(help=True)

    # Use the input question to start with
    if len(question) > 0:
        question = ' '.join(question)
        if not qq: print(f"{PROMPT_PREFIX}{question}")
        ccb.start_prompt(question, box=(not qq))

    if not qq:
        # Run the display expense function when exiting the script
        atexit.register(ccb.display_expense)

        # Start chatting
        while True:
            try:
                ccb.start_prompt()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
    else:
        # TODO Autosave session in QQ mode
        pass


if __name__ == "__main__":
    main()
