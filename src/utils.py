import asyncio
import random
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Union

from pyrogram import Client, emoji, filters
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from button import ButtonFactory, GroupButton


def cut(x: str, length: int) -> List[str]:
    ret = []
    while x != "":
        ret.append(x[:length])
        x = x[length:]
    return ret


async def selection(
    app: Client,
    user: int,
    options: List[Any],
    message_text: str = "Select",
    multi_selection: bool = True,
    name_selector: Callable[[Any], str] = None,
    max_options_per_page: int = 8,
    message: Message = None,
    delete: bool = True,
) -> Union[List[Any], Tuple[List[Any], Message]]:
    ns = SimpleNamespace()
    opt = list()

    ns.page = 0
    ns.done = False
    ns.canceled = False

    total_pages = len(options) // max_options_per_page + (
        1 if len(options) % max_options_per_page != 0 else 0
    )

    factory = ButtonFactory()
    select_group = factory.create_group("select")
    items = [select_group.add(k) for k in options]

    next_button = factory.create_action("next")
    back_button = factory.create_action("back")
    selectall_button = factory.create_action("select all")
    unselectall_button = factory.create_action("unselect all")
    done_button = factory.create_action("done")
    cancel_button = factory.create_action("cancel")

    def create_button(button: GroupButton):
        name = button.value
        if callable(name_selector):
            name = name_selector(name)
        name = str(name)

        if len(name) >= 20:
            name = name[:40]
        selected = name in opt
        return [button.button(f"{emoji.CHECK_MARK if selected else ''}{name}")]

    def navigation_buttons():
        ret = []

        if ns.page > 0:
            ret.append(back_button.button(f"{emoji.LEFT_ARROW} {ns.page - 1}"))
        if ns.page < total_pages - 1:
            ret.append(next_button.button(f"{ns.page + 1} {emoji.RIGHT_ARROW}"))

        return ret

    async def _select(app: Client, callback_query: CallbackQuery):
        a = ns.page * max_options_per_page
        b = min(len(options), (ns.page + 1) * max_options_per_page)

        # yapf: disable
        extra = [
            [
                selectall_button.button('Select all'),
                unselectall_button.button('Unselect all')
            ],
            [done_button.button(f'{emoji.CHECK_MARK_BUTTON} DONE'), cancel_button.button(f'{emoji.CROSS_MARK_BUTTON} CANCEL')]
        ]
        navigation = navigation_buttons()
        markup = InlineKeyboardMarkup(
            [create_button(opt) for opt in items[a:b]] +
            ([navigation] if len(navigation) > 0 else []) + (extra if multi_selection else [[cancel_button.button('Cancel')]])
        )
        # yapf: enable

        if callback_query == None:
            if message == None:
                return await app.send_message(user, message_text, reply_markup=markup)
            else:
                await message.edit(message_text, reply_markup=markup)
                return message
        else:
            await callback_query.edit_message_reply_markup(markup)

    async def _select_all(app: Client, callback_query: CallbackQuery):
        opt = options.copy()
        await _select(app, callback_query)

    async def _unselect_all(app: Client, callback_query: CallbackQuery):
        opt.clear()
        await _select(app, callback_query)

    async def _next_page(app: Client, callback_query: CallbackQuery):
        if ns.page < total_pages - 1:
            ns.page += 1
        await _select(app, callback_query)

    async def _back_page(app: Client, callback_query: CallbackQuery):
        if ns.page > 0:
            ns.page -= 1
        await _select(app, callback_query)

    async def _done(_, callback_query: CallbackQuery):
        await callback_query.message.delete(True)
        ns.done = True

    async def _cancel(_, callback_query: CallbackQuery):
        await callback_query.message.delete(True)
        ns.canceled = True
        ns.done = True

    async def _select_item(app: Client, callback_query: CallbackQuery):
        m = factory.get(callback_query.data).value

        if m in opt:
            opt.remove(m)
        else:
            opt.append(m)

        if multi_selection:
            await _select(app, callback_query)
        else:
            if delete:
                await callback_query.message.delete(True)
            ns.done = True

    handlers = [
        select_group.callback_handler(_select_item),
        next_button.callback_handler(_next_page),
        back_button.callback_handler(_back_page),
        selectall_button.callback_handler(_select_all),
        unselectall_button.callback_handler(_unselect_all),
        done_button.callback_handler(_done),
        cancel_button.callback_handler(_cancel),
    ]

    for u in handlers:
        app.add_handler(u)

    message = await _select(app, None)
    while not ns.done:
        await asyncio.sleep(0.5)

    for h in handlers:
        app.remove_handler(h)

    if delete:
        return opt if not ns.canceled else None
    return (opt if not ns.canceled else None, message)