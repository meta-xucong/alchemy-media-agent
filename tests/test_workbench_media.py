import base64
from email.message import Message
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import unittest
from unittest.mock import patch

BUNDLE = Path(__file__).resolve().parents[1] / "src_skeleton/app/static/downloads/alchemy-api-mcp-v1.zip"
sys.path.insert(0, str(BUNDLE))
try:
    from alchemy_api_mcp import server as standalone_api_mcp
    from alchemy_api_mcp.versioned_tools import VersionedToolError, VersionedTools, WORKBENCH_IMAGE_TOOL
finally:
    sys.path.remove(str(BUNDLE))


PNG = b"\x89PNG\r\n\x1a\nfixture-original"
WEBP = b"RIFF\x14\x00\x00\x00WEBPfixture-preview"


class MediaResponse(BytesIO):
    def __init__(self, payload, content_type):
        super().__init__(payload)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class Opener:
    def __init__(self):
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append(request)
        assert timeout == 30
        if "/preview" in request.full_url:
            return MediaResponse(WEBP, "image/webp")
        return MediaResponse(PNG, "image/png")


class WorkbenchMediaTests(unittest.TestCase):
    def setUp(self):
        self.opener = Opener()
        self.tools = VersionedTools("https://alchemy.example", "test-key", opener=self.opener)

    def test_preview_mcp_result_remains_native_image(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": WORKBENCH_IMAGE_TOOL, "arguments": {"product": "v2", "output_id": "out_x"},
        }}
        with patch.object(VersionedTools, "from_environment", return_value=self.tools):
            result = standalone_api_mcp.dispatch(message)["result"]
        self.assertEqual(result["content"][1]["type"], "image")
        self.assertEqual(base64.b64decode(result["content"][1]["data"]), WEBP)
        self.assertEqual(self.opener.requests[0].full_url, "https://alchemy.example/api/v2/image/history/out_x/preview")

    def test_original_bytes_and_product_scopes(self):
        for product, path in (
            ("v2", "/api/v2/outputs/out_x/download?direct=true"),
            ("lab", "/api/lab/outputs/out_x/download"),
        ):
            with self.subTest(product=product):
                result = self.tools.call(WORKBENCH_IMAGE_TOOL, {
                    "product": product, "output_id": "out_x", "rendition": "original",
                })
                resource = result["content"][1]["resource"]
                self.assertEqual(base64.b64decode(resource["blob"]), PNG)
                self.assertEqual(resource["uri"], f"alchemy://original/{product}/out_x.png")
                request = self.opener.requests[-1]
                self.assertEqual(request.full_url, "https://alchemy.example" + path)
                self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
                self.assertEqual(request.get_method(), "GET")

    def test_rejects_missing_permissions_redirects_and_invalid_ids(self):
        with self.assertRaises(VersionedToolError):
            self.tools.call(WORKBENCH_IMAGE_TOOL, {"product": "v1", "output_id": "../out_x"})
        self.assertEqual(self.opener.requests, [])
        for status in (302, 403):
            with self.subTest(status=status), patch.object(
                self.opener, "open", side_effect=HTTPError("test", status, "", {}, None),
            ):
                with self.assertRaises(VersionedToolError) as error:
                    self.tools.call(WORKBENCH_IMAGE_TOOL, {"product": "lab", "output_id": "out_x"})
                self.assertEqual(error.exception.http_status, status)
                self.assertFalse(error.exception.outcome_unknown)

    def test_does_not_return_html_or_too_large_original(self):
        for body, mime in ((b"<html>", "text/html"), (b"not an image", "image/png"),
                           (PNG + bytes(8 * 1024 * 1024), "image/png")):
            with patch.object(self.opener, "open", return_value=MediaResponse(body, mime)):
                with self.assertRaises(VersionedToolError):
                    self.tools.call(WORKBENCH_IMAGE_TOOL, {"product": "lab", "output_id": "out_x", "rendition": "original"})

    def test_saves_byte_identical_local_file_without_overwriting(self):
        with TemporaryDirectory() as directory:
            tools = VersionedTools("https://alchemy.example", "test-key", opener=self.opener,
                                   output_directory=directory)
            args = {"product": "lab", "output_id": "out_x", "rendition": "original"}
            locator = tools.call(WORKBENCH_IMAGE_TOOL, args)["content"][1]
            self.assertEqual(locator["type"], "resource_link")
            original = Path(directory) / "lab-out_x.png"
            self.assertEqual(locator["uri"], original.as_uri())
            self.assertEqual(original.read_bytes(), PNG)
            self.assertEqual(tools.call(WORKBENCH_IMAGE_TOOL, args)["content"][1], locator)
            original.write_bytes(b"existing user file")
            with self.assertRaisesRegex(VersionedToolError, "workbench_output_already_exists"):
                tools.call(WORKBENCH_IMAGE_TOOL, args)
            self.assertEqual(original.read_bytes(), b"existing user file")


if __name__ == "__main__":
    unittest.main()
