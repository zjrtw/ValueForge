import unittest
from unittest.mock import patch, MagicMock

from src.storage.r2_client import get_r2_client


class GetR2ClientTest(unittest.TestCase):
    @patch("src.storage.r2_client.boto3.client")
    @patch("src.storage.r2_client.settings")
    def test_creates_s3_client_with_r2_settings(self, mock_settings, mock_boto_client):
        mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
        mock_settings.R2_ACCESS_KEY_ID = "test_key"
        mock_settings.R2_SECRET_ACCESS_KEY = "test_secret"

        get_r2_client()

        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args

        self.assertEqual(call_kwargs.args[0], "s3")
        self.assertEqual(call_kwargs.kwargs["endpoint_url"], "https://test.r2.cloudflarestorage.com")
        self.assertEqual(call_kwargs.kwargs["aws_access_key_id"], "test_key")
        self.assertEqual(call_kwargs.kwargs["aws_secret_access_key"], "test_secret")
        self.assertEqual(call_kwargs.kwargs["region_name"], "auto")

    @patch("src.storage.r2_client.boto3.client")
    @patch("src.storage.r2_client.settings")
    def test_uses_s3v4_signature(self, mock_settings, mock_boto_client):
        mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
        mock_settings.R2_ACCESS_KEY_ID = "key"
        mock_settings.R2_SECRET_ACCESS_KEY = "secret"

        get_r2_client()

        config_arg = mock_boto_client.call_args.kwargs["config"]
        self.assertEqual(config_arg.signature_version, "s3v4")

    @patch("src.storage.r2_client.boto3.client")
    @patch("src.storage.r2_client.settings")
    def test_configures_retries(self, mock_settings, mock_boto_client):
        mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
        mock_settings.R2_ACCESS_KEY_ID = "key"
        mock_settings.R2_SECRET_ACCESS_KEY = "secret"

        get_r2_client()

        config_arg = mock_boto_client.call_args.kwargs["config"]
        self.assertEqual(config_arg.retries["max_attempts"], 3)
        self.assertEqual(config_arg.retries["mode"], "adaptive")

    @patch("src.storage.r2_client.boto3.client")
    @patch("src.storage.r2_client.settings")
    def test_returns_boto3_client(self, mock_settings, mock_boto_client):
        mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
        mock_settings.R2_ACCESS_KEY_ID = "key"
        mock_settings.R2_SECRET_ACCESS_KEY = "secret"
        fake_client = MagicMock()
        mock_boto_client.return_value = fake_client

        result = get_r2_client()

        self.assertIs(result, fake_client)

    @patch("src.storage.r2_client.boto3.client")
    @patch("src.storage.r2_client.settings")
    def test_each_call_creates_new_client(self, mock_settings, mock_boto_client):
        mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
        mock_settings.R2_ACCESS_KEY_ID = "key"
        mock_settings.R2_SECRET_ACCESS_KEY = "secret"

        get_r2_client()
        get_r2_client()

        self.assertEqual(mock_boto_client.call_count, 2)


if __name__ == "__main__":
    unittest.main()
