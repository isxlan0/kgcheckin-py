import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.management import ManagementController


class ManagementTests(unittest.TestCase):
    def test_render_qr_lines_scales_down_to_requested_width(self) -> None:
        image = Image.new("1", (120, 120), 1)
        for y in range(20, 100):
            for x in range(20, 100):
                image.putpixel((x, y), 0)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        lines = ManagementController.render_qr_lines(buffer.getvalue(), max_columns=32)

        self.assertTrue(lines)
        self.assertTrue(all(len(line) <= 32 for line in lines))

    def test_add_account_by_phone_with_code_skips_resending_captcha(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.send_captcha_calls = 0
                self.login_calls = 0

            def send_captcha(self, _phone: str) -> dict[str, object]:
                self.send_captcha_calls += 1
                return {"status": 1}

            def login_with_phone(self, phone: str, code: str) -> dict[str, object]:
                self.login_calls += 1
                return {"status": 1, "data": {"userid": phone, "token": f"token-{code}"}}

            def get_user_detail_by_credentials(self, user_id: str, _token: str) -> dict[str, object]:
                return {"data": {"nickname": f"user-{user_id}"}}

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakeClient()
            paths = RepoPaths.resolve(Path(temp_dir))
            controller = ManagementController(
                ConfigStore(paths),
                AccountStore(paths),
                client_factory=lambda: client,
            )

            controller.add_account_by_phone(phone="13800138000", code="1234", emit=lambda _message: None)

            accounts = controller.list_accounts()
            self.assertEqual(client.send_captcha_calls, 0)
            self.assertEqual(client.login_calls, 1)
            self.assertEqual(len(accounts), 1)
            self.assertEqual(accounts[0].nickname, "user-13800138000")


if __name__ == "__main__":
    unittest.main()
