#!/bin/bash
git log --oneline | while read l;do
  CID=$(echo $l | cut -f 1 -d " ")
  MSG=$(echo $l | cut -f 2- -d " ")
  echo "* [$MSG](https://github.com/dvd-dev/hilo/commit/$CID)"
done
