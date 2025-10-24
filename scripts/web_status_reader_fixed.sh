#!/bin/bash
# Robust status reader with 3-second timeout

TMP_OUT=$(mktemp)
{
  $(dirname "$0")/System_State_Reading1.sh > "$TMP_OUT" 2>&1 &
  PID=$!
  
  for _ in {1..30}; do
    if grep -qE '^(server off|shutdown|hybernate|active|unknown)' "$TMP_OUT"; then
      # Get the last status line (most recent)
      STATUS=$(grep -E '^(server off|shutdown|hybernate|active|unknown)' "$TMP_OUT" | tail -n 1)
      
      # Normalize the output
      case "$STATUS" in
        "server off") echo "server off" ;;
        "hybernate") echo "hybernate" ;;
        "shutdown") echo "shutdown" ;;
        "active") echo "active" ;;
        *) echo "unknown" ;;
      esac
      
      kill $PID 2>/dev/null
      rm -f "$TMP_OUT"
      exit 0
    fi
    sleep 0.1
  done
  
  kill $PID 2>/dev/null
  rm -f "$TMP_OUT"
  echo "unknown"
  exit 1
} 2>/dev/null
