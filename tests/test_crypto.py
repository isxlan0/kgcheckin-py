import unittest

from kugou_signer.constants import PUBLIC_RSA_KEY
from kugou_signer.kugou.crypto import aes_decrypt, aes_encrypt, md5_hex, rsa_encrypt_no_padding
from kugou_signer.kugou.protocol import sign_params_key, signature_android_params, signature_web_params


class CryptoTests(unittest.TestCase):
    def test_md5_matches_js(self) -> None:
        self.assertEqual(md5_hex("abc123"), "e99a18c428cb38d5f260853678922e03")

    def test_aes_fixed_key_matches_js(self) -> None:
        actual = aes_encrypt(
            {"mobile": "13800138000", "code": "123456"},
            "90b8382a1bb4ccdcf063102053fd75b8",
            "f063102053fd75b8",
        )
        self.assertEqual(
            actual,
            "039674f96c876f70b101e8a6ebbfd2ea8f7676e6576b9be26ceff105fe6590a3bec9e0521f3ee8c9eb75e8ec195b7b9a",
        )

    def test_aes_roundtrip_matches_js_vector(self) -> None:
        self.assertEqual(aes_decrypt("8b86ef168c5f90f02d64122b8b481204", "test1234"), "hello world")

    def test_rsa_no_padding_matches_js(self) -> None:
        actual = rsa_encrypt_no_padding({"clienttime_ms": 1700000000000, "key": "abcd"}, PUBLIC_RSA_KEY)
        self.assertEqual(
            actual,
            "a9aff7e2b1df511ab266032e3816c799aa411f27b2352ea0c01cd8bdd02da65fb0f3caac51c52bf014421e62c9913d99d7d081312e8606742094f9dc99175dc4956d2d4081d752a490c9c1e7f60a74f52a77ebf047411731e60d39bef23b5536fee9a150b4e315893d5d2dbb62122e002120b7de7a244a91b22b18f7641a5e21",
        )

    def test_signatures_match_js(self) -> None:
        self.assertEqual(sign_params_key(1700000000000), "a16d61ca1308a00264f488e64029b29a")
        self.assertEqual(
            signature_android_params(
                {
                    "appid": 1005,
                    "clientver": 20489,
                    "clienttime": 1700000000,
                    "dfid": "-",
                    "mid": "m1",
                    "uuid": "u1",
                    "userid": 0,
                },
                '{"businessid":5,"mobile":"13800138000","plat":3}',
            ),
            "d1cd3a41c132d7c5081d49fbdb2e5dbb",
        )
        self.assertEqual(
            signature_web_params(
                {
                    "appid": 1001,
                    "plat": 4,
                    "qrcode_txt": "https://h5.kugou.com/apps/loginQRCode/html/index.html?appid=1005&",
                    "srcappid": 2919,
                    "type": 1,
                }
            ),
            "92696af811fed7cb60c301a3e39ba55a",
        )


if __name__ == "__main__":
    unittest.main()
