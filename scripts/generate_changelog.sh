#!/bin/bash
git log --oneline | while read -r cid msg; do
  echo "* [$msg](https://github.com/dvd-dev/hilo/commit/$cid)"
done
