#!/bin/bash

echo -ne "\\033[2J\033[3;1f"
eval "cat ~/astra/assets/banner.txt"
printf "\n\n\033[1;32mastra is running!\033[0m"
