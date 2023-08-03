#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Chat
# @raycast.mode silent

# Optional parameters:
# @raycast.icon 🤖
# @raycast.argument1 { "type": "text", "placeholder": "query", "optional": true}
# @raycast.packageName Chat CLI

# Documentation:
# @raycast.description Chat in Terminal
# @raycast.author Kai Xu
# @raycast.authorURL xuk.ai

wezterm --config "font_size=20" start $HOME/bin/chat "$1"
