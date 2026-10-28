"""Exercise the MCP server and the browser endpoint together."""

import asyncio
import json
import os
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


def request(url: str, data: dict | None = None, origin: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    body = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=15) as response:
        return json.load(response)


class DesktopIntegrationTest(unittest.TestCase):
    def test_diagram_selection_and_refresh(self) -> None:
        asyncio.run(self.exercise())

    async def exercise(self) -> None:
        params = StdioServerParameters(command=str(ROOT / "desktop/.venv/bin/uml-viewer-desktop"), env=os.environ.copy())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                missing = await client.call_tool("show_diagram", {"path": "relative.edn"})
                self.assertTrue(missing.isError)
                result = await client.call_tool("show_diagram", {"path": str(ROOT / "examples/library.edn")})
                self.assertFalse(result.isError, result.content)
                session = json.loads(result.content[0].text)
                url = session["url"]
                sid = session["session_id"]
                scene = request(url + "/scene")["scene"]
                catalog = next(item for item in scene["classes"] if item["name"] == "Catalog")
                self.assertGreater(len(scene["edges"]), 0)
                selection = {"kind": "class", "id": catalog["id"]}
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    request(url + "/selection", selection, "https://example.invalid")
                self.assertEqual(denied.exception.code, 403)
                hostile = urllib.request.Request(url + "/scene", headers={"Host": "attacker.invalid"})
                with self.assertRaises(urllib.error.HTTPError) as denied_host:
                    urllib.request.urlopen(hostile, timeout=15)
                self.assertEqual(denied_host.exception.code, 404)
                origin = "/".join(url.split("/")[:3])
                with self.assertRaises(urllib.error.HTTPError) as unknown:
                    request(url + "/selection", {"kind": "class", "id": "missing"}, origin)
                self.assertEqual(unknown.exception.code, 400)
                self.assertTrue(request(url + "/selection", selection, origin)["ok"])
                selected = await client.call_tool("get_selection", {"session_id": sid})
                self.assertEqual(json.loads(selected.content[0].text)["selection"]["item"]["name"], "Catalog")
                updated = await client.call_tool("update_diagram", {"session_id": sid})
                self.assertFalse(updated.isError, updated.content)
                self.assertEqual(request(url + "/scene")["version"], 2)
                selected = await client.call_tool("get_selection", {"session_id": sid})
                self.assertIsNone(json.loads(selected.content[0].text)["selection"])
                closed = await client.call_tool("close_diagram", {"session_id": sid})
                self.assertFalse(closed.isError, closed.content)
                with self.assertRaises(urllib.error.HTTPError) as expired:
                    request(url + "/scene")
                self.assertEqual(expired.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
