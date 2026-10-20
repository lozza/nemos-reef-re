#!/bin/sh
# usage: fstr.sh <function-name-regex>  -> per function, the calls that carry known string args
grep -P "^\S+\t[^\t]*$1" /home/user/nemos-reef/re/calls.txt | grep -P '\tr[0-9]=' | awk -F'\t' '
{ f=$2; sub(/\(.*/, "", f); if (f != last) { print "== " f; last = f }
  t=$3; sub(/^-> /, "", t); sub(/\(.*/, "", t); print "   " t "  " $4 }'
