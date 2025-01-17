#!/bin/bash

# Copy config.py.example to config.py
if [ -f config.py.example ]; then
  cp config.py.example config.py
  echo "config.py.example copied to config.py"
fi

# Copy system_instruction.txt.example to system_instruction.txt
if [ -f system_instruction.txt.example ]; then
  cp system_instruction.txt.example system_instruction.txt
  echo "system_instruction.txt.example copied to system_instruction.txt"
fi

# Add copy logic for additional .example files here. 