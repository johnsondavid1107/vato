"""Telegram channel (spec §5, M4): family group chat in, butler text out,
and the Tier-3 inline Confirm/Refuse buttons.

Trust model, enforced mechanically:
- One hardcoded allowlist (`config.yaml: allowed_user_ids`). A message from
  any other user ID — including DMs — is silently ignored and audit-logged.
  The bot never replies, never reacts: it must not reveal its existence.
- Long polling only; zero inbound ports.
- Button taps are gated by the same allowlist; a stranger tapping a leaked
  confirm button gets a silent no-op.

Threading: python-telegram-bot is async and lives on the daemon's main event
loop. Brain.respond is blocking, so handlers run it via asyncio.to_thread.
`confirm()` is the flip side — called from worker threads (the brain's tool
loop, voice or telegram), it schedules the button message onto the loop and
blocks the calling thread on a concurrent Future until a family member taps
or the timeout passes.

Setup self-test (collects the IDs for config.yaml):
    python -m integrations.telegram_bot
"""

import asyncio
import concurrent.futures
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters,
)

from brain.client import Brain
from core.audit import AuditLog
from core.config import require_env

log = logging.getLogger("vato.telegram")

CONFIRM_PREFIX = "vato-confirm"


class TelegramChannel:
    def __init__(self, cfg: dict, brain: Brain, audit: AuditLog):
        self._token = require_env("TELEGRAM_BOT_TOKEN")
        self._brain = brain
        self._audit = audit
        self._allowed = {int(i) for i in (cfg.get("allowed_user_ids") or [])}
        tg = cfg.get("telegram") or {}
        self._family_chat_id = tg.get("family_chat_id") or 0
        self._confirm_timeout = float(tg.get("confirm_timeout_seconds", 120))
        # token -> Future resolved by a button tap with (approved, first_name)
        self._pending: dict[str, concurrent.futures.Future] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

        self._app = (Application.builder().token(self._token).build())
        self._app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self._on_message))
        self._app.add_handler(CallbackQueryHandler(
            self._on_button, pattern=rf"^{CONFIRM_PREFIX}\|"))

    # ── lifecycle (runs on the daemon's asyncio loop) ─────────────────────────

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(
            allowed_updates=["message", "callback_query"])
        me = await self._app.bot.get_me()
        log.info("Telegram channel up as @%s (allowlist: %d user(s))",
                 me.username, len(self._allowed))

    async def stop(self) -> None:
        try:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        except Exception:
            log.exception("Telegram shutdown failed")

    # ── inbound messages ──────────────────────────────────────────────────────

    async def _on_message(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        msg = update.effective_message
        if msg is None or msg.text is None:
            return
        if user is None or user.id not in self._allowed:
            # Spec §5: silently ignored and logged. No reply of any kind.
            log.info("Ignored Telegram message from non-allowlisted user %s",
                     user.id if user else "?")
            self._audit.record(
                channel="telegram",
                requester=str(user.id) if user else "unknown",
                action="incoming_message",
                args={"chat_id": msg.chat_id},
                tier=0,
                outcome="ignored: not allowlisted",
            )
            return

        # Group chats share one brain history, so tag who is speaking.
        text = f"[{user.first_name}] {msg.text}"
        reply = await asyncio.to_thread(self._brain.respond, text, str(user.id))
        await msg.reply_text(reply)

    # ── Tier-3 confirmation gate (spec §6) ────────────────────────────────────

    def confirm(self, text: str) -> tuple[bool, str]:
        """Blocking; called from worker threads via ToolRouter.confirmer."""
        if self._loop is None:
            return False, "the Telegram bot is not running"
        if not self._family_chat_id:
            return False, ("telegram.family_chat_id is not set in config.yaml "
                           "(run: python -m integrations.telegram_bot)")
        token = uuid.uuid4().hex[:12]
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._pending[token] = fut
        asyncio.run_coroutine_threadsafe(
            self._send_confirm(token, text), self._loop)
        try:
            approved, who = fut.result(timeout=self._confirm_timeout)
            return approved, (f"approved by {who}" if approved
                              else f"refused by {who}")
        except concurrent.futures.TimeoutError:
            return False, (f"nobody confirmed within "
                           f"{int(self._confirm_timeout)} seconds")
        finally:
            self._pending.pop(token, None)

    async def _send_confirm(self, token: str, text: str) -> None:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm",
                                 callback_data=f"{CONFIRM_PREFIX}|{token}|yes"),
            InlineKeyboardButton("❌ Refuse",
                                 callback_data=f"{CONFIRM_PREFIX}|{token}|no"),
        ]])
        try:
            await self._app.bot.send_message(
                chat_id=self._family_chat_id, text=text, reply_markup=keyboard)
        except Exception as exc:
            fut = self._pending.get(token)
            if fut is not None and not fut.done():
                fut.set_exception(exc)

    async def _on_button(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = query.from_user
        if user is None or user.id not in self._allowed:
            await query.answer()  # silent no-op; reveal nothing (§5)
            return
        _, token, decision = query.data.split("|", 2)
        approved = decision == "yes"
        fut = self._pending.get(token)
        if fut is None or fut.done():
            await query.answer("This request has already expired.")
            return
        fut.set_result((approved, user.first_name))
        await query.answer("Confirmed." if approved else "Refused.")
        verdict = (f"✅ Approved by {user.first_name}" if approved
                   else f"❌ Refused by {user.first_name}")
        try:  # freeze the message so the buttons can't be tapped twice
            await query.edit_message_text(
                f"{query.message.text}\n\n{verdict}")
        except Exception:
            pass


# ── Setup self-test: python -m integrations.telegram_bot ─────────────────────
# Verifies the token and prints the user ID + chat ID of every message it
# sees, so David can fill config.yaml (allowed_user_ids, family_chat_id).
# It never replies — strangers learn nothing even during setup.

def _selftest() -> None:
    import dotenv

    from core.config import ROOT
    dotenv.load_dotenv(ROOT / ".env")

    async def main() -> None:
        token = require_env("TELEGRAM_BOT_TOKEN")
        app = Application.builder().token(token).build()

        async def show(update: Update, _ctx) -> None:
            u, m = update.effective_user, update.effective_message
            if u is None or m is None:
                return
            print(f"  message from user_id={u.id} ({u.first_name})"
                  f"  in chat_id={m.chat_id} ({m.chat.type}): {m.text!r}")

        app.add_handler(MessageHandler(filters.ALL, show))
        await app.initialize()
        me = await app.bot.get_me()
        print(f"Token OK — bot is @{me.username}.")
        print("Listening for 60s. Send a message in the family group chat now")
        print("(and have each family member send one). Copy the user_ids into")
        print("config.yaml allowed_user_ids and the group chat_id into")
        print("telegram.family_chat_id. Note: group messages only show up if")
        print("privacy mode is disabled (@BotFather → /setprivacy → Disable).")
        await app.start()
        await app.updater.start_polling(allowed_updates=["message"])
        try:
            await asyncio.sleep(60)
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        print("Self-test done.")

    asyncio.run(main())


if __name__ == "__main__":
    _selftest()
