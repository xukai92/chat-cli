# Chat CLI

**Prerequsite**: Copy `chat-cli.toml` to `~/.chat-cli.toml` or `~/.config/chat-cli.toml` and update `api_key` in the file

## Usage

Command line interface

```sh
❯ python chat.py --help
```

```
Usage: chat.py [OPTIONS]

Options:
  -c, --context TEXT      Name of system context in config file
  -s, --session FILENAME  Filepath of a dialog session file
  --help                  Show this message and exit.
```

Start chatting

```sh
❯ python chat.py
```

```
╭────────────────────────────── system ──────────────────────────────╮
│ Welcome to ChatGPT CLI (type /h for help)                          │
╰────────────────────────────────────────────────────────────────────╯
```

Commands in chat
```
>>> /h                                                 [0][S][default]
```

```
╭────────────────────────────── system ──────────────────────────────╮
│ Help / TL;DR                                                       │
│                                                                    │
│  • /q: quit                                                        │
│  • /h: show help                                                   │
│  • /a model: amend assistant                                       │
│  • /m: toggle multiline (for the next session only)                │
│  • /M: toggle multiline                                            │
│  • /n: new session                                                 │
│  • /N: new session (ignoring loaded)                               │
│  • /d [1]: display previous response                               │
│  • /p [1]: previous response in plain text                         │
│  • /md [1]: previous response in Markdown                          │
│  • /s filepath: save current session to filepath                   │
│  • /l filepath: load filepath and start a new session              │
│  • /L filepath: load filepath (permanently) and start a new        │
│    session                                                         │
╰────────────────────────────────────────────────────────────────────╯
```

## Acknowledgements

- Heavily inspired by https://github.com/marcolardera/chatgpt-cli
- Tested by Pinzhen and Bing
