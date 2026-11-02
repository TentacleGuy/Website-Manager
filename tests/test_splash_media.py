"""Exercise actual media responses without Docker, sockets or private project data."""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
_isolated=tempfile.TemporaryDirectory()
os.environ.setdefault('VMM_DATA',_isolated.name)
import server


class SplashMediaTests(unittest.TestCase):
    def response(self,range_header=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'assets').mkdir()
            (root/'assets/tentacle-web.mp4').write_bytes(b'0123456789')
            handler=object.__new__(server.Handler)
            handler.path='/assets/tentacle-web.mp4'
            handler.headers={'Host':'localhost:8090'}
            if range_header is not None:handler.headers['Range']=range_header
            handler.wfile=io.BytesIO();status=[];headers={}
            handler.send_response=status.append
            handler.send_header=lambda key,value:headers.update({key:value})
            handler.end_headers=lambda:None
            with patch.object(server,'STATIC',root):handler.do_GET()
            return status[0],headers,handler.wfile.getvalue()

    def test_full_video(self):
        code,headers,body=self.response()
        self.assertEqual(code,200);self.assertEqual(body,b'0123456789')
        self.assertEqual(headers['Content-Type'],'video/mp4')
        self.assertEqual(headers['Content-Length'],'10')
        self.assertEqual(headers['Accept-Ranges'],'bytes')

    def test_safari_probe_and_open_ended_ranges(self):
        for request,expected,content_range in [('bytes=0-1',b'01','bytes 0-1/10'),('bytes=7-',b'789','bytes 7-9/10'),('bytes=-3',b'789','bytes 7-9/10'),('bytes=8-99',b'89','bytes 8-9/10')]:
            with self.subTest(request=request):
                code,headers,body=self.response(request)
                self.assertEqual(code,206);self.assertEqual(body,expected)
                self.assertEqual(headers['Content-Range'],content_range)
                self.assertEqual(headers['Content-Length'],str(len(expected)))

    def test_invalid_ranges_do_not_return_video(self):
        for request in ('bytes=10-','bytes=5-2','bytes=-0','bytes=-','bytes=0-1,3-4','bad'):
            with self.subTest(request=request):
                code,headers,body=self.response(request)
                self.assertEqual(code,416);self.assertEqual(body,b'')
                self.assertEqual(headers['Content-Range'],'bytes */10')
