# PaperclipMaxxer

PaperclipMaxxer is a Python Discord bot that uses OpenRouter with `openai/gpt-oss-120b`.
You mention the bot to ask questions. After that, it keeps a short active conversation per
channel/user and uses a small LLM decision step to decide whether unmentioned follow-up messages
are truly addressed to it. Otherwise it stays silent.

## What is included

- Python Discord gateway bot using `discord.py`.
- OpenRouter chat completions client.
- SQLite memory for recent channel messages and active back-and-forths.
- Smart context retrieval:
  - always stores recent text messages it can see;
  - only fetches Discord channel history before a mention when the prompt appears to reference prior chat;
  - includes recent stored bot/user conversation for follow-ups;
  - uses a decision prompt before replying to unmentioned active-thread messages.
- Optional Cloudflare Worker health endpoint.

Cloudflare Workers cannot run this Python Discord gateway bot because Discord gateway bots need a
long-lived WebSocket process and this project is intentionally Python. The Worker in `worker/` is
there for deployment visibility/health only. Run the Python bot on your machine, a VPS, or another
long-running Python host.

## API key location

Put your keys in a local `.env` file at the project root:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
DISCORD_TOKEN=your-discord-bot-token
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-oss-120b
```

Do not commit `.env`.

## Discord setup

1. Go to <https://discord.com/developers/applications>.
2. Create an application named `PaperclipMaxxer`.
3. Open `Bot`, then create a bot if Discord has not created one.
4. Click `Reset Token` or `View Token`, then put that token in `DISCORD_TOKEN` in `.env`.
5. In `Bot -> Privileged Gateway Intents`, enable `Message Content Intent`.
6. In `OAuth2 -> URL Generator`, select:
   - `bot`
   - permissions: `Send Messages`, `Read Message History`, `View Channels`
7. Open the generated invite URL and add the bot to your server.
8. In Discord, mention it: `@PaperclipMaxxer what did we just discuss?`

The bot must be able to read the channel. If it cannot see a private channel, add the bot role to
that channel permissions.

## Run locally with uv

Use Python 3.11 or newer.

```bash
uv run paperclipmaxxer
```

The first run creates `.venv`, resolves dependencies from `pyproject.toml`, and writes `uv.lock`.
You can also run the module directly:

```bash
uv run python -m paperclipmaxxer.bot
```

You should see a log line like:

```text
Logged in as PaperclipMaxxer#1234 (...)
```

## Behavior

- Mentioned messages always route to the bot.
- Unmentioned messages only get a response when the conversation with that user/channel is still
  active and the decision model says the message is a direct follow-up.
- Replying directly to the bot's previous Discord message is treated as an active follow-up.
- The active conversation timeout defaults to 15 minutes. Change `CONVERSATION_TTL_SECONDS` in
  `.env` if you want it shorter or longer.

## Optional Cloudflare Worker

This does not host the Python bot. It gives you a tiny deployable endpoint for status checks.

```bash
cd worker
npm install
npx wrangler login
npx wrangler deploy
```

After deploy, test:

```bash
curl https://paperclipmaxxer.<your-workers-subdomain>.workers.dev/health
```

Expected response:

```json
{
  "ok": true,
  "service": "PaperclipMaxxer",
  "note": "The Python Discord gateway bot must be running separately."
}
```

## Production notes

- Keep `.env` on the machine that runs the bot.
- Use a process manager such as `systemd`, `pm2`, Docker, or your host's restart policy.
- The SQLite database path defaults to `paperclipmaxxer.sqlite3`; set `DATABASE_PATH` if you want
  it somewhere else.
- If OpenRouter changes the model ID, update `OPENROUTER_MODEL`.
