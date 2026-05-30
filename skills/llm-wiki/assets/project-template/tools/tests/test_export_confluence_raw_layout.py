import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
CONFLUENCE_DIR = TOOLS_DIR / "confluence_sync"


def load_exporter():
    sys.path.insert(0, str(TOOLS_DIR))
    sys.path.insert(0, str(CONFLUENCE_DIR))
    spec = importlib.util.spec_from_file_location("export_confluence_tree", CONFLUENCE_DIR / "export_confluence_tree.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeImageResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: bytes, headers: dict[str, str] | None = None):
        self.payload = payload
        self.headers = headers or {}
        self.iterated = False

    def iter_content(self, chunk_size=8192):
        self.iterated = True
        yield self.payload


class FakeImageSession:
    request_timeout = 30
    request_interval = 0.0
    asset_request_interval = 0.0
    last_request_at = 0.0

    def __init__(self, response: FakeImageResponse):
        self.response = response

    def get(self, url, timeout=30, stream=False, headers=None):
        return self.response


class FailingImageSession:
    request_timeout = 30
    request_interval = 0.0
    asset_request_interval = 0.0
    last_request_at = 0.0

    def __init__(self, exporter):
        self.exporter = exporter

    def get(self, url, timeout=30, stream=False, headers=None):
        raise self.exporter.requests.ConnectionError("remote disconnected")


class ExportConfluenceRawLayoutTest(unittest.TestCase):
    def test_legacy_pages_root_path_overrides_are_normalized_to_flat_raw_paths(self):
        exporter = load_exporter()
        pages = {
            "642319073": exporter.PageNode(
                page_id="642319073",
                title="测试页面",
                url="https://cwiki.guazi.com/pages/viewpage.action?pageId=642319073",
                depth=1,
                html="<p>正文</p>",
            )
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "raw"
            paths = exporter.complete_page_path_overrides(
                pages,
                output_dir,
                pages_dir_name="",
                page_path_overrides={
                    "642319073": "pages-642319072/642319073-旧路径/index.md",
                },
            )

        self.assertEqual(paths["642319073"], "642319073-测试页面/index.md")

    def test_images_larger_than_default_limit_are_not_downloaded(self):
        exporter = load_exporter()
        big_response = FakeImageResponse(
            b"x" * 16,
            headers={"Content-Length": str(5 * 1024 * 1024 + 1)},
        )
        html = '<p><img src="/download/attachments/1/big.png" alt="big"></p>'

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            image_links = exporter.download_page_images(
                FakeImageSession(big_response),
                html,
                "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                page_dir,
            )

            self.assertEqual(image_links, {})
            self.assertFalse((page_dir / "assets" / "big.png").exists())
            self.assertFalse(big_response.iterated)

    def test_image_download_connection_error_is_skipped(self):
        exporter = load_exporter()
        html = '<p><img src="/download/attachments/1/flaky.png" alt="flaky"></p>'

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            image_links = exporter.download_page_images(
                FailingImageSession(exporter),
                html,
                "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                page_dir,
            )

            self.assertEqual(image_links, {})
            self.assertFalse((page_dir / "assets" / "flaky.png").exists())


if __name__ == "__main__":
    unittest.main()
