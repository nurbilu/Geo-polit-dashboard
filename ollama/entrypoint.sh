#!/bin/sh
# Boots the Ollama server, then ensures the Llama 4 Scout model is available.
# Pulls OLLAMA_MODEL (default llama4:scout). If a custom FP8 Modelfile is
# mounted at /Modelfile, it is built into the model instead of a plain pull.
set -e

MODEL="${OLLAMA_MODEL:-llama4:scout}"

echo "[ollama] starting server..."
ollama serve &
SERVER_PID=$!

echo "[ollama] waiting for API..."
until ollama list >/dev/null 2>&1; do
  sleep 2
done

if ollama list | grep -q "$MODEL"; then
  echo "[ollama] model '$MODEL' already present."
elif [ -f /Modelfile ] && grep -qiE '^\s*FROM\s+' /Modelfile; then
  echo "[ollama] building '$MODEL' from custom Modelfile (FP8)..."
  ollama create "$MODEL" -f /Modelfile || echo "[ollama] custom build failed; falling back to pull"
  ollama list | grep -q "$MODEL" || ollama pull "$MODEL"
else
  echo "[ollama] pulling '$MODEL' (this can take a while)..."
  ollama pull "$MODEL"
fi

echo "[ollama] ready. Serving '$MODEL'."
wait "$SERVER_PID"
