from __future__ import annotations

from kugou_signer.config.store import AccountStore
from kugou_signer.models import Account


class AccountService:
    def __init__(self, store: AccountStore) -> None:
        self.store = store

    def list_accounts(self) -> list[Account]:
        return self.store.load()

    def save_login(self, user_id: str, token: str, nickname: str = "") -> tuple[Account, bool]:
        existing_accounts = self.store.load()
        for existing in existing_accounts:
            if existing.user_id == str(user_id):
                existing.token = token
                existing.nickname = nickname or existing.nickname
                return self.store.upsert(existing)
        account = Account(user_id=str(user_id), token=token, nickname=nickname)
        return self.store.upsert(account)

    def remove_account(self, user_id: str) -> bool:
        return self.store.remove(str(user_id))
